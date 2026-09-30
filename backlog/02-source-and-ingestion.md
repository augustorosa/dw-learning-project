# Epic 2: Source and ingestion

Stories BF-70, then BF-09 to BF-15, plus BF-71. Anchor numbers as at **2024-09-13**: **16,374 passings / 1,316 subscribers / 8.04% penetration**. Business rules and the wrong-number table are in [`docs/BUSINESS_RULES.md`](../docs/BUSINESS_RULES.md). Traps are in [`docs/GOTCHAS.md`](../docs/GOTCHAS.md).

Two ways into the same raw contract. Epic 3 does not branch.

**Option A.** Do BF-13 (CSV) or BF-71 (SQL inserts inside Snowflake). One of them. Both must leave six tables in `brindle_dev_raw_db.raw`, the same row counts, `''` still `''`, and `_fivetran_synced` / `_fivetran_deleted` on every table.

**Option B.** Fivetran. BF-02, BF-09, BF-10, then BF-14. The connector lands in the same schema. `dbt build` still needs no model change.

BF-11, BF-12, and BF-15 are shared. BF-12 still rules out CDC for this source. The passings tables stay a full refresh even if you later do the incremental track.

---

### BF-70: Plain SQL account
**As a** data engineer **I want** the three databases, the raw schema, one warehouse, and one transform role **so that** I can load and model without the DCM project.

**Learning objective:** the minimum account the rest of the core track actually needs. DCM and two-plane RBAC are the platform track (BF-03 to BF-08). They are worth doing. They are not a gate.

**Acceptance criteria**
- [ ] If BF-07 already ran, you skip this story. Write that down in `NOTES.md` and move on.
- [ ] Otherwise `snowflake/bootstrap/plain_account.sql` has been run as `ACCOUNTADMIN`.
- [ ] It creates `brindle_transform_wh` (XSMALL, 60-second auto-suspend), `brindle_dev_raw_db`, `brindle_dev_int_db`, `brindle_dev_anl_db`, schema `brindle_dev_raw_db.raw`, and role `brindle_transform_rl`.
- [ ] The role owns `raw`, can create schemas in the int and anl databases, and can use the warehouse. Your user is granted the role.
- [ ] You replace `<your_user>` in the script before you run it. The username is not committed.

**Verification:** `SHOW DATABASES LIKE 'BRINDLE_DEV%'` returns **3** rows. `USE ROLE brindle_transform_rl;` then `SELECT CURRENT_ROLE()` returns **BRINDLE_TRANSFORM_RL**. `SHOW SCHEMAS IN DATABASE brindle_dev_raw_db` includes **RAW**.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-01

---

### BF-09: Provision RDS Postgres with a pinned engine version
**As a** data engineer **I want** an RDS Postgres instance at a pinned version **so that** Fivetran compatibility is not decided by whatever RDS happens to default to.

**Learning objective:** pin versions on managed services. Defaults move, and they move without telling you.

**Acceptance criteria**
- [ ] `aws/provision.sh` creates the instance with `--engine-version` **explicitly set to 16.11**, matching the source system's version.
- [ ] A comment records GOTCHA K: omitting `--engine-version` gave the reference build Postgres 18.3, which risks Fivetran incompatibility.
- [ ] `--no-multi-az` for cost, using the two-AZ subnet group from BF-02.
- [ ] Credentials are written to `aws/.brindle-pg-credentials`, which is gitignored.
- [ ] `aws/teardown.sh` removes instance, subnet group, and security group in dependency order.

**Verification:** `psql -c "select version()"` reports **PostgreSQL 16.11**, not 18.x.

**Estimate:** M  ·  **Track:** aws  ·  **Depends on:** BF-02

---

### BF-10: Load the source into Postgres
**As a** data engineer **I want** the six source tables created and loaded in RDS **so that** the raw load has a real operational database to read from.

**Learning objective:** faithful source modelling. The source's bad types are part of the specification, not something to fix upstream. You are given the DDL. The job is to understand why it is shaped the way it is.

**Acceptance criteria**
- [ ] You have read `postgres/ddl.sql` and can explain each deliberate ugliness in `NOTES.md`. `in_service_date` is `VARCHAR` holding `MM-DD-YYYY`. `address_type`, `structure_type` and `hubsite` hold empty strings. `subscribers` is at subscriber-**period** grain with no unique constraint on `service_address_id`. There is no foreign key from `subscribers` to `locations_passed`, because orphans must load.
- [ ] `postgres/load_postgres.sh` has been run against your instance.
- [ ] You can explain the `null '\N'` option on `\copy`. Without it, Postgres reads an unquoted empty CSV field as NULL and the blanks are gone before Snowflake ever sees them.

