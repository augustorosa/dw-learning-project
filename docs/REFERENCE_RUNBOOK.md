# Reference runbook: what "done" looks like

This is the operating runbook for a finished build: every track done, every story
verified. Use it two ways. Read it at the start to see where you are heading, and use it at
BF-55 as a model for writing your own. Your object names should match. Your commands may
differ, and that is fine.

The anchor numbers on this page were computed independently in Python, in SQL over the
CSV files, and in SQL over a Postgres load of the same data. The Snowflake, Sigma and agent
rows are the values a correct build must return. They are targets, not screenshots.

## The numbers that matter

As at **2024-09-13**:

| Surface | Passings | Subscribers | Penetration |
| --- | ---: | ---: | ---: |
| Raw source, rules applied by hand | 16,374 | 1,316 | 8.04% |
| dbt fact `fct_passings_subscribers_monthly` | 16,374 | 1,316 | 8.04% |
| Semantic view `sv_brindle_by_market` | 16,374 | 1,316 | 8.04% |
| Cortex agent `BRINDLE_GENERAL_AGENT` (optional) | 16,374 | 1,316 | 8.04% |
| Sigma workbook KPI tiles (optional) | 16,374 | 1,316 | 8.04% |

NetSuite track, same date: build capex paid to date **$23,287,443.42** and capex per passing
**$1,422.22**, from the hand-written raw query, `fct_market_build_economics_monthly`
and the semantic view alike.

## Daily sequence

### 1. Check the source

Core track: the source is `data/csv/`, and `python data/generate_data.py --check` proves it
has not drifted. AWS track: confirm the RDS instance is `available`.

```bash
aws rds describe-db-instances --db-instance-identifier brindle-pg \
  --query 'DBInstances[0].DBInstanceStatus' --output text
```

If the instance is gone, `aws/provision.sh` rebuilds it in about ten minutes. Then
reload with `postgres/load_postgres.sh`.

### 2. Land the data

```bash
# core track
snow sql -f snowflake/raw/load_raw_from_csv.sql -c brindle \
  --role brindle_ingest_rl --warehouse brindle_ingest_wh

# AWS track
python postgres/load_to_snowflake.py

# NetSuite track
snow sql -f snowflake/raw/load_netsuite_from_csv.sql -c brindle \
  --role brindle_ingest_rl --warehouse brindle_ingest_wh
```

The load prints its own checks. You want 18,253 locations and **1,442** blank dates.

### 3. Build the warehouse

By hand, while you are changing models:

```bash
cd dbt
export SNOWFLAKE_PAT="<your_pat>"
dbt source freshness --profiles-dir .
dbt build --profiles-dir .
dbt snapshot --profiles-dir .
```

Once BF-73 is in place, the daily build is the task, not this shell. After BF-75 the
task runs `--target prod`.

```sql
execute task brindle_dev_anl_db.anl.build_brindle_daily;
```

Suspend it when you stop working. A resumed task on a cron will spend credits every day.

```sql
alter task brindle_dev_anl_db.anl.build_brindle_daily suspend;
```

Expect zero errors and zero warnings on fresh data. Then confirm the anchor:

```bash
snow sql -c brindle --role brindle_transform_rl --warehouse brindle_transform_wh -q "
  select sum(passings) p, sum(subscribers) s,
         round(100.0 * sum(subscribers) / sum(passings), 2) pen
  from brindle_dev_anl_db.anl.fct_passings_subscribers_monthly
  where year_month = '2024-09'"
```

### 4. Open the front doors

- **Semantic view**, for a SQL audience:

```sql
select * from semantic_view(
    brindle_dev_anl_db.anl.sv_brindle_by_market
    metrics penetration.total_passings, penetration.total_subscribers, penetration_pct
    dimensions market.market_name
    where calendar.year_month = '2024-09'
) order by penetration_pct desc;
```

- **Cortex agent**: `SNOWFLAKE_INTELLIGENCE.AGENTS.BRINDLE_GENERAL_AGENT`.
- **Sigma workbook**: "Brindle Fiber: Cohort Performance By Market", with KPI tiles, the
  by-market table, and penetration by market.

## Agent questions worth opening a demo with

