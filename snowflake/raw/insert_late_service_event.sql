-- BF-78. One late event, strictly after the current max event_at (2024-09-13).
-- Run this only after the first two incremental builds, then build again.
--
--   snow sql -f snowflake/raw/insert_late_service_event.sql -c brindle \
--     --role brindle_transform_rl --warehouse brindle_transform_wh

insert into brindle_dev_raw_db.raw.service_events (
  event_id, service_address_id, event_type, event_at, _fivetran_synced, _fivetran_deleted
)
select 9000001, 'SA-LATE', 'activation', '2024-09-14'::date, current_timestamp(), false
where not exists (
  select 1
  from brindle_dev_raw_db.raw.service_events
  where event_id = 9000001
);