**Verification:** the script's own check prints 6, 12, 30, 580, 18253, 2194 and **1442** blank dates. `\d brindle_src.locations_passed` shows `in_service_date` as `character varying`, and `\d brindle_src.subscribers` shows **no** unique constraint on `service_address_id`.

**Estimate:** S  ·  **Track:** aws  ·  **Depends on:** BF-09

---

### BF-11: Reproducible synthetic data
**As a** data engineer **I want** to understand how the provided generator guarantees identical data on every machine **so that** the anchor numbers are assertions rather than anecdotes.

**Learning objective:** determinism in test data. Without a fixed seed, "16,374" is an anecdote. And a fixed seed is not enough on its own: libraries like Faker change their output between releases, so `data/generate_data.py` uses only the standard library `random` module, seeded with 42.

**Acceptance criteria**
- [ ] You have read the header of `data/generate_data.py` and the `N_*` constants, and can say which planted count drives which business rule.
- [ ] Row counts are exactly: `markets` 6, `hubsites` 12, `service_areas` 30, `pon_zones` 580, `locations_passed` 18,253, `subscribers` 2,194 (21,075 in total).
- [ ] Blanks are exactly: `in_service_date` 1,442 (empty string, **not** NULL), `address_type` 529, `structure_type` 505, `hubsite` 575.
- [ ] 437 locations have a real `in_service_date` **after** 2024-09-13. They exist so the as-of cutoff actually excludes something (37 of them fall between 14 and 30 September 2024).
- [ ] The profile the script prints is pasted into `NOTES.md`.

**Verification:** `python data/generate_data.py --check` prints `OK: data/csv matches the generator`. Delete `data/csv/`, regenerate, and `--check` still passes.

**Estimate:** S  ·  **Track:** core  ·  **Depends on:** BF-01

---

### BF-12: Decision record: why full-table sync, not CDC
**As a** data engineer **I want** the ingestion-strategy decision written down **so that** the next person does not "improve" it into CDC and break it.

**Learning objective:** ingestion strategy is dictated by source operational reality, not preference, and the reasoning must survive the person who had it.

**Acceptance criteria**
- [ ] A decision record in `docs/` states the source is **restored nightly from backup**.
- [ ] It explains the consequences: a restore destroys replication slots and resets LSNs, and `xmin` / `ctid` are not stable across it.
- [ ] It concludes: daily **full-table** sync, plus a dbt snapshot to rebuild the history the source no longer carries.
- [ ] It names the snapshot as a hard dependency of this choice, linking forward to BF-34.
- [ ] It states the freshness implication: warn at 48h, because a daily sync makes anything tighter a false alarm.

**Verification:** the record exists and answers, in writing, "why not CDC?" and "what replaces the history we lose?". A reviewer who has not seen the project can restate both.

**Estimate:** S  ·  **Track:** core  ·  **Depends on:** BF-11

---

### BF-13: Raw load from CSV, reproducing the Fivetran contract
**As a** data engineer **I want** the source loaded from CSV in exactly the shape Fivetran would produce **so that** swapping in the real connector later changes nothing downstream.

**Learning objective:** contract-first ingestion. Standing in for a tool means matching its output contract, not just moving the rows. And one file-format option decides whether this project has anything to teach.

This is option A, CSV path. BF-71 is the other option A path. Do one of them.

**Acceptance criteria**
- [ ] `snowflake/raw/load_raw_from_csv.sql` has been run, loading all six tables into `brindle_dev_raw_db.raw`. Platform track: `brindle_ingest_rl` and `brindle_ingest_wh`. Plain account: `brindle_transform_rl` and `brindle_transform_wh`.
- [ ] Every table has `_fivetran_synced` (load timestamp) and `_fivetran_deleted` (boolean).
- [ ] The load uses **`empty_field_as_null = false`**, so `''` survives as `''`, and you can say why that matters here.
- [ ] **Break it on purpose.** Set `empty_field_as_null = true`, reload, and watch the blank count drop to 0 while the row count stays at 18,253. Nothing errors. Then revert and reload.
- [ ] The load is idempotent: a re-run replaces rather than duplicates.

