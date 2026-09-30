-- BF-70. The account the core track needs when you skip the platform track.
-- If BF-07 already created these databases, do not run this.
--
-- Replace <your_user> before you run it. Do not commit the username.
--
--   snow sql -f snowflake/bootstrap/plain_account.sql -c brindle

create warehouse if not exists brindle_transform_wh
  warehouse_size = xsmall
  auto_suspend = 60
  auto_resume = true
  initially_suspended = true;

create database if not exists brindle_dev_raw_db;
create database if not exists brindle_dev_int_db;
create database if not exists brindle_dev_anl_db;

create schema if not exists brindle_dev_raw_db.raw;

create role if not exists brindle_transform_rl;

grant usage on warehouse brindle_transform_wh to role brindle_transform_rl;
grant usage on database brindle_dev_raw_db to role brindle_transform_rl;
grant usage on database brindle_dev_int_db to role brindle_transform_rl;
grant usage on database brindle_dev_anl_db to role brindle_transform_rl;
grant ownership on schema brindle_dev_raw_db.raw to role brindle_transform_rl copy current grants;
grant create schema on database brindle_dev_int_db to role brindle_transform_rl;
grant create schema on database brindle_dev_anl_db to role brindle_transform_rl;

grant role brindle_transform_rl to user <your_user>;
