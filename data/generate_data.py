#!/usr/bin/env python3
"""
Brindle Fiber synthetic source data generator.

Brindle Fiber is a made-up fiber ISP. Any resemblance to a real company is
coincidental.

Writes six CSV files into data/csv/ that stand in for the operational Postgres
source. The data is deliberately dirty, and the dirt is the curriculum:

  * in_service_date is a VARCHAR in MM-DD-YYYY format, and 1,442 rows hold an
    empty string instead of a date
  * address_type, structure_type and hubsite have planted empty strings
  * subscribers is at subscriber-PERIOD grain, so service_address_id repeats
  * 12 subscriber addresses are orphans with no matching location
  * a batch of orders was cancelled by a 2022 billing migration and re-signed
    later (this is what defect A trips over)
  * some locations go into service AFTER the report as-of date, so the
    as-of cutoff actually excludes something

Determinism: only the standard library `random` module is used, seeded with 42.
No Faker, because Faker's generated values change between Faker releases and
"seeded" would stop meaning "reproducible". Re-running this script on any
Python 3.9+ produces byte-identical CSVs.

CSV conventions (these matter, see GOTCHAS "empty_field_as_null"):
  * blanks are written as an empty, UNQUOTED field:   ...,,...
  * there are no SQL NULLs in the source. If you ever need one, write \\N
  * header row on every file, comma delimited, UTF-8, \\n line endings

Usage:
    python data/generate_data.py            # writes data/csv/*.csv and prints a profile
    python data/generate_data.py --check    # regenerates in memory, compares to the files on disk
"""

from __future__ import annotations

import argparse
import csv
import io
import random
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

SEED = 42
REPORT_AS_OF = date(2024, 9, 13)

# Exact planted counts. Changing any of these changes the anchor numbers.
N_MARKETS = 6
N_HUBSITES = 12
N_SERVICE_AREAS = 30
N_PON_ZONES = 580
N_LOCATIONS = 18_253
N_BLANK_IN_SERVICE_DATE = 1_442
N_FUTURE_IN_SERVICE = 437          # real dates after REPORT_AS_OF, so the cutoff bites
N_BLANK_ADDRESS_TYPE = 529
N_BLANK_STRUCTURE_TYPE = 505
N_BLANK_HUBSITE = 575
N_SUBSCRIBER_ROWS = 2_194
N_ORPHAN_ADDRESSES = 12

BUILD_START = date(2021, 1, 4)
BUILD_END = date(2024, 9, 1)        # last "past" in-service date
FUTURE_END = date(2025, 3, 28)      # last future in-service date
MIGRATION_DATE = date(2022, 3, 1)   # billing migration that cancelled orders

MARKETS = [
    # market_id, market_name, state_code, weight (size), launch offset in days, take rate
    (1, "Ashford Valley", "NY", 1.00, 0, 0.060),
    (2, "Briar Coast", "MA", 0.86, 60, 0.048),
    (3, "Cobalt Hills", "VT", 0.80, 120, 0.075),
    (4, "Dunmore Plains", "NY", 1.30, 30, 0.036),
    (5, "Evergreen Lakes", "NH", 0.97, 200, 0.050),
    (6, "Foxglove Ridge", "CT", 0.70, 90, 0.085),
]
HUBSITE_SUFFIXES = ["North Hub", "South Hub"]
TOWNS = [
    "Alder", "Bramble", "Calder", "Dovecote", "Elmsworth", "Fernhill", "Galloway",
    "Hartwell", "Ivybridge", "Juniper", "Kingsmere", "Lindale", "Marlow", "Netherby",
    "Oakhurst", "Pemberton", "Quarry", "Rookwood", "Stanmore", "Thornbury",
    "Upton", "Vale", "Westbrook", "Yarrow", "Ashby", "Bexley", "Cranmore",
    "Draycott", "Eastleigh", "Fairholme",
]
STREETS = [
    "Maple", "Cedar", "Birch", "Willow", "Hawthorn", "Chestnut", "Sycamore", "Aspen",
    "Laurel", "Hemlock", "Poplar", "Linden", "Spruce", "Magnolia", "Rowan", "Hazel",
]
STREET_TYPES = ["St", "Ave", "Rd", "Ln", "Dr", "Ct", "Way"]
OTHER_ENTITIES = ["ACQUIRED", "WHOLESALE"]


