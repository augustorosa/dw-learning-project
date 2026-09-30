-- BF-77. Append-only service events, derived from the subscriber extract.
-- The passings tables stay a full refresh. BF-12 still applies to them.
-- This script does not reload rows that are already here, so a second run adds 0.
-- The late row for BF-78 is insert_late_service_event.sql, not this file.
--
--   snow sql -f snowflake/raw/load_service_events.sql -c brindle \
--     --role brindle_transform_rl --warehouse brindle_transform_wh

use database brindle_dev_raw_db;
use schema raw;

create table if not exists service_events (
  event_id number,
  service_address_id varchar,
  event_type varchar,
  event_at date,
  _fivetran_synced timestamp_tz,
  _fivetran_deleted boolean
);

insert into service_events (
  event_id, service_address_id, event_type, event_at, _fivetran_synced, _fivetran_deleted
)
select
  subscriber_period_id,
  service_address_id,
  case when is_active = 1 then 'activation' else 'cancellation' end,
  service_eff_date,
  current_timestamp(),
  false
from subscribers
where subscriber_period_id not in (select event_id from service_events);

select event_type, count(*) as n
from service_events
group by 1
order by 1;
