# Epic 4: Testing and data quality

Stories BF-28 to BF-35, then BF-74 beside the defect, and BF-75 and BF-76 once the tests are green. Anchor numbers as at **2024-09-13**: **16,374 passings / 1,316 subscribers / 8.04% penetration**. Business rules and the wrong-number table are in [`docs/BUSINESS_RULES.md`](../docs/BUSINESS_RULES.md). Traps are in [`docs/GOTCHAS.md`](../docs/GOTCHAS.md).

---

### BF-28: Generic tests on keys and relationships
**As a** data engineer **I want** `unique`, `not_null`, `relationships`, and `accepted_values` declared in schema yml **so that** structural breakage fails the build instead of reaching the report.

**Learning objective:** dbt's four built-in generic tests, how they are declared in `_schema.yml`, and how `relationships` differs from a database foreign key: it is enforced at build time on the modelled data, not at write time.

**Acceptance criteria**
- [ ] `unique` and `not_null` on every dimension surrogate key.
- [ ] `not_null` on every fact FK and measure.
- [ ] `relationships` from each fact FK to its dimension key.
- [ ] `accepted_values` on the cleaned categorical columns, **including `'N/A'`** in the allowed list. It is a real value here, not an absence.
- [ ] Tests live in `dbt/models/anl/_schema.yml` and `dbt/models/int/_schema.yml`, not in ad-hoc singular tests.

**Verification:** `dbt test --select test_type:generic` or `dbt build` is green. Then temporarily remove `'N/A'` from one `accepted_values` list and confirm the test **fails** with a non-zero row count, proving it is actually evaluating.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-73

---

### BF-29: Custom generic test: `unknown_rate`
**As a** data engineer **I want** a reusable generic test asserting the share of Unknown-keyed rows stays under a threshold **so that** a degrading join surfaces as a failure rather than a slowly growing Unknown bucket.

**Learning objective:** authoring a **custom generic test**: `{% test %}`, the `model` and `column_name` context variables, and passing configuration arguments such as a threshold.

**Acceptance criteria**
- [ ] `dbt/tests/generic/test_unknown_rate.sql` defines a `test` block taking a threshold argument.
- [ ] It returns failing rows when the proportion of rows whose column equals `'0'` (or `'N/A'`) exceeds the threshold.
- [ ] The default threshold is **5%**, overridable per use.
- [ ] The test returns rows on failure and zero rows on pass, per dbt's contract.
- [ ] A header comment states where the test belongs (fact FK edges) and where it does not. See BF-30.

**Verification:** applied to a fact FK on correct data, `dbt test --select "test_name:unknown_rate"` passes with **0** failing rows. Set the threshold to `0.0` and confirm it then fails, proving the arithmetic works in both directions.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-28

---

### BF-30: Place `unknown_rate` on fact FK edges, not dimension keys
**As a** data engineer **I want** `unknown_rate` applied to the fact's FK columns **so that** it measures unresolved joins rather than the existence of the Unknown member itself.

**Learning objective:** a test must be placed where the defect would actually appear. This is defect B, and it is a subtle category error rather than a coding mistake.

**Acceptance criteria**
- [ ] `unknown_rate` is applied to `fct_passings_subscribers_monthly`'s FK columns, `market_key` and `date_key`.
- [ ] It is applied to **no** dimension key column.
- [ ] A comment records defect B: it was originally on `dim_market.market_key`. `dim_market` has 6 markets plus 1 Unknown row, so 1/7 = **14.3%**, over the 5% threshold. It failed **by construction**, and would on any small dimension.
- [ ] The comment generalises the lesson: the Unknown member is a designed row in a dimension, so its presence there is expected. On a fact FK it means a join did not resolve.

**Verification:** `grep -n unknown_rate dbt/models/anl/_schema.yml` shows the test only under the fact's columns. `dbt test --select fct_passings_subscribers_monthly` passes, and on correct data the unknown rate on each FK is **0%**, not merely under 5%.

