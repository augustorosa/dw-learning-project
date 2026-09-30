# Project plan

Seven phases. Each one ends somewhere you could put the project down for a week, with a
milestone you can check rather than feel. The business rules and numbers live in
[`BUSINESS_RULES.md`](BUSINESS_RULES.md). The traps named by letter live in
[`GOTCHAS.md`](GOTCHAS.md).

## Phase overview

| Phase | Epics | Stories | Milestone | Core effort |
| --- | --- | --- | --- | --- |
| 0. Foundations | 1 | BF-01, then BF-70 or the platform track BF-03 to BF-08 | Three databases and `brindle_transform_rl` exist. Platform track: `snow dcm plan` is clean and RBAC is proven by a negative test | ~1.5 days, or ~5 if you take the platform track |
| 1. Source and ingestion | 2 | Option A: BF-13 or BF-71. Option B: BF-02, BF-09, BF-10, BF-14. Shared: BF-11, BF-12, BF-15 | 21,075 rows in `raw` with the 1,442 blanks intact | ~3 days |
| 2. dbt core modelling | 3 | BF-16 to BF-27, BF-72, BF-73 | The fact returns 16,374 / 1,316 / 8.04%, and one Snowflake task has built it | ~13 days |
| 3. Testing and data quality | 4 | BF-28 to BF-35, BF-74 to BF-76 | Defect A is caught, the unit test fails when `min` becomes `max`, and prod plus `state:modified+` have been run | ~10.5 days |
| 4. Docs and semantic layer | 5, 6 | BF-36 to BF-42 | The semantic view returns the anchor numbers and resists both aggregation traps | ~6 days |
| 5. Optional tracks | 7, 8, 10, 11 | BF-43 to BF-52, BF-58 to BF-69, BF-77 to BF-81 | The agent passes its evals, the Sigma export matches, capex per passing reconciles at $1,422.22, and the three Kimball patterns have counts | 3.5 + 5.5 + 16.5 + 1.5 days |
| 6. Verification and handoff | 9 | BF-53 to BF-57 | Every surface agrees, month by month, after a rebuild from empty | ~5 days |

Option B (Fivetran) adds about three days and needs AWS. The platform track adds about
four days on top of BF-01 and replaces BF-70. Effort uses S = half a day, M = one day,
L = two days. The core track totals about 40 working days, so plan on eight weeks full
time, or about four months at two days a week.

---

## Phase 0: Foundations

**Stories:** BF-01, and either BF-70 or BF-03 to BF-08. **Depends on:** nothing.

**Goal.** An account you can load. The plain path is one warehouse, three databases, and
`brindle_transform_rl`. The platform track is DCM, fully declared warehouses, and a
negative RBAC test. Do one.

**Watch for.** Four gotchas live here, and three of them look like something other than
their cause: D (DCM needs the deployer role to own itself), E (undeclared warehouse
properties silently revert), F (`AGENT` and `USER` are not DCM entities), and on the AWS
track L (subnet groups need two AZs).

**Definition of done**

- [ ] Plain path: `SHOW DATABASES LIKE 'BRINDLE_DEV%'` returns the raw, int, and anl
      databases, and `brindle_transform_rl` can use `brindle_transform_wh`.
- [ ] Platform track, if you took it: `snow dcm plan` exits 0, `SHOW DATABASES LIKE 'BRINDLE%'`
      returns those three plus `brindle_admin_db`, every warehouse declares
      `enable_query_acceleration`, and `brindle_bi_rl` **cannot** read raw (BF-08).
- [ ] Every object the project creates is `BRINDLE_`-prefixed.

## Phase 1: Source and ingestion

**Stories:** BF-11, BF-12, BF-15, plus option A (BF-13 or BF-71) or option B (BF-02, BF-09,
BF-10, BF-14). **Depends on:** Phase 0.

**Goal.** Six tables, 21,075 rows, in `brindle_dev_raw_db.raw`, in exactly the shape a
Fivetran full-table sync would produce, so that swapping paths changes nothing downstream.

**Decisions to internalise.** The source in this scenario is restored nightly from
backup, which rules out CDC (GOTCHA N), so ingestion is a daily full-table sync plus a dbt
snapshot. And `empty_field_as_null = false` is load-bearing: `''` versus NULL is the whole
data-quality signal in this dataset.

**Definition of done**

- [ ] `python data/generate_data.py --check` passes.
- [ ] Landing row counts are exactly `markets` 6, `hubsites` 12, `service_areas` 30,
      `pon_zones` 580, `locations_passed` 18,253, `subscribers` 2,194.
- [ ] `select count(*) from locations_passed where in_service_date = ''` returns **1,442**
      in Snowflake. Not 0.