def mmddyyyy(d: date) -> str:
    return d.strftime("%m-%d-%Y")


def ramp_date(rng: random.Random, start: date, end: date) -> date:
    """A date in [start, end] with density rising over time, like a build-out."""
    span = (end - start).days
    return start + timedelta(days=int(span * (rng.random() ** 0.6)))


def generate() -> dict[str, list[list]]:
    rng = random.Random(SEED)

    # ---- hierarchy -------------------------------------------------------
    markets = [[m[0], m[1], m[2]] for m in MARKETS]

    hubsites = []
    hub_id = 0
    hubs_by_market = defaultdict(list)
    for m in MARKETS:
        for suffix in HUBSITE_SUFFIXES:
            hub_id += 1
            name = f"{m[1].split()[0]} {suffix}"
            hubsites.append([hub_id, name, m[0]])
            hubs_by_market[m[0]].append(hub_id)

    # 5 service areas per market: 3 on the first hub, 2 on the second
    service_areas = []
    sa_market = {}
    sa_id = 0
    towns = TOWNS[:]
    rng.shuffle(towns)
    for m in MARKETS:
        h1, h2 = hubs_by_market[m[0]]
        for hub in (h1, h1, h1, h2, h2):
            sa_id += 1
            service_areas.append([sa_id, towns[sa_id - 1], hub])
            sa_market[sa_id] = m[0]

    # 580 PON zones spread unevenly over the 30 service areas
    sa_weights = [rng.uniform(0.6, 1.4) for _ in range(N_SERVICE_AREAS)]
    pon_zones = []
    zone_sa = {}
    zone_counts = [1] * N_SERVICE_AREAS  # every area gets at least one zone
    for _ in range(N_PON_ZONES - N_SERVICE_AREAS):
        zone_counts[rng.choices(range(N_SERVICE_AREAS), weights=sa_weights)[0]] += 1
    pz_id = 0
    for sa_index, count in enumerate(zone_counts):
        for n in range(count):
            pz_id += 1
            sa = sa_index + 1
            pon_zones.append([pz_id, f"PON-{sa:02d}-{n + 1:03d}", sa])
            zone_sa[pz_id] = sa

    # ---- locations -------------------------------------------------------
    market_weight = {m[0]: m[3] for m in MARKETS}
    zone_weights = [market_weight[sa_market[zone_sa[z]]] * rng.uniform(0.5, 1.5)
                    for z in range(1, N_PON_ZONES + 1)]
    hub_name = {h[0]: h[1] for h in hubsites}
    sa_hub = {s[0]: s[2] for s in service_areas}
    sa_town = {s[0]: s[1] for s in service_areas}
    launch = {m[0]: BUILD_START + timedelta(days=m[4]) for m in MARKETS}

    ids = rng.sample(range(1_000_000, 8_999_999), N_LOCATIONS)
    idx = list(range(N_LOCATIONS))
    blank_date = set(rng.sample(idx, N_BLANK_IN_SERVICE_DATE))
    remaining = [i for i in idx if i not in blank_date]
    future = set(rng.sample(remaining, N_FUTURE_IN_SERVICE))
    blank_addr = set(rng.sample(idx, N_BLANK_ADDRESS_TYPE))
    blank_struct = set(rng.sample(idx, N_BLANK_STRUCTURE_TYPE))
    blank_hub = set(rng.sample(idx, N_BLANK_HUBSITE))

    locations = []
    loc_meta = {}  # service_address_id -> (market_id, in_service date or None)
    for i in idx:
        zone = rng.choices(range(1, N_PON_ZONES + 1), weights=zone_weights)[0]
        sa = zone_sa[zone]
        mkt = sa_market[sa]
        said = f"SA{ids[i]:07d}"
        street = f"{rng.randint(1, 9999)} {rng.choice(STREETS)} {rng.choice(STREET_TYPES)}"
        structure = rng.choices(["SFU", "MDU"], weights=[0.83, 0.17])[0]
        addr_type = rng.choices(["RESIDENTIAL", "BUSINESS"], weights=[0.91, 0.09])[0]

        if i in blank_date:
            isd, isd_text = None, ""
        elif i in future:
            isd = REPORT_AS_OF + timedelta(days=1 + rng.randint(0, (FUTURE_END - REPORT_AS_OF).days - 1))
            isd_text = mmddyyyy(isd)
        else:
            isd = ramp_date(rng, launch[mkt], BUILD_END)
            isd_text = mmddyyyy(isd)

        locations.append([
            said, zone, street, sa_town[sa],
            "" if i in blank_addr else addr_type,
            "" if i in blank_struct else structure,
            "" if i in blank_hub else hub_name[sa_hub[sa]],
            isd_text,
        ])
        loc_meta[said] = (mkt, isd)

    # ---- subscribers (subscriber-period grain) ---------------------------
    take_rate = {m[0]: m[5] for m in MARKETS}
    eligible = [s for s, (mkt, isd) in loc_meta.items() if isd is not None and isd <= REPORT_AS_OF]
    rng.shuffle(eligible)

    def periods_for(first_date: date) -> list[tuple[date, int]]:
        """Build 1 to 3 periods. Once an address has been active, its LAST period
        is always active: a cancelled order is always followed by a re-sign.
        That property is what makes defect A invisible at the report month."""
        span_left = (REPORT_AS_OF - first_date).days
        if span_left < 60:
            return [(first_date, 1)]
        if first_date < MIGRATION_DATE and rng.random() < 0.65:
            # migration victim: active, cancelled by the migration, re-signed later
            resign = MIGRATION_DATE + timedelta(days=rng.randint(200, 640))
            resign = min(resign, REPORT_AS_OF)
            return [(first_date, 1), (MIGRATION_DATE + timedelta(days=rng.randint(0, 20)), 0), (resign, 1)]
        roll = rng.random()
        if roll < 0.45:
            return [(first_date, 1)]  # one order, installed
        if roll < 0.65:
            # never installed: every order cancelled
            n = rng.choice([1, 2])
            out, d = [], first_date
            for _ in range(n):
                out.append((d, 0))
                d = min(d + timedelta(days=rng.randint(30, 300)), REPORT_AS_OF)
            return out
        if roll < 0.82:
            # cancelled first order, installed on the second
            second = min(first_date + timedelta(days=rng.randint(20, 180)), REPORT_AS_OF)
            return [(first_date, 0), (second, 1)]
        # plain upgrade: two active periods
        second = min(first_date + timedelta(days=rng.randint(90, 500)), REPORT_AS_OF)
        return [(first_date, 1), (second, 1)]

    subscriber_rows: list[list] = []
    pid = 0

    def add_address(said: str, first_date: date, entity: str, periods=None):
        nonlocal pid
        for eff, active in (periods or periods_for(first_date)):
            pid += 1
            subscriber_rows.append([pid, said, entity, eff.isoformat(), active])

    # orphans first, so their share is fixed regardless of the take rates
    orphan_ids = rng.sample(range(9_000_000, 9_999_999), N_ORPHAN_ADDRESSES)
    for oid in orphan_ids:
        first = ramp_date(rng, date(2021, 6, 1), date(2024, 6, 1))
        add_address(f"SA{oid:07d}", first, "GREENFIELD")

    for said in eligible:
        if len(subscriber_rows) >= N_SUBSCRIBER_ROWS:
            break
        mkt, isd = loc_meta[said]
        if rng.random() > take_rate[mkt] * 1.85:
            continue
        first = min(isd + timedelta(days=rng.randint(7, 420)), REPORT_AS_OF)
        entity = "GREENFIELD" if rng.random() < 0.92 else rng.choice(OTHER_ENTITIES)
        add_address(said, first, entity)

    # trim to the exact row count, then drop any address left half-written
    # in a way that breaks the "last period active if ever active" property
    subscriber_rows = subscriber_rows[:N_SUBSCRIBER_ROWS]
    by_addr = defaultdict(list)
    for r in subscriber_rows:
        by_addr[r[1]].append(r)
    last = subscriber_rows[-1][1]
    rows = by_addr[last]
    if any(r[4] == 1 for r in rows) and rows[-1][4] == 0:
        rows[-1][4] = 1  # keep the property, keep the count

    return {
        "markets": [["market_id", "market_name", "state_code"]] + markets,
        "hubsites": [["hubsite_id", "hubsite_name", "market_id"]] + hubsites,
        "service_areas": [["service_area_id", "service_area_name", "hubsite_id"]] + service_areas,
        "pon_zones": [["pon_zone_id", "pon_zone_name", "service_area_id"]] + pon_zones,
        "locations_passed": [["service_address_id", "pon_zone_id", "street_address", "city",
                              "address_type", "structure_type", "hubsite", "in_service_date"]] + locations,
        "subscribers": [["subscriber_period_id", "service_address_id", "entity",
                         "service_eff_date", "is_active"]] + subscriber_rows,
    }


