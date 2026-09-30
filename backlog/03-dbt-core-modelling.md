# Epic 3: dbt core modelling

Stories BF-16 to BF-27, then BF-72 after the macros and BF-73 after the fact. Anchor numbers as at **2024-09-13**: **16,374 passings / 1,316 subscribers / 8.04% penetration**. Business rules and the wrong-number table are in [`docs/BUSINESS_RULES.md`](../docs/BUSINESS_RULES.md). Traps are in [`docs/GOTCHAS.md`](../docs/GOTCHAS.md).

---

### BF-16: dbt project, profile, and PAT authentication
**As a** data engineer **I want** a dbt project that connects to Snowflake unattended **so that** builds do not depend on a human clicking a browser prompt.

**Learning objective:** `dbt_project.yml`, `profiles.yml`, targets, and `dbt debug`. Plus the authentication trap.

**Acceptance criteria**
- [ ] `dbt/dbt_project.yml` exists with project name and a `dev` target.
- [ ] `dbt/profiles.yml` uses a **PAT in the `password:` field**, not `authenticator: externalbrowser`, which hangs on a browser prompt instead of failing, and is useless for anything unattended (GOTCHA M).
- [ ] The PAT is confirmed **not role-restricted**. A restricted PAT fails `USE ROLE` with a confusing permissions error rather than an auth error.
- [ ] `profiles.yml` does not contain a literal secret committed to git.
- [ ] `role` is `brindle_transform_rl`.

**Verification:** `dbt debug` reports **"All checks passed!"** and completes without opening a browser. Then `dbt show --inline "select current_role()"` returns **BRINDLE_TRANSFORM_RL**.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-70 or BF-07

---

### BF-17: Layer config: int as views, anl as tables
**As a** data engineer **I want** layer-level materialization and database config in `dbt_project.yml` **so that** individual models do not each restate their own physical strategy.

**Learning objective:** configuration inheritance and the `models:` hierarchy. Config set at a folder applies to everything beneath it, and per-model config is an exception rather than the norm.

**Acceptance criteria**
- [ ] `models:` config sets `int` to `+materialized: view`, `+database: int` and `+schema: int`.
- [ ] `models:` config sets `anl` to `+materialized: table`, `+database: anl` and `+schema: anl`. Without `+schema`, both layers land in whatever schema the profile names.
- [ ] No individual model file restates a materialization that its folder already sets.
- [ ] A comment explains the reasoning: `int` means integration, cheap disposable transformation logic, while `anl` means analysis, the queryable serving layer that BI and the semantic view hit.

**Verification:** after `dbt build`, `select table_name, table_type from brindle_dev_int_db.information_schema.tables` shows **VIEW** for every `int_` object, and the same query against the anl database shows **BASE TABLE** for every `dim_`/`fct_` object. Check in Snowflake, not in the yml. The incremental model in BF-78 is the exception, and only after that story: it is a table, and the model says why.

**Estimate:** S  ·  **Track:** core  ·  **Depends on:** BF-16

---

### BF-18: Custom `generate_database_name`
**As a** data engineer **I want** a macro mapping the logical database alias to a physical name **so that** `+database: int` resolves to `brindle_dev_int_db` without any model knowing the physical name.

**Learning objective:** overriding dbt's built-in naming macros. dbt's default `generate_database_name` concatenates. Overriding it lets you keep an environment-independent logical alias in the model config.

**Acceptance criteria**
- [ ] `dbt/macros/infrastructure/generate_database_name.sql` maps `int` → `brindle_dev_int_db`, `anl` → `brindle_dev_anl_db`, `raw` → `brindle_dev_raw_db`.
- [ ] The environment segment (`dev`) comes from the target, so a future `prod` target needs no model change.
- [ ] A matching `generate_schema_name.sql` override exists so schemas are not prefixed with the target schema name.
- [ ] No model file mentions a physical database name.

**Verification:** `grep -r 'brindle_dev' dbt/models/` returns **no matches**. `dbt compile`, then inspect any `anl` model in `dbt/target/compiled/`. The fully qualified name reads `brindle_dev_anl_db`.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-17

---