**Estimate:** S  ·  **Track:** core  ·  **Depends on:** BF-29

---

### BF-31: Make it fail on purpose: reintroduce the subscriber-balance defect
**As a** data engineer **I want** to reintroduce defect A and watch the monotonicity test catch it **so that** I learn in my bones that a correct total does not imply a correct series.

**Learning objective:** invariant testing versus endpoint checking. **This is the single most valuable story in the project.** Do it even if you skip others.

**The defect.** Instead of qualifying on `first_active_service_eff_date`, the fact picks each address's *current* record for the month, meaning its latest period on or before the as-of point (`max(service_eff_date)`), and counts the address only if that period is active. It looks like sensible "current status" logic. It breaks business rule 3. In March 2022 a billing migration cancelled a batch of orders, and those customers re-signed months later. Under the defect they vanish from every month in between. Because every one of them had re-signed by September 2024, the report month is untouched.

**Acceptance criteria**
- [ ] A singular test `dbt/tests/assert_balances_are_non_decreasing.sql` asserts that for each market, `passings` and `subscribers` never decrease month over month, because they are cumulative balances.
- [ ] The test passes on the corrected fact.
- [ ] You **deliberately** switch the fact to the current-record logic above, and rebuild.
- [ ] You confirm the headline reconciliation is **still correct**, 16,374 / 1,316 / 8.04%, because the defect is invisible at the final month, which is exactly where the reconciliation was being checked.
- [ ] You confirm `dbt build` would have been **green** without this test.
- [ ] You confirm the monotonicity test now **fails**, and record the failing row count.
- [ ] You confirm the historic damage: **2022-03 reads 21 instead of 56** (−62%) and **2022-12 reads 196 instead of 220** (−11%).
- [ ] You revert to the correct version and confirm the test passes again.
- [ ] A note in `NOTES.md` states the lesson: test the invariant, not the endpoint.

**Verification:** with the defect in place, `dbt test --select assert_balances_are_non_decreasing` **fails** (5 rows in the reference build), while `select sum(subscribers) from fct_passings_subscribers_monthly where year_month = '2024-09'` still returns **1316**. Querying 2022-03 returns **21** with the defect and **56** without. After reverting, the test passes and 2022-12 returns **220**, not 196.

**Then sit with this.** A different bug, using `max(service_eff_date)` over *all* periods as a fixed start date, also undercounts history, yet it keeps every series non-decreasing. This test would not catch it. An invariant only catches the defects that violate it. The month-by-month comparison against a hand-written source query in BF-53 is what catches that one, which is why BF-53 compares all 270 rows and not just the last six.

**Estimate:** L  ·  **Track:** core  ·  **Depends on:** BF-30

---

### BF-74: Unit test the re-sign on `int_subscriber`
**As a** data engineer **I want** a dbt unit test with a few fixture rows **so that** the grain change fails before it ever reaches the fact.

**Learning objective:** a unit test answers "given these rows, does this model do what I think?" A singular test answers "does the warehouse violate this rule?" You want both. This one is the small version of defect A.

**Acceptance criteria**
- [ ] A unit test on `int_subscriber`, in the model's YAML, with one address and three periods: installed `2022-02-01`, cancelled `2022-03-15`, installed again `2022-06-01`.
- [ ] The expected row has `first_active_service_eff_date = 2022-02-01`.
- [ ] `dbt test --select int_subscriber` passes.
- [ ] You replace the `min(case when is_active = 1 ...)` with `max(case when is_active = 1 then service_eff_date end)`, rebuild the test, and it **fails** because the fixture now starts at `2022-06-01`.
- [ ] You revert the model. The test passes again.

**Verification:** with the `max` swap in place, `dbt test --select int_subscriber` fails on that unit test. After the revert it passes, and `first_active_service_eff_date` for a real re-signer is still the earlier date. dbt 1.8 or newer is required. SETUP already asks for that.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-31

