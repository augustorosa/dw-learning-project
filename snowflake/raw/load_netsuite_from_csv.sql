-- Load data/csv/netsuite/*.csv into the Snowflake raw database.
-- NetSuite track, story BF-58. Stands in for a Fivetran NetSuite connector.
--
-- The tables keep NetSuite's own names (transaction, transactionline,
-- nexttransactionlinelink and so on), the way a connector lands them. Rows
-- deleted in NetSuite are still here, flagged _fivetran_deleted = true, which
-- is how Fivetran reports deletes. The CSVs already carry that flag.
-- _fivetran_synced is added at load time.
--
-- Run from the repo root. Platform track uses the ingest role.
-- Plain account (BF-70) uses brindle_transform_rl and brindle_transform_wh.
--
--   snow sql -f snowflake/raw/load_netsuite_from_csv.sql \
--     --role brindle_ingest_rl --warehouse brindle_ingest_wh
--
-- Safe to re-run: every table is truncated and reloaded.

use database brindle_dev_raw_db;
create schema if not exists netsuite;
use schema netsuite;

create stage if not exists netsuite_csv_stage;
put file://data/csv/netsuite/*.csv @netsuite_csv_stage overwrite = true auto_compress = false;

create or replace file format netsuite_csv
  type = csv
  skip_header = 1
  field_optionally_enclosed_by = '"'
  empty_field_as_null = false
  null_if = ('\\N');

-- ---------------------------------------------------------------- tables
create table if not exists currency (
  id number, symbol varchar, name varchar,
  _fivetran_synced timestamp_tz, _fivetran_deleted boolean);

create table if not exists account (
  id number, acctnumber varchar, fullname varchar, accttype varchar,
  _fivetran_synced timestamp_tz, _fivetran_deleted boolean);

create table if not exists vendor (
  id number, entityid varchar, companyname varchar, category varchar,
  currency number, isinactive varchar, lastmodifieddate timestamp_ntz,
  _fivetran_synced timestamp_tz, _fivetran_deleted boolean);

create table if not exists transaction (
  id number, tranid varchar,
  type varchar,               -- VendBill or VendPmt
  trandate date, entity number, currency number,
  exchangerate number(18, 6), -- to USD, per transaction
  status varchar,             -- as of the extract, not as of any report date
  memo varchar, lastmodifieddate timestamp_ntz,
  _fivetran_synced timestamp_tz, _fivetran_deleted boolean);

create table if not exists transactionline (
  transaction number, id number,
  mainline varchar,           -- 'T' on line 0: the header total, opposite sign
  account number,
  foreignamount number(18, 2),  -- in the transaction's currency
  netamount number(18, 2),      -- in USD at the transaction's own rate
  custcol_bf_service_area varchar,
  memo varchar,
  _fivetran_synced timestamp_tz, _fivetran_deleted boolean);

create table if not exists nexttransactionlinelink (
  previousdoc number, previousline number,   -- the bill
  nextdoc number, nextline number,           -- the payment
  linktype varchar,
  foreignamount number(18, 2),               -- applied, in the bill's currency
  _fivetran_synced timestamp_tz, _fivetran_deleted boolean);

-- ---------------------------------------------------------------- load
truncate table currency;
copy into currency from (
  select $1, $2, $3, current_timestamp(), false
  from @netsuite_csv_stage/currency.csv)
  file_format = (format_name = netsuite_csv) force = true;

truncate table account;
copy into account from (
  select $1, $2, $3, $4, current_timestamp(), $5
  from @netsuite_csv_stage/account.csv)
  file_format = (format_name = netsuite_csv) force = true;

truncate table vendor;
copy into vendor from (
  select $1, $2, $3, $4, $5, $6, $7, current_timestamp(), $8
  from @netsuite_csv_stage/vendor.csv)
  file_format = (format_name = netsuite_csv) force = true;

truncate table transaction;
copy into transaction from (
  select $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, current_timestamp(), $11
  from @netsuite_csv_stage/transaction.csv)
  file_format = (format_name = netsuite_csv) force = true;

truncate table transactionline;
copy into transactionline from (
  select $1, $2, $3, $4, $5, $6, $7, $8, current_timestamp(), $9
  from @netsuite_csv_stage/transactionline.csv)
  file_format = (format_name = netsuite_csv) force = true;

truncate table nexttransactionlinelink;
copy into nexttransactionlinelink from (
  select $1, $2, $3, $4, $5, $6, current_timestamp(), $7
  from @netsuite_csv_stage/nexttransactionlinelink.csv)
  file_format = (format_name = netsuite_csv) force = true;

-- ---------------------------------------------------------------- check
-- Expected: 2, 8, 12, 3204, 9977, 2359, then 10 deleted transactions and
-- a sum of 0.00 over every bill line (mainline included, which is the trap).
select 'currency' as check_name, count(*)::varchar as n from currency
union all select 'account', count(*)::varchar from account
union all select 'vendor', count(*)::varchar from vendor
union all select 'transaction', count(*)::varchar from transaction
union all select 'transactionline', count(*)::varchar from transactionline
union all select 'nexttransactionlinelink', count(*)::varchar from nexttransactionlinelink
union all select 'deleted transactions', count(*)::varchar from transaction where _fivetran_deleted
union all select 'sum of all bill lines', sum(l.foreignamount)::varchar
  from transactionline l join transaction t on t.id = l.transaction where t.type = 'VendBill';