### BF-19: Sources with freshness
**As a** data engineer **I want** the six raw tables declared as dbt sources with a freshness policy **so that** models reference them symbolically and staleness is detectable.

**Learning objective:** `sources`, `source()`, `loaded_at_field`, and freshness thresholds, and the idea that a threshold must be set from the actual sync cadence, not copied from a tutorial.

**Acceptance criteria**
- [ ] `dbt/models/int/_sources.yml` declares all six tables under one source.
- [ ] `loaded_at_field: _fivetran_synced`.
- [ ] Freshness **warns at 48 hours**, with a comment recording why: the sync is daily, so anything tighter is a false alarm and anything looser hides a two-day outage.
- [ ] Each source table has a description.
- [ ] No model uses a hardcoded raw table name. All go through `source()`.

**Verification:** `dbt source freshness` exits with status **pass** or **warn**, never error, on freshly loaded data. `grep -rl 'brindle_dev_raw_db' dbt/models/` returns **nothing**.

**Estimate:** S  ·  **Track:** core  ·  **Depends on:** BF-18, and BF-13 or BF-71

---

### BF-20: Custom utility macros instead of dbt_utils
**As a** data engineer **I want** the four utility macros written from scratch **so that** we control the hashing contract and understand what packages usually hide.

**Learning objective:** macro authoring: arguments, `{% macro %}`, returning SQL fragments, and `{{ }}` invocation inside a model. Writing `surrogate_key` yourself is the fastest way to understand why surrogate keys are fragile.

**Acceptance criteria**
- [ ] `dbt/macros/utils/utils_surrogate_key.sql` builds a **SHA-256** key over an ordered list of columns, with NULLs coalesced to a fixed sentinel so a NULL cannot collide with an empty string.
- [ ] `dbt/macros/utils/utils_change_hash.sql` hashes the attribute set for change detection.
- [ ] `dbt/macros/utils/coalesce_to_unknown.sql` maps both `''` **and** `NULL` to the literal `'N/A'`.
- [ ] `dbt/macros/utils/generate_unknown_record.sql` emits the Unknown dimension row keyed `'0'`.
- [ ] `dbt/packages.yml` does **not** include `dbt_utils` yet, and nothing in the project references it. BF-72 is where the package is allowed, after this macro exists.
- [ ] Each macro has a header comment stating its contract and the collision risk it guards against.

**Verification:** `grep -r dbt_utils dbt/ --include=*.yml --include=*.sql` returns **no matches**. `dbt show --inline` on a select that calls `utils_surrogate_key` once over the literals `'a','b'` and once over `'ab',''` returns **two different** hashes.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-19

---

### BF-72: Compare the hand-written key with `dbt_utils`
**As a** data engineer **I want** `dbt_utils` installed and compared with `utils_surrogate_key` **so that** I know what the package avoids, and when to stop hand-rolling.

**Learning objective:** packages. You wrote the macro so the collision is yours. The package exists so the next project does not re-implement it. The hashes will not match. The collision behavior should.

**Acceptance criteria**
- [ ] `dbt/packages.yml` includes `dbt_utils`, and `dbt deps` has been run.
- [ ] Models still call `utils_surrogate_key`. No model calls `dbt_utils.generate_surrogate_key`.
- [ ] A `dbt show --inline` compares both macros on `('a','b')` and on `('ab','')`.
- [ ] `NOTES.md` records three facts: each macro returns two different values for those two inputs; the two macros do not return the same hash, because yours is SHA-256 and `dbt_utils` is MD5; both close the boundary collision if BF-20 was written correctly.

**Verification:** `dbt show --inline` prints four hashes. The two from your macro differ from each other. The two from `dbt_utils.generate_surrogate_key` differ from each other. Your hash is not the package hash. `grep -n dbt_utils dbt/models` returns **no matches**.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-20

---

### BF-21: `int_location`: parse the date, plant the sentinel
**As a** data engineer **I want** an integration model that parses `in_service_date` and maps blanks to a future sentinel **so that** the passings rule needs no special-case branch.

**Learning objective:** the `int` layer as the cleaning boundary, `ref()` versus `source()`, and sentinel design, meaning choosing a sentinel value that makes a downstream rule do the work for you.