---

### BF-32: Singular test: grain uniqueness
**As a** data engineer **I want** a singular test asserting one fact row per month and market **so that** a fan-out from a bad join fails the build instead of quietly doubling the numbers.

**Learning objective:** singular tests (a plain SQL file in `tests/` that passes when it returns zero rows), and why declared grain deserves an explicit assertion rather than being left implicit.

**Acceptance criteria**
- [ ] `dbt/tests/assert_fact_grain_is_month_market.sql` returns groups where the count exceeds 1.
- [ ] It passes on the correct fact.
- [ ] A comment states the declared grain in words, so a future reader knows what the test is defending.
- [ ] The failure mode is named: a join fan-out inflates every measure proportionally, so it looks like growth rather than a bug.

**Verification:** `dbt test --select assert_fact_grain_is_month_market` passes with **0** rows. Then temporarily duplicate the fact via a self-union and confirm it fails with **270** rows, one per month-market pair.

**Estimate:** S  ·  **Track:** core  ·  **Depends on:** BF-31

---

### BF-33: Singular tests: attributability and ratio-of-sums
**As a** data engineer **I want** tests asserting subscribers are attributable to a market, and that penetration is a ratio of sums **so that** the two remaining business rules are enforced rather than merely documented.

**Learning objective:** encoding a business rule as a test. Business rule 4, penetration is a ratio of sums and never stored per row, is the kind of rule a well-meaning future change breaks, so it needs a guard.

**Acceptance criteria**
- [ ] `dbt/tests/assert_subscribers_attributable_to_market.sql` returns any fact row where `market_key = '0'` and `subscribers > 0`. Orphans are excluded before the fact by the location join (business rule 3), so this passes with **0** rows.
- [ ] The exclusion is **measured and written down**, not assumed. 12 orphan addresses exist (BF-15). 11 of them are active GREENFIELD addresses that would have counted, so a leak shows up as 1,327 subscribers instead of 1,316.
- [ ] `dbt/tests/assert_penetration_is_ratio_of_sums.sql` fails if a per-row penetration column exists on the fact or on `v_by_market_current`. Averaging done further downstream is caught by BF-42 and BF-45, not here.
- [ ] A comment explains the weighting error: averaging per-market ratios weights a 1,559-passing market the same as a 4,258-passing one.

**Verification:** both tests pass with **0** rows. Separately, confirm the two numbers differ: `sum(subscribers)/sum(passings)` for 2024-09 returns **0.0804**, while `avg(subscribers/passings)` over the six markets returns **0.0870**. Record both.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-32

---

### BF-34: Snapshot `locations_passed` with `strategy='check'`
**As a** data engineer **I want** a dbt snapshot capturing changes to the source table **so that** we rebuild the history the nightly-restored source cannot carry.

**Learning objective:** `dbt snapshot`, SCD2 in dbt, and `strategy='check'` versus `strategy='timestamp'`. `check` is required here because the source has no trustworthy updated-at column, and the nightly restore would reset one anyway.

**Acceptance criteria**
- [ ] `dbt/snapshots/snp_locations_passed.sql` uses `strategy='check'` with an explicit `check_cols` list.
- [ ] `unique_key` is the location's natural key.
- [ ] A comment links to the BF-12 decision record: full-table sync plus snapshot, because CDC is impossible under nightly restore.
- [ ] `utils_change_hash` is used for change detection if `check_cols` is hash-based.
- [ ] `dbt snapshot` run twice on unchanged data produces **no** new rows.

**Verification:** `dbt snapshot`, note `select count(*) from snp_locations_passed`. Run `dbt snapshot` again with no source change: the count is **unchanged** and all rows still have `dbt_valid_to is null`. Change one row in the raw table (AWS track: in Postgres, then reload), snapshot again: exactly **one** row gains a non-null `dbt_valid_to` and exactly one new row appears.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-33

