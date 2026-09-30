-- Brindle Fiber operational source (fictional). Optional AWS track.
--
-- These tables copy the shape of a messy operational system on purpose.
-- Do not "fix" the types here. The dirt is the curriculum, and the int layer
-- in dbt is where it gets cleaned.

set client_min_messages = warning;
create schema if not exists brindle_src;
set search_path = brindle_src;

drop table if exists subscribers, locations_passed, pon_zones, service_areas, hubsites, markets;

create table markets (
    market_id        integer primary key,
    market_name      varchar(100) not null,
    state_code       varchar(2)   not null
);

create table hubsites (
    hubsite_id       integer primary key,
    hubsite_name     varchar(100) not null,
    market_id        integer      not null references markets
);

create table service_areas (
    service_area_id   integer primary key,
    service_area_name varchar(100) not null,
    hubsite_id        integer      not null references hubsites
);

create table pon_zones (
    pon_zone_id      integer primary key,
    pon_zone_name    varchar(20)  not null,
    service_area_id  integer      not null references service_areas
);

create table locations_passed (
    service_address_id varchar(12)  primary key,
    pon_zone_id        integer      not null references pon_zones,
    street_address     varchar(200) not null,
    city               varchar(100) not null,
    -- empty string means "the field team left it blank". It is not NULL, and
    -- that difference is the whole data-quality signal in this project.
    address_type       varchar(20)  not null,
    structure_type     varchar(20)  not null,
    -- free-text copy of the hub name, typed by hand in the source app, often blank
    hubsite            varchar(100) not null,
    -- MM-DD-YYYY stored as text, and blank for 1,442 rows. Yes, really.
    in_service_date    varchar(10)  not null
);

-- Subscriber-PERIOD grain: one row per order at an address.
-- service_address_id is deliberately NOT unique, and there is deliberately no
-- foreign key to locations_passed, because 12 orphan addresses must load.
create table subscribers (
    subscriber_period_id integer     primary key,
    service_address_id   varchar(12) not null,
    entity               varchar(20) not null,   -- GREENFIELD, ACQUIRED, WHOLESALE
    service_eff_date     date        not null,
    is_active            smallint    not null    -- 1 = order installed, 0 = cancelled
);