**Acceptance criteria**
- [ ] `dbt/models/int/int_location.sql` reads via `source()`.
- [ ] Blank `in_service_date` (`''`) maps to the sentinel **`'12-31-2030'`** before parsing.
- [ ] The `MM-DD-YYYY` varchar is parsed to a real `DATE`.
- [ ] `address_type`, `structure_type`, `hubsite` go through `coalesce_to_unknown` to the literal `'N/A'`.
- [ ] A comment states the sentinel's purpose: it is in the future, so those rows fail `in_service_date <= as_of_date` **naturally**, rather than needing an exclusion branch.
- [ ] No row is dropped here. Filtering is the fact's job. Cleaning is this model's job.

**Verification:** `select count(*) from int_location` returns **18253** (nothing dropped). `select count(*) from int_location where in_service_date_parsed = '2030-12-31'` returns **1442**. `select count(*) from int_location where address_type = 'N/A'` returns **529**. `select count(*) from int_location where in_service_date_parsed > '2024-09-13' and in_service_date_parsed < '2030-12-31'` returns **437**: real dates that are simply not in service yet.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-72

---

### BF-22: `int_subscriber` and `int_market_hierarchy`
**As a** data engineer **I want** integration models for subscribers and the market hierarchy **so that** the grain change and the hierarchy flattening are explicit, isolated, and testable.

**Learning objective:** grain as a first-class concept, and how `ref()` builds the DAG. The subscriber source is at subscriber-**period** grain and must be reduced to one row per address. *How* you reduce it is where defect A hides, so the aggregation belongs in a named model you can inspect.

**Acceptance criteria**
- [ ] `int_subscriber.sql` aggregates to **one row per `service_address_id`**.
- [ ] It computes `sum(is_active)` so the `>= 1` rule can be applied downstream.
- [ ] It computes **`min(case when is_active = 1 then service_eff_date end) as first_active_service_eff_date`**. This is the column that prevents defect A. See BF-31.
- [ ] It retains `entity` so the GREENFIELD filter can be applied downstream. Entity is constant per address in this source. Prove it with a test rather than assuming it, because if it ever varies, grouping by it silently breaks the grain.
- [ ] `int_market_hierarchy.sql` joins `markets`, `hubsites`, `service_areas`, `pon_zones` into one flattened hierarchy via `source()`.
- [ ] A comment on `first_active_service_eff_date` states explicitly that qualifying on the latest period (`max(service_eff_date)`) instead erases re-signers from the months between a cancelled order and the re-sign.

**Verification:** `select count(*) from int_subscriber` returns **1631**, which is less than the 2,194 source rows and equals `select count(distinct service_address_id) from subscribers`. `dbt ls --select +int_market_hierarchy` lists the four upstream sources, proving the DAG.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-21

---

### BF-23: The `vars:` entry for `report_as_of_date`
**As a** data engineer **I want** the as-of date defined exactly once as a project variable **so that** two models cannot drift to different dates.

**Learning objective:** `vars:`, `{{ var('...') }}`, and single-source-of-truth configuration. Two hardcoded dates in two models is not a bug you find by reading. It is a bug you find six months later.

**Acceptance criteria**
- [ ] `dbt_project.yml` has `vars: report_as_of_date: '2024-09-13'`.
- [ ] Every model needing the date uses `{{ var('report_as_of_date') }}`.
- [ ] The literal `2024-09-13` appears **nowhere** in `dbt/models/`.
- [ ] A comment states the drift failure mode being prevented.

**Verification:** `grep -rn '2024-09-13' dbt/models/ dbt/macros/` returns **no matches**, and the same grep against `dbt/dbt_project.yml` returns **exactly one** line.

**Estimate:** S  ·  **Track:** core  ·  **Depends on:** BF-22

---

### BF-24: `dim_market` with an Unknown member
**As a** data engineer **I want** a market dimension with a union'd Unknown row keyed `'0'` **so that** fact rows with an unresolvable market still join and are visibly attributed to Unknown.

**Learning objective:** the Unknown member pattern. Inner joins silently drop unmatched facts and outer joins silently produce NULL labels. A real Unknown row makes the problem countable instead of invisible.