- [ ] Every raw table has `_fivetran_synced` and `_fivetran_deleted`.
- [ ] The ingestion decision record exists and names the nightly restore as the reason
      CDC was rejected.
- [ ] The data profile (BF-15) is in `NOTES.md`, with the query behind each number.
- [ ] AWS track: `psql` connects to RDS and reports PostgreSQL 16.x, pinned rather than
      defaulted.

## Phase 2: dbt core modelling

**Stories:** BF-16 to BF-27, BF-72, BF-73. **Depends on:** Phases 0 and 1.

**Goal.** The `int` layer integrates, the `anl` layer is analysis, the fact reconciles
to the anchor numbers, and a Snowflake task can build it.

**The order concepts land in.** Project and profile, then layer config, then
`generate_database_name`, then sources with freshness, then hand-written macros, then
the `dbt_utils` comparison, then the `int` models with `ref()`, then `vars:`, then
dimensions with an Unknown member, then the fact, then the presentation view, then the
daily task. [`LEARNING_PATH.md`](LEARNING_PATH.md) walks through why.

**The SELECT scaffold.** Every `anl` model carries these seven comment blocks, in this
order. It makes a long model reviewable at a glance, and it makes an absence visible.

```
/* surrogate pk */  /* natural keys */  /* foreign keys */
/* attributes */    /* measures */      /* dates */        /* audit */
```

**Definition of done**

- [ ] `dbt build` is green.
- [ ] Core `int` models are views in `brindle_dev_int_db`, and `anl` models are tables
      in `brindle_dev_anl_db`, confirmed in `information_schema`, not in the yml.
      `v_by_market_current` is a view on purpose. `int_service_event` is incremental,
      and only if you did that track.
- [ ] The fact for 2024-09 returns **16,374 / 1,316 / 8.04%**, and has 270 rows.
- [ ] Penetration is not a stored column anywhere.
- [ ] `2024-09-13` appears exactly once across `dbt/models`, `dbt/macros` and
      `dbt_project.yml`, in `vars:`.
- [ ] `dim_market` and `dim_location` have an Unknown member keyed `'0'`. `dim_date` is a
      generated calendar, so every date resolves and it needs none.
- [ ] Every `anl` model has the seven-block scaffold.
- [ ] Models call `utils_surrogate_key`. `packages.yml` contains `dbt_utils`, and the
      BF-72 note records that the hashes differ and the collision behavior agrees.
- [ ] `BUILD_BRINDLE_DAILY` has one succeeded run, and the task is resumed only after that.

## Phase 3: Testing and data quality

**Stories:** BF-28 to BF-35, BF-74, BF-75, BF-76. **Depends on:** Phase 2.

**Goal.** Tests that would have caught the bugs the reference build actually shipped. Not
coverage for its own sake.

**The centre of the phase** is BF-31. You reintroduce defect A, confirm the report month
is still exactly right, and watch the monotonicity test fail. BF-30 is the quieter lesson:
a test hung on the wrong column (defect B) is not a weak test, it is a meaningless one.

**Definition of done**

- [ ] `dbt test` is green on the corrected models.
- [ ] `unknown_rate` sits on the fact's FK columns and on no dimension key.
- [ ] The monotonicity test demonstrably fails with defect A in place, and the failing
      row count is recorded.
- [ ] A singular test fails if a per-row penetration column is reintroduced.
- [ ] `dbt snapshot` runs twice on unchanged data with no new rows the second time.
- [ ] `dbt source freshness` warns, rather than errors, past 48 hours.
- [ ] The `int_subscriber` unit test fails when `first_active_service_eff_date` is a `max`.
- [ ] `dbt build --target prod` returns the anchor numbers from `brindle_prod_anl_db`.
- [ ] `state:modified+` with `--defer` runs a subset, and the workflow file has no token.

## Phase 4: Docs and semantic layer

**Stories:** BF-36 to BF-42. **Depends on:** Phase 3.

**Goal.** Descriptions in Snowflake, a docs site, and a semantic view that returns the
anchor numbers and refuses the two aggregation traps.

**Why docs come first.** `persist_docs` writes dbt descriptions into Snowflake comments,
and those comments are what an agent reads. A wrong description is a correctness bug with
a delayed symptom. And the fact has to be right before it is described.

**Definition of done**

- [ ] `dbt docs generate` succeeds and the DAG has no surprises.
- [ ] Column comments are present in `information_schema.columns` for the fact and every
      dimension.
- [ ] `NON ADDITIVE BY` is fully table-qualified (GOTCHA C).
- [ ] A semantic view query for 2024-09 returns **16,374 / 1,316 / 8.04%**.
- [ ] A three-month aggregate of subscribers returns 1,316, not 3,062, and total
      penetration returns 8.04%, not 8.70%.

## Phase 5: Optional tracks