**Verification:** in Snowflake, `select count(*) from brindle_dev_raw_db.raw.locations_passed where in_service_date = ''` returns **1442** and `select count(*) from brindle_dev_raw_db.raw.locations_passed` returns **18253**. During the break-it step the first query returns **0**. Write both results in `NOTES.md`.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-12, and BF-70 or BF-07

---

### BF-71: Raw load from SQL inside Snowflake
**As a** data engineer **I want** the same six tables created and filled with SQL inserts **so that** option A does not depend on a stage or a CSV copy.

**Learning objective:** the contract is the tables, not the tool that filled them. `COPY` from a stage and `INSERT` from SQL are the same raw layer if the rows match.

This is the alternate to BF-13. Do not do both. There is no `PUT` and no file format in this path, so you do not get the `empty_field_as_null` trap. Read that trap in BF-13 anyway. It is why the blanks are specified as `''`.

**Acceptance criteria**
- [ ] `snowflake/raw/seed_network.sql` has been run as the same role you would have used for BF-13.
- [ ] The script creates the six tables in `brindle_dev_raw_db.raw` and inserts every row. It does not create a stage.
- [ ] You can say where the file came from: `python data/export_seed_sql.py` writes it from `data/csv/`, so a generator change has a way back to SQL.
- [ ] Blanks are inserted as `''`, not NULL.
- [ ] A re-run truncates and inserts again. Row counts do not double.

**Verification:** the same two counts as BF-13. `in_service_date = ''` returns **1442**. `count(*)` on `locations_passed` returns **18253**. `in_service_date is null` returns **0**.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-12, and BF-70 or BF-07

---

### BF-14: Wire up Fivetran properly
**As a** data engineer **I want** a real Fivetran Postgres connector on a daily full-table sync **so that** ingestion is operated rather than scripted.

**Learning objective:** the difference between a stand-in and the real thing, and what a managed connector gives you that a script does not: scheduling, alerting, schema-drift handling, retries.

**Acceptance criteria**
- [ ] A Fivetran Postgres connector reads `brindle_src` in Postgres and lands in `brindle_dev_raw_db.raw`.
- [ ] Sync mode is **full table**, daily, per BF-12.
- [ ] The RDS security group permits Fivetran's egress ranges for the region.
- [ ] Raw row counts equal the Postgres counts. If you also did option A, the rows match that load field for field, and any difference is either reconciled or documented.
- [ ] `fivetran/README.md` records the connector ID, schedule, and destination.
- [ ] **Honest note:** the reference build never ran this. There were no API credentials, so BF-13 stood in. This story is the proper version, and it is untested.

**Verification:** after one sync, raw row counts equal Postgres row counts for all six tables, and `max(_fivetran_synced)` is within the last 24 hours. Then `dbt build` succeeds with **no model changes**, proving the contract held.

**Estimate:** M  ·  **Track:** aws  ·  **Depends on:** BF-10, and BF-13 or BF-71

---

### BF-15: Profile the dirty data before modelling
**As a** data engineer **I want** a written profile of the landed data **so that** the cleaning rules in the `int` layer come from evidence rather than assumption.

**Learning objective:** profile before you model. Every `int`-layer rule in this project traces to a number you can produce with one query.

**Acceptance criteria**
- [ ] Blank counts confirmed in Snowflake: `in_service_date` 1,442, `address_type` 529, `structure_type` 505, `hubsite` 575.
- [ ] Future-dated locations measured: 437 non-blank `in_service_date` values fall after 2024-09-13.
- [ ] `entity` distribution measured by address: 1,514 of 1,631 subscriber addresses (92.8%) are GREENFIELD. The rest are ACQUIRED or WHOLESALE.
- [ ] `subscribers` grain confirmed: `service_address_id` repeats, max repeat 3.
- [ ] Orphans measured: 12 subscriber addresses (21 period rows) have no matching location.
- [ ] `in_service_date` format confirmed as `MM-DD-YYYY` on every non-blank row, with no stray format.
- [ ] Findings recorded in `NOTES.md`, each with the query that produced it.

**Verification:** `select count(distinct s.service_address_id) from subscribers s left join locations_passed l on s.service_address_id = l.service_address_id where l.service_address_id is null` returns **12**. `select max(c) from (select service_address_id, count(*) c from subscribers group by 1)` returns **3**. `select count(*) from locations_passed where in_service_date <> '' and try_to_date(in_service_date, 'MM-DD-YYYY') is null` returns **0**.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-13 or BF-71
