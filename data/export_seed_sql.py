#!/usr/bin/env python3
"""Write snowflake/raw/seed_network.sql from data/csv. Used by BF-71.

The CSV load and this SQL insert are two ways into the same raw tables.
Re-run this after generate_data.py if you change the network data.
"""

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = ROOT / "data" / "csv"
OUT = ROOT / "snowflake" / "raw" / "seed_network.sql"
BATCH = 200

TABLES = [
    ("markets", ["market_id", "market_name", "state_code"], [int, str, str]),
    ("hubsites", ["hubsite_id", "hubsite_name", "market_id"], [int, str, int]),
    ("service_areas", ["service_area_id", "service_area_name", "hubsite_id"], [int, str, int]),
    ("pon_zones", ["pon_zone_id", "pon_zone_name", "service_area_id"], [int, str, int]),
    (
        "locations_passed",
        [
            "service_address_id",
            "pon_zone_id",
            "street_address",
            "city",
            "address_type",
            "structure_type",
            "hubsite",
            "in_service_date",
        ],
        [str, int, str, str, str, str, str, str],
    ),
    (
        "subscribers",
        ["subscriber_period_id", "service_address_id", "entity", "service_eff_date", "is_active"],
        [int, str, str, str, int],
    ),
]

DDL = """
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
  in_service_date varchar,
  _fivetran_synced timestamp_tz, _fivetran_deleted boolean);

create table if not exists subscribers (
  subscriber_period_id number, service_address_id varchar, entity varchar,
  service_eff_date date, is_active number,
  _fivetran_synced timestamp_tz, _fivetran_deleted boolean);
""".strip()


def sql_literal(value: str, kind: type) -> str:
    if kind is int:
        return value
    if kind is str and value == "" :
        return "''"
    escaped = value.replace("'", "''")
    if kind is str:
        return f"'{escaped}'"
    return f"'{escaped}'"


def rows(name: str) -> list[dict]:
    with (CSV_DIR / f"{name}.csv").open(newline="") as handle:
        return list(csv.DictReader(handle))


def inserts(name: str, columns: list[str], kinds: list[type]) -> str:
    body = []
    data = rows(name)
    col_list = ", ".join(columns)
    for start in range(0, len(data), BATCH):
        chunk = data[start : start + BATCH]
        values = []
        for row in chunk:
            values.append("(" + ", ".join(sql_literal(row[c], k) for c, k in zip(columns, kinds)) + ")")
        body.append(
            f"insert into {name} ({col_list}, _fivetran_synced, _fivetran_deleted)\n"
            f"select {col_list}, current_timestamp(), false\n"
            f"from values\n  " + ",\n  ".join(values) + f"\n  as v({col_list});"
        )
    return "\n\n".join(body)


def main() -> None:
    parts = [
        "-- BF-71. Insert the network tables into the raw layer. No stage, no CSV copy.",
        "-- Generated from data/csv by data/export_seed_sql.py. Do not hand-edit.",
        "-- Re-run that script if you regenerate the network data.",
        "--",
        "--   snow sql -f snowflake/raw/seed_network.sql -c brindle \\",
        "--     --role brindle_transform_rl --warehouse brindle_transform_wh",
        "",
        "use database brindle_dev_raw_db;",
        "create schema if not exists raw;",
        "use schema raw;",
        "",
        DDL,
        "",
    ]
    for name, columns, kinds in TABLES:
        parts.append(f"truncate table if exists {name};")
        parts.append(inserts(name, columns, kinds))
        parts.append("")
    parts.append(
        """select 'markets' as check_name, count(*) as n from markets
union all select 'hubsites', count(*) from hubsites
union all select 'service_areas', count(*) from service_areas
union all select 'pon_zones', count(*) from pon_zones
union all select 'locations_passed', count(*) from locations_passed
union all select 'subscribers', count(*) from subscribers
union all select 'blank in_service_date', count(*) from locations_passed where in_service_date = ''
union all select 'NULL in_service_date', count(*) from locations_passed where in_service_date is null;
"""
    )
    OUT.write_text("\n".join(parts))
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