**Stories:** BF-43 to BF-46 (agent), BF-47 to BF-52 (Sigma), BF-58 to BF-69 (NetSuite).
**Depends on:** Phase 4 for the agent, Phase 2 for Sigma (BF-47 needs only
`v_by_market_current`), Phase 3 for NetSuite (its last story, BF-69, also needs Phase 4).

**Agent.** Built imperatively from `snowflake/bootstrap/` because of GOTCHA F, evaluated
against two deliberate traps (summing a balance, averaging a ratio) and one question it
must decline.

**Sigma.** Budget for it. Four of the fourteen gotchas live here (G, H, I, J), and the
worst of them, G, returns `{"valid": true}` for a workbook that renders nothing.

**NetSuite.** A second source, vendor bills and payments from the ERP, modelled against
the dimensions you already have. It teaches allocation across a many-to-many, a
conservation test, and drill-across between two facts. Five planted traps (O to S) are
worth reading before you start.

**Definition of done**

- [ ] Agent: all four evals pass, with numbers, not descriptions.
- [ ] Sigma: the workbook renders real values, proven by **exporting** its data, and
      column references are table-prefixed throughout.
- [ ] NetSuite: capex paid to date is $23,287,443.42 as at 2024-09-13, reproduced by a
      hand-written query over raw, and capex per passing is $1,422.22. The
      conservation test passes, and fails when the fan-out is put back.
- [ ] NetSuite, if you continued: `dim_vendor` has 14 rows after the rename, `fct_ap_bill`
      has 2,320 rows, and `sum(cash_paid)` is $23,287,443.42.

## Phase 6: Verification and handoff

**Stories:** BF-53 to BF-57. **Depends on:** Phase 4, plus Phase 5 for whatever you built.

**Goal.** Every surface agrees, the stack rebuilds from empty, and the handoff is honest.

**Definition of done**

- [ ] The reconciliation record lists every surface, the query used on each, and the
      value returned. All read 16,374 / 1,316 / 8.04%.
- [ ] A hand-written source query matches the fact on all 270 month-market rows.
- [ ] A full teardown and rebuild produces identical numbers.
- [ ] Teardown leaves no `BRINDLE`-prefixed object behind.
- [ ] Your notes list every shortcut and any story you could not verify.

---

## Dependency map

```
Phase 0  Foundations
   |
Phase 1  Source and ingestion
   |
Phase 2  dbt modelling -------------------------------------------------.
   |                                                                    |
Phase 3  Testing -----------------------------------.                   |
   |                                                |                   |
Phase 4  Docs  ->  Semantic view                    |                   |
   |                    |                           |                   |
   |              Phase 5a  Agent       Phase 5c  NetSuite    Phase 5b  Sigma
   |                    |                           |                   |
Phase 6  Reconciliation, rebuild, runbook, teardown, handoff <----------'
```

Hard sequencing constraints, as opposed to merely sensible ones:

- **The RBAC negative test before anything reads raw.** Otherwise you do not know
  whether `brindle_bi_rl` is correctly scoped or just untested.
- **A correct fact before docs.** A description of a wrong measure is worse than none.
- **Testing before the semantic view.** The view inherits the fact's defects and makes
  them harder to see.
- **Docs before the agent.** `persist_docs` output is the agent's grounding.
- **`v_by_market_current` before the Sigma workbook.** Because of GOTCHA H, the month
  filter lives in dbt, not in Sigma.

## Stretch goals

Not in the stories. Roughly in order of value. A prod dbt target is BF-75, not a stretch.
DCM-in-CI is still a stretch. It is not the dbt state selection in BF-76.

1. **Cohort and vintage grain.** The full report is "Cohort Performance": cohorts by
   in-service vintage, which this rebuild flattens away. Add a vintage dimension and
   re-grain the fact. This is where balance versus flow gets hard, because a cohort's
   balance and a market's balance answer different questions.
2. **The By PON page.** A second page at PON-zone grain, 580 zones, using `dim_location`.
   It tests whether your dimensions are truly conformed or merely happen to work at
   market grain.
3. **CI on the DCM plan.** Run `snow dcm plan` on every pull request and fail on an
   unexpected diff. This is the real answer to GOTCHA E: a silent property revert is only
   invisible if nobody is diffing.
4. **Wire up Fivetran for real.** BF-14 specifies it. The reference build never ran it.
5. **Model churn.** The passings fact holds balances only, so it cannot answer churn.
   BF-77 lands the events. It does not prove that the running total of activations
   reconciles to the balance fact. That reconciliation is still open.
6. **Vendor credits and accruals.** NetSuite track only. Add `VendCred` transactions that
   reduce what is owed, and a second view of capex on an accrual basis (by bill date) next
   to the cash basis. Explain to a finance reader, in two sentences, why the two
   differ.