def to_csv(rows: list[list]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n", quoting=csv.QUOTE_MINIMAL).writerows(rows)
    return buf.getvalue()


# ---- profile: the business rules applied in plain Python ------------------
def month_ends(first: date, last: date):
    y, m = first.year, first.month
    while (y, m) <= (last.year, last.month):
        nxt = date(y + (m == 12), m % 12 + 1, 1)
        yield f"{y:04d}-{m:02d}", nxt - timedelta(days=1)
        y, m = nxt.year, nxt.month


def profile(tables: dict[str, list[list]]) -> None:
    locs = tables["locations_passed"][1:]
    subs = tables["subscribers"][1:]
    zone_sa = {r[0]: r[2] for r in tables["pon_zones"][1:]}
    sa_hub = {r[0]: r[2] for r in tables["service_areas"][1:]}
    hub_mkt = {r[0]: r[2] for r in tables["hubsites"][1:]}
    mkt_name = {r[0]: r[1] for r in tables["markets"][1:]}

    def parse(s: str) -> date:
        return date(2030, 12, 31) if s == "" else date(int(s[6:]), int(s[:2]), int(s[3:5]))

    loc = {r[0]: (hub_mkt[sa_hub[zone_sa[r[1]]]], parse(r[7])) for r in locs}

    periods = defaultdict(list)
    entity = {}
    for _, said, ent, eff, active in subs:
        periods[said].append((date.fromisoformat(eff), active))
        entity[said] = ent
    orphans = [s for s in periods if s not in loc]

    first_active = {}
    for said, ps in periods.items():
        acts = [d for d, a in ps if a == 1]
        if said in loc and entity[said] == "GREENFIELD" and acts:
            first_active[said] = min(acts)

    first_month = min(d for _, d in loc.values()).replace(day=1)
    months = list(month_ends(first_month, REPORT_AS_OF))

    def point(month_end: date) -> date:
        return min(month_end, REPORT_AS_OF)

    def balances(month_end: date, defect: bool = False):
        p = defaultdict(int)
        s = defaultdict(int)
        cut = point(month_end)
        for said, (mkt, isd) in loc.items():
            if isd <= cut:
                p[mkt] += 1
        if not defect:
            for said, fa in first_active.items():
                if fa <= cut:
                    s[loc[said][0]] += 1
        else:
            # defect A: latest period as of the month (max service_eff_date), counted if active
            for said, ps in periods.items():
                if said not in loc or entity[said] != "GREENFIELD":
                    continue
                if not any(a for _, a in ps):
                    continue
                current = [x for x in ps if x[0] <= cut]
                if current and max(current)[1] == 1:
                    s[loc[said][0]] += 1
        return p, s

    ym_final, me_final = months[-1]
    p, s = balances(me_final)
    P, S = sum(p.values()), sum(s.values())

    print("== raw counts ==")
    for t, rows in tables.items():
        print(f"  {t:<17} {len(rows) - 1:>6}")
    print(f"  total source rows {sum(len(r) - 1 for r in tables.values()):>6}")
    print("== planted dirt ==")
    print(f"  blank in_service_date   {sum(1 for r in locs if r[7] == '')}")
    print(f"  blank address_type      {sum(1 for r in locs if r[4] == '')}")
    print(f"  blank structure_type    {sum(1 for r in locs if r[5] == '')}")
    print(f"  blank hubsite           {sum(1 for r in locs if r[6] == '')}")
    fut = sum(1 for m, d in loc.values() if REPORT_AS_OF < d < date(2030, 12, 31))
    print(f"  dated after as-of       {fut}")
    print(f"  max real in_service     {max(d for _, d in loc.values() if d.year < 2030)}")
    print(f"  distinct sub addresses  {len(periods)}  (max periods per address {max(len(v) for v in periods.values())})")
    would = sum(1 for o in orphans if entity[o] == "GREENFIELD" and any(a for _, a in periods[o]))
    print(f"  orphan addresses        {len(orphans)}  (rows {sum(len(periods[o]) for o in orphans)}, {would} would qualify if they had a location)")
    ent = defaultdict(int)
    for said in periods:
        ent[entity[said]] += 1
    print(f"  entity by address       {dict(sorted(ent.items()))}")
    print(f"  max service_eff_date    {max(date.fromisoformat(r[3]) for r in subs)}")
    print("== anchor numbers as at", REPORT_AS_OF, "==")
    print(f"  passings    {P}   (= {len(locs)} - {sum(1 for r in locs if r[7] == '')} blank - {fut} not yet in service)")
    print(f"  subscribers {S}")
    print(f"  penetration {100 * S / P:.2f}%")
    print("== by market ==")
    ratios = []
    for mid in sorted(p):
        ratios.append(s[mid] / p[mid])
        print(f"  {mkt_name[mid]:<16} passings {p[mid]:>5}  subscribers {s[mid]:>4}  penetration {100 * s[mid] / p[mid]:.2f}%")
    print(f"  unweighted mean of market ratios {100 * sum(ratios) / len(ratios):.2f}%  (wrong on purpose)")
    in_2024 = [(ym, me) for ym, me in months if ym.startswith("2024")]
    three = [me for ym, me in months][-3:]
    print(f"  sum of subscribers over the last 3 months {sum(sum(balances(me)[1].values()) for me in three)}  (the sum trap, 3 months)")
    print(f"  sum of passings over {len(in_2024)} months of 2024 {sum(sum(balances(me)[0].values()) for _, me in in_2024)}  (the sum trap)")
    print("== defect A (latest period as of month, counted if active) ==")
    drops = 0
    prev = None
    for ym, me in months:
        _, sd = balances(me, defect=True)
        if prev is not None:
            drops += sum(1 for mid in set(sd) | set(prev) if sd.get(mid, 0) < prev.get(mid, 0))
        prev = sd
    print(f"  market-months where subscribers decrease: {drops}")
    for ym, me in months:
        if ym in ("2022-02", "2022-03", "2022-06", "2022-12", "2023-06", ym_final):
            _, sc = balances(me)
            _, sd = balances(me, defect=True)
            c, d = sum(sc.values()), sum(sd.values())
            print(f"  {ym}  correct {c:>4}  defect {d:>4}  error {100 * (d - c) / c:+.0f}%")
    print(f"== fact grain: {len(months)} months x {len(p)} markets = {len(months) * len(p)} rows, {months[0][0]} to {ym_final}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--check", action="store_true", help="compare a fresh generation to data/csv without writing")
    ap.add_argument("--quiet", action="store_true", help="skip the profile")
    args = ap.parse_args()

    out = Path(__file__).resolve().parent / "csv"
    tables = generate()
    if args.check:
        bad = [t for t, rows in tables.items()
               if not (out / f"{t}.csv").exists() or (out / f"{t}.csv").read_text() != to_csv(rows)]
        print("OK: data/csv matches the generator" if not bad else f"MISMATCH: {', '.join(bad)}")
        return 1 if bad else 0

    out.mkdir(parents=True, exist_ok=True)
    for t, rows in tables.items():
        (out / f"{t}.csv").write_text(to_csv(rows))
    if not args.quiet:
        profile(tables)
    return 0


if __name__ == "__main__":
    sys.exit(main())
