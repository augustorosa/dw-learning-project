-- Load data/csv/*.csv straight into the Snowflake raw database.
-- Core track: this replaces RDS Postgres and Fivetran (story BF-13).
--
-- It lands the data in the same shape a Fivetran full-table sync would:
-- the source columns, plus _fivetran_synced and _fivetran_deleted on every
-- table. Your dbt sources are declared against that shape, so if you later
-- swap in the AWS track or a real connector, no model changes.
--
-- Run from the repo root after the raw database exists.
-- Platform track (BF-07): brindle_ingest_rl owns schema raw.
-- Plain account (BF-70): brindle_transform_rl owns schema raw.
-- Either role must be able to create the stage, file format, and tables:
--
-- Platform track:
--   snow sql -f snowflake/raw/load_raw_from_csv.sql \
--     --role brindle_ingest_rl --warehouse brindle_ingest_wh
-- Plain account (BF-70), no ingest role:
--   snow sql -f snowflake/raw/load_raw_from_csv.sql \
--     --role brindle_transform_rl --warehouse brindle_transform_wh
--
-- The PUT below uses a path relative to where you run the command. If your
-- client complains about it, swap in an absolute path (file:///Users/...).
--
-- Safe to re-run: every table is truncated and reloaded with force = true.

use database brindle_dev_raw_db;
create schema if not exists raw;
use schema raw;

create stage if not exists raw_csv_stage;
put file://data/csv/*.csv @raw_csv_stage overwrite = true auto_compress = false;

-- The one setting that matters.
-- The CSVs write a blank as an empty unquoted field (,,). With
-- empty_field_as_null = true (the Snowflake default) those blanks arrive as
-- NULL and the 1,442 blank in_service_date values silently disappear.
-- In this dataset '' versus NULL IS the data-quality signal. Keep it false.
create or replace file format raw_csv
  type = csv
  skip_header = 1
  field_optionally_enclosed_by = '"'
  empty_field_as_null = false
  null_if = ('\\N');

-- ---------------------------------------------------------------- tables
create table if not exists markets (
  market_id number, market_name varchar, state_code varchar,
  _fivetran_synced timestamp_tz, _fivetran_deleted boolean);

create table if not exists hubsites (
  hubsite_id number, hubsite_name varchar, market_id number,
  _fivetran_synced timestamp_tz, _fivetran_deleted boolean);

create table if not exists service_areas (
  service_area_id number, service_area_name varchar, hubsite_id number,
  _fivetran_synced timestamp_tz, _fivetran_deleted boolean);

create table if not exists pon_zones (
  pon_zone_id number, pon_zone_name varchar, service_area_id number,
  _fivetran_synced timestamp_tz, _fivetran_deleted boolean);

create table if not exists locations_passed (
  service_address_id varchar, pon_zone_id number, street_address varchar, city varchar,
  address_type varchar, structure_type varchar, hubsite varchar,
  in_service_date varchar,   -- MM-DD-YYYY text, blank on purpose. Do not cast it here.
  _fivetran_synced timestamp_tz, _fivetran_deleted boolean);

create table if not exists subscribers (
  subscriber_period_id number, service_address_id varchar, entity varchar,
  service_eff_date date, is_active number,
  _fivetran_synced timestamp_tz, _fivetran_deleted boolean);

-- ---------------------------------------------------------------- load
truncate table markets;
copy into markets from (
  select $1, $2, $3, current_timestamp(), false
  from @raw_csv_stage/markets.csv)
  file_format = (format_name = raw_csv) force = true;

truncate table hubsites;
copy into hubsites from (
  select $1, $2, $3, current_timestamp(), false
  from @raw_csv_stage/hubsites.csv)
  file_format = (format_name = raw_csv) force = true;

truncate table service_areas;
copy into service_areas from (
  select $1, $2, $3, current_timestamp(), false
  from @raw_csv_stage/service_areas.csv)
  file_format = (format_name = raw_csv) force = true;

truncate table pon_zones;
copy into pon_zones from (
  select $1, $2, $3, current_timestamp(), false
  from @raw_csv_stage/pon_zones.csv)
  file_format = (format_name = raw_csv) force = true;

truncate table locations_passed;
copy into locations_passed from (
  select $1, $2, $3, $4, $5, $6, $7, $8, current_timestamp(), false
  from @raw_csv_stage/locations_passed.csv)
  file_format = (format_name = raw_csv) force = true;

truncate table subscribers;
copy into subscribers from (
  select $1, $2, $3, $4, $5, current_timestamp(), false
  from @raw_csv_stage/subscribers.csv)
  file_format = (format_name = raw_csv) force = true;

-- ---------------------------------------------------------------- check
-- Expected: 6, 12, 30, 580, 18253, 2194, then 1442 blanks and 0 NULLs.
select 'markets' as check_name, count(*) as n from markets
union all select 'hubsites', count(*) from hubsites
union all select 'service_areas', count(*) from service_areas
union all select 'pon_zones', count(*) from pon_zones
union all select 'locations_passed', count(*) from locations_passed
union all select 'subscribers', count(*) from subscribers
union all select 'blank in_service_date', count(*) from locations_passed where in_service_date = ''
union all select 'NULL in_service_date', count(*) from locations_passed where in_service_date is null;