The first two are the demo. A naive build answers both confidently and wrongly.

1. **"What is penetration by market as of September 2024?"** The report page in words.
   Foxglove Ridge is top at 12.57%, Dunmore Plains is bottom at 5.28%.
2. **"What is the total number of homes passed across all of 2024?"** The agent declines
   to add the months up, explains that passings is a cumulative balance, and returns the
   ending balance, 16,374. A build without `NON ADDITIVE BY` returns 129,127.
3. **"What is the average penetration rate across our six markets?"** It returns the
   blended 8.04% and points out that averaging the six market rates (8.70%) would
   mislead.
4. **"What is our monthly churn by market?"** It declines, and says why: churn needs flow
   data, and this model holds only balances.
5. **"What has each home passed cost us to build, by market?"** NetSuite track only. It
   returns Cobalt Hills at $1,891.33 down to Dunmore Plains at $1,015.84, and $1,422.22
   for the company, and says that $589,924 of capex has no market.

## What is real and what is stubbed

**Stubbed by design:** ingestion. The core track loads CSVs straight into raw, and the
AWS track uses a hand-written loader. Both reproduce the Fivetran raw shape
(`_fivetran_synced`, `_fivetran_deleted`), so wiring up a real connector (BF-14) should
change no model, test, semantic view, agent or workbook. The NetSuite track works the same way: its CSVs stand in for a Fivetran NetSuite
connector, deletes arrive as `_fivetran_deleted` flags, and a real connector would land
the same tables.

**Out of scope for this version:**

- A Sigma *data model*. The Sigma API does not create them, so that half would be built
  in the Sigma UI. The workbook reads the governed view directly, which is a reasonable
  first version.
- Cohort and vintage grain (stretch goal 1).
- A second DCM environment. Prod databases are BF-75, created in SQL.

## Things that will bite you

The full list is in [`GOTCHAS.md`](GOTCHAS.md). The three most likely to cost an hour on a
normal day:

1. **A green `dbt build` is not proof the numbers are right.** Defect A leaves the report
   month exact and breaks 2022. `assert_balances_are_non_decreasing.sql` exists because
   of it. Do not delete it.
2. **Sigma `spec/verify` returning `{"valid": true}` does not mean the formulas resolve.**
   Always export an element's data to confirm.
3. **Sigma's connection inventory is cached.** A new view returns "Warehouse table not
   found" until you call `POST /v2/connections/{id}/sync`.

## Teardown

AWS track first:

```bash
aws/teardown.sh      # RDS instance, then subnet group, then security group
```

Snowflake, in dependency order:

```sql
use role accountadmin;
drop agent if exists snowflake_intelligence.agents.brindle_general_agent;
drop user if exists brindle_sigma_user;
alter task if exists brindle_dev_anl_db.anl.build_brindle_daily suspend;
drop task if exists brindle_dev_anl_db.anl.build_brindle_daily;
drop database if exists brindle_dev_anl_db;
drop database if exists brindle_dev_int_db;
drop database if exists brindle_dev_raw_db;
drop database if exists brindle_prod_anl_db;
drop database if exists brindle_prod_int_db;
drop database if exists brindle_prod_raw_db;
drop database if exists brindle_admin_db;          -- holds the DCM project object
drop warehouse if exists brindle_ingest_wh;
drop warehouse if exists brindle_transform_wh;
drop warehouse if exists brindle_anl_wh;
drop warehouse if exists brindle_deploy_wh;
drop role if exists brindle_bi_rl;
drop role if exists brindle_transform_rl;
drop role if exists brindle_ingest_rl;
drop role if exists brindle_deployer_rl;
```

`snowflake_intelligence` itself stays: it is a Snowflake-required location for agents, not
a project object. Then delete the Sigma workbook and connection. Afterwards, `SHOW DATABASES LIKE
'BRINDLE%'`, `SHOW WAREHOUSES LIKE 'BRINDLE%'`, `SHOW ROLES LIKE 'BRINDLE%'` and
`SHOW USERS LIKE 'BRINDLE%'` should each return nothing.

The `BRINDLE_` prefix is what makes this list safe to run in a shared account. Read it
line by line anyway.