---

### BF-35: Source freshness as an operational check
**As a** data engineer **I want** `dbt source freshness` wired in as a check I actually run **so that** a stalled sync is detected before the report is wrong.

**Learning objective:** freshness as an operational signal distinct from a data test, and calibrating a warn threshold to the real sync cadence rather than to a default.

**Acceptance criteria**
- [ ] `dbt source freshness` runs against all six sources.
- [ ] The 48h warn threshold from BF-19 is confirmed to behave as intended. It **warns**, and does not error.
- [ ] A short runbook note in `docs/` states what to do on a warn: check the Fivetran sync (or the loader), do not rebuild on stale data.
- [ ] The distinction is written down: freshness failing means ingestion is broken, and a test failing means the model is wrong. They have different owners and different fixes.

**Verification:** immediately after a load, `dbt source freshness` reports **pass** for all six. Then artificially set `_fivetran_synced` back by 60 hours on one table and confirm it reports **warn** for that table only, and the process exit does not fail the build.

**Estimate:** S  ·  **Track:** core  ·  **Depends on:** BF-34

---

### BF-75: A `prod` target
**As a** data engineer **I want** a second dbt target that builds `brindle_prod_*` databases **so that** `generate_database_name` is exercised instead of merely written.

**Learning objective:** the environment segment comes from the target. Models do not change between dev and prod. The macro you wrote in BF-18 is the whole mechanism.

**Acceptance criteria**
- [ ] `profiles.yml` has a `prod` output. Same role and warehouse. `target` stays `dev` as the default.
- [ ] `generate_database_name` takes the environment from `target.name`, so prod resolves to `brindle_prod_raw_db`, `brindle_prod_int_db`, and `brindle_prod_anl_db`.
- [ ] Those three databases exist before the build. Create them in SQL. A second DCM environment is not required.
- [ ] `dbt build --target prod` succeeds.
- [ ] The dev fact is untouched: dev 2024-09 is still 16,374 / 1,316.
- [ ] The BF-73 task `args` now say `build --target prod`, and the dbt project object is redeployed so the task can see that target. One `EXECUTE TASK` succeeds against prod.

**Verification:** `select sum(passings), sum(subscribers) from brindle_prod_anl_db.anl.fct_passings_subscribers_monthly where year_month = '2024-09'` returns **16374**, **1316**. The same query on `brindle_dev_anl_db` returns the same pair. `grep -r brindle_prod dbt/models` returns **no matches**.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-35, BF-73

---

### BF-76: Build only what changed
**As a** data engineer **I want** a state selection against the prod manifest **so that** a one-model change does not rebuild the project.

**Learning objective:** `state:modified+` and `--defer`. CI compares your project to a saved manifest and runs the changed node plus its downstream. Defer means unchanged parents are read from prod instead of rebuilt in dev.

**Acceptance criteria**
- [ ] After BF-75, `dbt compile --target prod` (or the prod build) manifest is copied to `dbt/prod-manifest/manifest.json`. That directory is gitignored.
- [ ] You change one model, something a state diff can see, and run:

```bash
dbt build --select state:modified+ --defer --state prod-manifest --target dev
```

- [ ] `NOTES.md` lists the nodes that ran, and names one node that did not.
- [ ] `.github/workflows/dbt-ci.yml` runs that command on pull request. `SNOWFLAKE_PAT` comes from a GitHub secret. The file contains no token. You run the command locally until you have a CI account. This repo does not store Snowflake credentials.
- [ ] The workflow `working-directory` is `dbt`, and it runs `dbt deps` before the build.

**Verification:** the command exits 0, the note lists fewer nodes than `dbt ls --select brindle`, and `git check-ignore dbt/prod-manifest/manifest.json` prints that path. `grep -n SNOWFLAKE_PAT .github/workflows/dbt-ci.yml` shows the secret reference and no literal token.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-75
