# Epic 11: Incremental models (optional track)

Stories BF-77 and BF-78. Do this after BF-27. It does not replace BF-12.

The network tables are restored nightly and stay a full refresh. This track adds a
different table, `service_events`, that really is append-only, so `is_incremental()` has
something honest to do.

---

### BF-77: An append-only event table
**As a** data engineer **I want** activations and cancellations landed as events **so that** an incremental model has a watermark that means something.

**Learning objective:** incremental is a property of the source, not a setting you turn on because full refresh feels slow. `subscribers` is still a full copy. `service_events` is one row per order event and only grows.

**Acceptance criteria**
- [ ] `snowflake/raw/load_service_events.sql` has been run against `brindle_dev_raw_db.raw`.
- [ ] The table is built from `subscribers`: `event_id` is `subscriber_period_id`, `event_at` is `service_eff_date`, `event_type` is `activation` when `is_active = 1` and `cancellation` otherwise.
- [ ] A second run of the script adds **0** rows.
- [ ] `NOTES.md` says why this table can be incremental and `locations_passed` cannot. Point at the BF-12 decision record.

**Verification:** `select count(*) from brindle_dev_raw_db.raw.service_events` returns **2194**. `count_if(event_type = 'activation')` returns **1669**. `count_if(event_type = 'cancellation')` returns **525**. `max(event_at)` is **2024-09-13**.

**Estimate:** S  ·  **Track:** incremental  ·  **Depends on:** BF-15, BF-27

---

### BF-78: `int_service_event` incremental model
**As a** data engineer **I want** an incremental model on `event_at` **so that** a second build adds nothing and a late row adds one.

**Learning objective:** `materialized='incremental'`, `unique_key`, `is_incremental()`, and `on_schema_change`. The `int` folder is views. This model overrides that. The override is the point, the same way `v_by_market_current` overrides `anl` tables.

**Acceptance criteria**
- [ ] `dbt/models/int/int_service_event.sql` is `materialized='incremental'` with `unique_key='event_id'`.
- [ ] The incremental filter is `event_at > (select max(event_at) from {{ this }})`, wrapped in `{% if is_incremental() %}`.
- [ ] A comment says a row with `event_at` equal to the current max is skipped by that filter. The late row in this story is the next day, so the demo does not hide inside that hole.
- [ ] `on_schema_change='fail'`, with a comment that a new column should break the build until someone decides. Silent append would hide a contract change.
- [ ] First `dbt build --select int_service_event` loads **2194** rows.
- [ ] Second build, with no source change, adds **0**.
- [ ] Then `snowflake/raw/insert_late_service_event.sql` inserts event **9000001** at **2024-09-14**. The next build adds **1**.

**Verification:** after the third build, `select count(*) from int_service_event` returns **2195**, and `select event_type from int_service_event where event_id = 9000001` returns **activation**. The row count after the second build was **2194**.

**Estimate:** M  ·  **Track:** incremental  ·  **Depends on:** BF-77
