-- BF-79. Second vendor extract. Changes one attribute on vendor 101.
-- Snapshot the vendors before you run this, or the old name is gone.
--
--   snow sql -f snowflake/raw/apply_vendor_change.sql -c brindle \
--     --role brindle_transform_rl --warehouse brindle_transform_wh

update brindle_dev_raw_db.netsuite.vendor
set companyname = 'Granitepoint Civil Group',
    lastmodifieddate = '2024-06-01 09:00:00'
where id = 101
  and companyname = 'Granitepoint Civil';