**Acceptance criteria**
- [ ] `dbt/models/anl/dim_market.sql` builds from `int_market_hierarchy` via `ref()`.
- [ ] `market_key` is a surrogate from `utils_surrogate_key`.
- [ ] An Unknown row keyed **`'0'`** is union'd on via `generate_unknown_record`, with descriptive attributes set to `'N/A'`.
- [ ] The model carries the full seven-block SELECT scaffold: `/* surrogate pk */ /* natural keys */ /* foreign keys */ /* attributes */ /* measures */ /* dates */ /* audit */`.
- [ ] Audit columns record the dbt invocation and load timestamp.

**Verification:** `select count(*) from dim_market` returns **7** (6 markets + Unknown). `select market_name from dim_market where market_key = '0'` returns **'N/A'**.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-23

---

### BF-25: `dim_location` and `dim_date`
**As a** data engineer **I want** location and calendar dimensions **so that** the fact has a calendar to join to, and the calendar owns its own date attributes.

**Learning objective:** conformed dimensions, and why the calendar owns `year_month`, `month_end_date` and `year_number`. The fact carries copies of the first two for convenience, but anything that reasons about time, the semantic view above all, must bind to the calendar's. This sets up GOTCHA C: the fact having a column named `year_month` is exactly what lets an unqualified `NON ADDITIVE BY` bind to the wrong table.

**Acceptance criteria**
- [ ] `dbt/models/anl/dim_date.sql` provides a month-grain calendar from 2021-01 through 2030-12, so every parsed date, the sentinel included, has a calendar row.
- [ ] `dim_date` carries **`year_month`, `month_end_date`, `year_number`**.
- [ ] `dbt/models/anl/dim_location.sql` builds from `int_location`, with a surrogate key and an Unknown row keyed `'0'`.
- [ ] A comment in `dim_location` says who it is for. The monthly fact is at market grain and has **no** location key, so nothing joins to `dim_location` yet. It is the conformed dimension the By PON stretch goal needs, and it is Unknown-member practice at 18,000-row scale.
- [ ] Both models carry the seven-block scaffold.
- [ ] A comment in `dim_date` flags that these three columns are the ones `NON ADDITIVE BY` must reference, **table-qualified**. See BF-40.

**Verification:** `select count(*) from dim_location` returns **18254** (18,253 plus Unknown). `select count(*), min(year_month), max(year_month) from dim_date` returns **120**, `2021-01`, `2030-12`. `select count(*) from dim_date where year_number is null` returns **0**.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-24

---

### BF-26: `fct_passings_subscribers_monthly`
**As a** data engineer **I want** a monthly fact of cumulative passings and subscribers **so that** the report page can be built and reconciled.

**Learning objective:** the point-in-time **balance** fact. `passings` and `subscribers` are cumulative balances, not monthly flows: a month contains all prior months. That determines every aggregation rule downstream, and it is why the semantic view needs `NON ADDITIVE BY`.

**Acceptance criteria**
- [ ] `dbt/models/anl/fct_passings_subscribers_monthly.sql` is at **month × market** grain, with a row for every month from 2021-01 through the report month for all six markets, zero balances included.
- [ ] Each month has an **as-of point**: `least(month_end_date, report_as_of_date)`. For every month but the last that is the month end. For 2024-09 it is 2024-09-13, not 2024-09-30.
- [ ] A location counts as a passing only if its parsed `in_service_date <=` the month's as-of point.
- [ ] A subscriber counts only if its address resolves to a location (orphans are excluded here), `entity = 'GREENFIELD'`, `sum(is_active) >= 1`, deduped to one row per `service_address_id`.
- [ ] Subscribers are qualified into a month on **`first_active_service_eff_date <=` the as-of point**, never on the latest period. See BF-31.
- [ ] **No stored penetration column.** Penetration is `sum(subscribers) / sum(passings)` at query time.
- [ ] FKs to `dim_market` and `dim_date` only. `market_key` defaults to `'0'` when unresolvable. `date_key` always resolves, because the calendar is generated to cover every month, so `dim_date` needs no Unknown row. There is no location key at this grain.
- [ ] Full seven-block scaffold.
- [ ] Uses `{{ var('report_as_of_date') }}`, never a literal.

**Verification:** `select sum(passings), sum(subscribers), round(sum(subscribers)/sum(passings), 4) from fct_passings_subscribers_monthly where year_month = '2024-09'` returns **16374**, **1316**, **0.0804**. `select count(*) from fct_passings_subscribers_monthly` returns **270**. And `select count(*) from information_schema.columns where table_name = 'FCT_PASSINGS_SUBSCRIBERS_MONTHLY' and column_name ilike '%penetration%'` returns **0**. Off by a little? Check the wrong-number table in `docs/BUSINESS_RULES.md` before you start debugging.

**Estimate:** L  ·  **Track:** core  ·  **Depends on:** BF-25

---

### BF-27: `v_by_market_current` presentation view
**As a** data engineer **I want** a view restricting the fact to the reporting month **so that** the month filter is testable in dbt and BI stays presentation-only.

**Learning objective:** pushing filter logic out of the BI tool and into the warehouse. GOTCHA H forces it, since element-level `filters` on a Sigma table element fail validation, but it is the better design regardless, because a filter in dbt can carry a test and a filter in Sigma cannot.

**Acceptance criteria**
- [ ] `dbt/models/anl/v_by_market_current.sql` is materialized as a **view**, overriding the `anl` default.
- [ ] It restricts to the month containing `{{ var('report_as_of_date') }}`.
- [ ] It joins `dim_market` so `market_name` is present and Sigma needs no joins.
- [ ] It exposes `passings` and `subscribers` but **not** a stored penetration column.
- [ ] A comment records that this exists partly because Sigma element-level filters do not validate, and that the benefit is testability.

**Verification:** `select count(*) from v_by_market_current` returns **6** (one row per market, no Unknown row with data). `select sum(passings), sum(subscribers) from v_by_market_current` returns **16374** and **1316**.

**Estimate:** S  ·  **Track:** core  ·  **Depends on:** BF-26

---

### BF-73: Daily dbt build as a Snowflake task
**As a** data engineer **I want** the dbt project deployed in Snowflake and run every day by a task **so that** the pipeline does not depend on someone remembering to type `dbt build`.

**Learning objective:** Snowflake tasks schedule a dbt project object with `EXECUTE DBT PROJECT`. The task has to live in the same database and schema as that object. Read Snowflake docs, *"Schedule execution of dbt project objects"*.

`dbt build` is the command. Tests you add in epic 4 join this task without a second scheduler story.

**Acceptance criteria**
- [ ] The dbt project is deployed as a Snowflake dbt project object `brindle_dev_anl_db.anl.brindle_dbt`.
- [ ] A task in that same database and schema runs the build. It is created suspended, which is the CREATE TASK default.

```sql
CREATE OR ALTER TASK brindle_dev_anl_db.anl.build_brindle_daily
  WAREHOUSE = brindle_transform_wh
  SCHEDULE = 'USING CRON 0 6 * * * America/New_York'
AS
  EXECUTE DBT PROJECT brindle_dev_anl_db.anl.brindle_dbt
    args='build --target dev';
```

- [ ] You run it once with `EXECUTE TASK`, while it is still suspended, and read the result in `TASK_HISTORY`.
- [ ] The fact for 2024-09 is still **16,374 / 1,316** after that run.
- [ ] You `ALTER TASK ... RESUME` only after that proof. `NOTES.md` says you will suspend the task when you stop working. A trial account should not pay for a build every morning.
- [ ] A comment on the task says BF-75 will point `args` at `--target prod` once that target exists.

**Verification:** `INFORMATION_SCHEMA.TASK_HISTORY` (or `SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY`, once it has caught up) shows one run of `BUILD_BRINDLE_DAILY` with state **SUCCEEDED**. Then:

```sql
select sum(passings), sum(subscribers)
from brindle_dev_anl_db.anl.fct_passings_subscribers_monthly
where year_month = '2024-09';
```

returns **16374** and **1316**. `SHOW TASKS LIKE 'BUILD_BRINDLE_DAILY'` shows the task **started** after the resume.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-27, BF-72
