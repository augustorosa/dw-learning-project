#!/usr/bin/env python3
"""
Brindle Fiber accounts payable data, shaped like a NetSuite extract.

Brindle Fiber is a made-up fiber ISP, and every vendor here is made up too.

This is the second source for the optional NetSuite track (Epic 10). It writes
six CSV files into data/csv/netsuite/ that look like what a Fivetran NetSuite
connector lands: NetSuite's own table and column names, plus _fivetran_deleted.
It is NetSuite-shaped, not a faithful copy of NetSuite's schema.

The network build in data/generate_data.py drives the spend. Every location
that was built generated construction, materials and engineering bills for its
service area, so capex follows the build-out month by month.

The traps are the curriculum:

  * transactionline has a mainline row (line 0) per transaction that carries
    the header total with the opposite sign. Sum all lines of a bill and you
    get zero. Sum them unsigned and you get double.
  * bills and payments are many-to-many through nexttransactionlinelink. One
    payment run pays many bills, and big bills are paid in two installments.
  * two vendors bill in CAD. Amounts in foreignamount are in the transaction's
    currency, and each transaction carries its own exchangerate to USD.
  * rows deleted in NetSuite stay in the extract with _fivetran_deleted = true:
    six duplicate bills entered by mistake, and four payments that were
    deleted and re-entered (their link rows are flagged too). In a real
    NetSuite account a voided payment usually stays, with a zero amount or a
    reversing entry. Here they were deleted, which a connector reports as a flag.
  * custcol_bf_service_area is typed by hand. Some capex lines have it blank,
    some in lower case or padded with spaces.
  * bills mix capex (FixedAsset accounts) and opex lines.
  * payment runs continue after the report as-of date, including one on
    2024-09-15, inside the report month.

Determinism: standard library only, seeded with 4242, amounts computed with
Decimal. Re-running produces byte-identical CSVs.

Usage:
    python data/generate_netsuite.py            # writes data/csv/netsuite/*.csv and prints a profile
    python data/generate_netsuite.py --check    # compares a fresh generation to the files on disk
"""

from __future__ import annotations

import argparse
import csv
import io
import random
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_data as gd  # noqa: E402  the network build drives the spend

SEED = 4242
REPORT_AS_OF = gd.REPORT_AS_OF
LAST_BILL_DATE = date(2024, 11, 30)
LAST_RUN_DATE = date(2024, 12, 15)
CENT = Decimal("0.01")

N_DUPLICATE_BILLS = 6        # entered twice by mistake, the copy deleted
N_VOIDED_PAYMENTS = 4        # deleted and re-entered two days later
BLANK_SA_RATE = 0.03         # capex lines with no service area typed
MESSY_SA_RATE = 0.03         # capex lines typed in lower case or padded

# cost per location built, USD, by market: terrain drives it
COST_PER_LOCATION = {1: 1180, 2: 1420, 3: 1760, 4: 960, 5: 1310, 6: 1590}

CURRENCIES = [[1, "USD", "US Dollar"], [2, "CAD", "Canadian Dollar"]]

ACCOUNTS = [
    # id, acctnumber, fullname, accttype
    [1, "1000", "Operating Bank", "Bank"],
    [2, "2000", "Accounts Payable", "AcctPay"],
    [3, "1610", "CIP : Outside Plant Construction", "FixedAsset"],
    [4, "1620", "CIP : Fiber and Materials", "FixedAsset"],
    [5, "1630", "CIP : Engineering and Permitting", "FixedAsset"],
    [6, "6100", "Professional Fees", "Expense"],
    [7, "6200", "Pole Attachment Rent", "Expense"],
    [8, "6300", "Contract Labour", "Expense"],
]
BANK, AP, OSP, MATERIALS, ENGINEERING, PROF_FEES, POLE_RENT, LABOUR = range(1, 9)

VENDORS = [
    # id, entityid, companyname, category, currency id, terms (days)
    [101, "V-0101", "Granitepoint Civil", "Construction", 1, 30],
    [102, "V-0102", "Northway Trenching", "Construction", 1, 30],
    [103, "V-0103", "Tamber Aerial Works", "Construction", 1, 30],
    [104, "V-0104", "Ridgefield Splicing", "Construction", 1, 30],
    [105, "V-0105", "Lakeshore Fibre Supply", "Materials", 2, 45],
    [106, "V-0106", "Maple Conduit Co", "Materials", 2, 45],
    [107, "V-0107", "Keel Engineering", "Engineering", 1, 30],
    [108, "V-0108", "Bluefin Permitting", "Engineering", 1, 30],
    [109, "V-0109", "Oxbow Legal LLP", "Professional services", 1, 30],
    [110, "V-0110", "Crestline Pole Services", "Utilities", 1, 30],
    [111, "V-0111", "Harrow Staffing", "Contract labour", 1, 15],
    [112, "V-0112", "Quarrystone Paving", "Construction", 1, 30],
]
VENDOR = {v[0]: v for v in VENDORS}
# each market has a main civil contractor, and a splicing crew shared by all
CIVIL_BY_MARKET = {1: 101, 2: 102, 3: 103, 4: 101, 5: 112, 6: 102}
SPLICER = 104
MATERIALS_BY_MARKET = {1: 105, 2: 106, 3: 105, 4: 106, 5: 105, 6: 106}
ENGINEERING_BY_MARKET = {1: 107, 2: 107, 3: 108, 4: 107, 5: 108, 6: 108}


def money(x) -> Decimal:
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


def month_start(d: date) -> date:
    return d.replace(day=1)


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def cad_rate_series(rng: random.Random) -> dict[date, Decimal]:
    """A CAD to USD rate for every day, as a bounded random walk."""
    rates, r, d = {}, 0.7550, date(2020, 12, 1)
    while d <= date(2025, 1, 31):
        r = min(0.8000, max(0.7100, r + rng.gauss(0, 0.0018)))
        rates[d] = Decimal(f"{r:.6f}")
        d += timedelta(days=1)
    return rates


def generate() -> dict[str, list[list]]:
    net = gd.generate()
    rng = random.Random(SEED)
    cad = cad_rate_series(rng)

    sa_hub = {r[0]: r[2] for r in net["service_areas"][1:]}
    hub_mkt = {r[0]: r[2] for r in net["hubsites"][1:]}
    sa_mkt = {sa: hub_mkt[h] for sa, h in sa_hub.items()}
    zone_sa = {r[0]: r[2] for r in net["pon_zones"][1:]}

    # ---- when was each location built, by service area and month --------
    built = defaultdict(int)  # (sa, month) -> locations built
    for said, zone, *_rest, isd in net["locations_passed"][1:]:
        sa = zone_sa[zone]
        if isd == "":
            # built, but nobody recorded the in-service date
            m = add_months(date(2021, 4, 1), rng.randint(0, 38))
        else:
            d = date(int(isd[6:]), int(isd[:2]), int(isd[3:5]))
            m = add_months(month_start(d), -rng.randint(1, 3))
        m = max(m, date(2021, 1, 1))
        if m <= date(2024, 11, 1):
            built[(sa, m)] += 1

    # ---- bills -----------------------------------------------------------
    # a bill is (vendor, date, [(account, sa_code or None, usd_amount)])
    bills = []
    months = sorted({m for _, m in built})
    for m in months:
        by_market = defaultdict(list)
        for sa in range(1, 31):
            n = built.get((sa, m), 0)
            if n:
                by_market[sa_mkt[sa]].append((sa, n))
        for mkt, sas in sorted(by_market.items()):
            cpl = COST_PER_LOCATION[mkt]
            # construction: one bill per service area, from the civil contractor,
            # plus a splicing bill for the market covering every area built
            for sa, n in sas:
                amt = n * cpl * 0.70 * rng.uniform(0.85, 1.15)
                lines = [(OSP, sa, amt)]
                if rng.random() < 0.12:
                    lines.append((LABOUR, None, amt * rng.uniform(0.02, 0.06)))  # opex slipped in
                bills.append((CIVIL_BY_MARKET[mkt], m + timedelta(days=rng.randint(3, 27)), lines))
            splice = [(OSP, sa, n * cpl * 0.08 * rng.uniform(0.9, 1.1)) for sa, n in sas]
            bills.append((SPLICER, m + timedelta(days=rng.randint(10, 27)), splice))
            # materials: one CAD bill per market, one line per service area
            mat = [(MATERIALS, sa, n * cpl * 0.16 * rng.uniform(0.9, 1.1)) for sa, n in sas]
            bills.append((MATERIALS_BY_MARKET[mkt], m + timedelta(days=rng.randint(1, 20)), mat))
            # engineering and permitting, billed ahead of the build
            eng = [(ENGINEERING, sa, n * cpl * 0.06 * rng.uniform(0.8, 1.2)) for sa, n in sas]
            eng_date = max(date(2021, 1, 5), add_months(m, -1) + timedelta(days=rng.randint(5, 25)))
            bills.append((ENGINEERING_BY_MARKET[mkt], eng_date, eng))

    # opex that has nothing to do with the build
    m = date(2021, 1, 1)
    while m <= date(2024, 11, 1):
        bills.append((109, m + timedelta(days=rng.randint(5, 25)), [(PROF_FEES, None, rng.uniform(8000, 22000))]))
        bills.append((110, m + timedelta(days=2), [(POLE_RENT, f"SA-{sa:02d}", rng.uniform(900, 2400)) for sa in range(1, 31, 6)]))
        bills.append((111, m + timedelta(days=rng.randint(10, 26)), [(LABOUR, None, rng.uniform(12000, 30000))]))
        m = add_months(m, 1)

    bills = [b for b in bills if b[1] <= LAST_BILL_DATE]
    bills.sort(key=lambda b: (b[1], b[0]))

    # ---- turn bills into transactions and lines --------------------------
    transactions, lines_out = [], []
    tid = 1000
    bill_records = []  # dicts used by the payment runs

    def sa_text(sa):
        if sa is None:
            return ""
        if isinstance(sa, str):
            return sa  # opex lines keep whatever was typed
        code = f"SA-{sa:02d}"
        roll = rng.random()
        if roll < BLANK_SA_RATE:
            return ""
        if roll < BLANK_SA_RATE + MESSY_SA_RATE:
            return rng.choice([code.lower(), f" {code}", f"{code} ", f"sa-{sa:02d} "])
        return code

    def rate_for(vendor_id, d):
        return cad[d] if VENDOR[vendor_id][4] == 2 else Decimal("1")

    def write_bill(vendor_id, d, lines, deleted=False, texts=None):
        nonlocal tid
        tid += 1
        rate = rate_for(vendor_id, d)
        cur = VENDOR[vendor_id][4]
        out_lines, total_f, total_n = [], Decimal(0), Decimal(0)
        texts = texts or [sa_text(sa) for _, sa, _ in lines]
        for i, ((acct, sa, usd), txt) in enumerate(zip(lines, texts), start=1):
            foreign = money(Decimal(str(usd)) / rate)   # the vendor bills in its own currency
            netamt = money(foreign * rate)
            total_f += foreign
            total_n += netamt
            out_lines.append([tid, i, "F", acct, foreign, netamt, txt, "", "true" if deleted else "false"])
        head = [tid, 0, "T", AP, -total_f, -total_n, "", "", "true" if deleted else "false"]
        lines_out.append(head)
        lines_out.extend(out_lines)
        transactions.append([tid, f"BILL-{tid}", "VendBill", d.isoformat(), vendor_id, cur, rate, None,
                             f"{VENDOR[vendor_id][2]} {d:%b %Y}", None, "true" if deleted else "false"])
        return tid, total_f, texts

    for vendor_id, d, lines in bills:
        b_id, total_f, texts = write_bill(vendor_id, d, lines)
        bill_records.append({"id": b_id, "vendor": vendor_id, "date": d, "total": total_f,
                             "open": total_f, "lines": lines, "texts": texts})

    # duplicates entered by mistake, then deleted in NetSuite
    for b in rng.sample(bill_records, N_DUPLICATE_BILLS):
        write_bill(b["vendor"], b["date"], b["lines"], deleted=True, texts=b["texts"])

    # ---- payment runs on the 1st and 15th --------------------------------
    runs, d = [], date(2021, 2, 1)
    while d <= LAST_RUN_DATE:
        runs.append(d)
        d = d.replace(day=15) if d.day == 1 else add_months(d, 1)

    # each bill gets installments: (due run, amount)
    schedule = defaultdict(list)  # run date -> [(bill, amount)]
    for b in bill_records:
        due = b["date"] + timedelta(days=VENDOR[b["vendor"]][5])
        first = next((r for r in runs if r >= due), None)
        if first is None:
            continue  # still open at extraction
        if b["total"] * rate_for(b["vendor"], b["date"]) > 25_000 and rng.random() < 0.30:
            part = money(b["total"] * Decimal("0.6"))
            second = next((r for r in runs if r >= add_months(first, 1)), None)
            schedule[first].append((b, part))
            if second:
                schedule[second].append((b, b["total"] - part))
        else:
            schedule[first].append((b, b["total"]))

    links = []
    payments = []  # (payment id, run date, vendor, total, [(bill id, amount)])
    for run in runs:
        by_vendor = defaultdict(list)
        for b, amt in schedule.get(run, []):
            by_vendor[b["vendor"]].append((b, amt))
        for vendor_id, items in sorted(by_vendor.items()):
            tid += 1
            total = sum(a for _, a in items)
            for b, amt in items:
                b["open"] -= amt
            payments.append([tid, run, vendor_id, total, [(b["id"], a) for b, a in items]])

    # four payments deleted and re-entered two days later, before the as-of date
    voidable = [p for p in payments if p[1] <= REPORT_AS_OF - timedelta(days=30)]
    voided = {p[0] for p in rng.sample(voidable, N_VOIDED_PAYMENTS)}

    def write_payment(pid, run, vendor_id, total, applied, deleted):
        rate = rate_for(vendor_id, run)
        cur = VENDOR[vendor_id][4]
        flag = "true" if deleted else "false"
        transactions.append([pid, f"PMT-{pid}", "VendPmt", run.isoformat(), vendor_id, cur, rate, "Posted",
                             f"Payment run {run:%Y-%m-%d}", None, flag])
        lines_out.append([pid, 0, "T", BANK, -total, -money(total * rate), "", "", flag])
        lines_out.append([pid, 1, "F", AP, total, money(total * rate), "", "", flag])
        for bill_id, amt in applied:
            links.append([bill_id, 0, pid, 0, "Payment", amt, flag])

    for pid, run, vendor_id, total, applied in payments:
        write_payment(pid, run, vendor_id, total, applied, deleted=pid in voided)
        if pid in voided:
            tid += 1
            write_payment(tid, run + timedelta(days=2), vendor_id, total, applied, deleted=False)

    # bill status is as of the extract, not as of any report date
    status = {}
    for b in bill_records:
        status[b["id"]] = ("Paid In Full" if b["open"] == 0 else
                           "Open" if b["open"] == b["total"] else "Partially Paid")
    stamp = datetime(2024, 12, 31, 23, 40)
    for t in transactions:
        if t[2] == "VendBill":
            t[7] = status.get(t[0], "Open")
        t[9] = (datetime.fromisoformat(t[3]) + timedelta(hours=rng.randint(1, 200))).strftime("%Y-%m-%d %H:%M:%S")
        if t[10] == "true":
            t[9] = stamp.strftime("%Y-%m-%d %H:%M:%S")

    transactions.sort(key=lambda t: t[0])
    lines_out.sort(key=lambda r: (r[0], r[1]))
    links.sort(key=lambda r: (r[2], r[0]))

    vendor_rows = [[v[0], v[1], v[2], v[3], v[4], "F", "2021-01-02 09:00:00", "false"] for v in VENDORS]
    return {
        "currency": [["id", "symbol", "name"]] + CURRENCIES,
        "account": [["id", "acctnumber", "fullname", "accttype", "_fivetran_deleted"]]
                   + [a + ["false"] for a in ACCOUNTS],
        "vendor": [["id", "entityid", "companyname", "category", "currency", "isinactive",
                    "lastmodifieddate", "_fivetran_deleted"]] + vendor_rows,
        "transaction": [["id", "tranid", "type", "trandate", "entity", "currency", "exchangerate",
                         "status", "memo", "lastmodifieddate", "_fivetran_deleted"]] + transactions,
        "transactionline": [["transaction", "id", "mainline", "account", "foreignamount", "netamount",
                             "custcol_bf_service_area", "memo", "_fivetran_deleted"]] + lines_out,
        "nexttransactionlinelink": [["previousdoc", "previousline", "nextdoc", "nextline", "linktype",
                                     "foreignamount", "_fivetran_deleted"]] + links,
    }


def to_csv(rows: list[list]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n", quoting=csv.QUOTE_MINIMAL).writerows(rows)
    return buf.getvalue()


# ---- profile: the business rules applied in plain Python ------------------
def profile(ns: dict[str, list[list]]) -> None:
    net = gd.generate()
    sa_hub = {r[0]: r[2] for r in net["service_areas"][1:]}
    hub_mkt = {r[0]: r[2] for r in net["hubsites"][1:]}
    mkt_name = {r[0]: r[1] for r in net["markets"][1:]}
    acct_type = {r[0]: r[3] for r in ns["account"][1:]}

    tx = {r[0]: r for r in ns["transaction"][1:]}
    live = lambda r: r[-1] == "false"  # noqa: E731
    lines = defaultdict(list)
    for r in ns["transactionline"][1:]:
        lines[r[0]].append(r)

    def market_of(text):
        code = text.strip().upper()
        if code.startswith("SA-") and code[3:].isdigit() and 1 <= int(code[3:]) <= 30:
            return hub_mkt[sa_hub[int(code[3:])]]
        return 0

    def allocate(cut, *, use_deleted=False, fx="payment", fan_out=False, include_opex=False):
        """Capex paid by market, payments dated on or before cut."""
        out = defaultdict(Decimal)
        for prev, _, nxt, _, _, amt, deleted in ns["nexttransactionlinelink"][1:]:
            pay, bill = tx[nxt], tx[prev]
            if not use_deleted and (deleted == "true" or pay[10] == "true" or bill[10] == "true"):
                continue
            if date.fromisoformat(pay[3]) > cut:
                continue
            rate = Decimal(str(pay[6])) if fx == "payment" else (Decimal(str(bill[6])) if fx == "bill" else Decimal(1))
            usd = Decimal(str(amt)) * rate
            detail = [l for l in lines[prev] if l[2] == "F" and (use_deleted or l[8] == "false")]
            base = sum(Decimal(str(l[4])) for l in detail)
            for l in detail:
                if acct_type[l[3]] != "FixedAsset" and not include_opex:
                    continue
                share = Decimal(1) if fan_out else Decimal(str(l[4])) / base
                out[market_of(l[6])] += usd * share
        return out

    def dollars(x):
        return f"{x.quantize(Decimal('1'), rounding=ROUND_HALF_UP):,}"

    print("== raw counts ==")
    for t, rows in ns.items():
        print(f"  {t:<24} {len(rows) - 1:>6}")
    txr = ns["transaction"][1:]
    print("== shape ==")
    print(f"  bills {sum(1 for t in txr if t[2] == 'VendBill')} (deleted {sum(1 for t in txr if t[2] == 'VendBill' and t[10] == 'true')})"
          f"   payments {sum(1 for t in txr if t[2] == 'VendPmt')} (deleted {sum(1 for t in txr if t[2] == 'VendPmt' and t[10] == 'true')})")
    print(f"  CAD transactions {sum(1 for t in txr if t[5] == 2)}")
    links = ns["nexttransactionlinelink"][1:]
    per_pay = defaultdict(int)
    per_bill = defaultdict(int)
    for l in links:
        if l[6] == "false":
            per_pay[l[2]] += 1
            per_bill[l[0]] += 1
    print(f"  live links {sum(1 for l in links if l[6] == 'false')}, deleted links {sum(1 for l in links if l[6] == 'true')}")
    print(f"  max bills per payment {max(per_pay.values())}, bills paid in 2 installments {sum(1 for v in per_bill.values() if v > 1)}")
    capex_lines = [l for l in ns["transactionline"][1:] if l[2] == "F" and acct_type[l[3]] == "FixedAsset" and l[8] == "false"]
    print(f"  live capex bill lines {len(capex_lines)}: blank service area {sum(1 for l in capex_lines if l[6] == '')}, "
          f"messy {sum(1 for l in capex_lines if l[6] and l[6] != l[6].strip().upper())}")

    good = allocate(REPORT_AS_OF)
    total = sum(good.values())
    print("== capex paid to date as at", REPORT_AS_OF, "==")
    print(f"  total capex paid     ${dollars(total)}")
    print(f"  unknown market       ${dollars(good[0])}  ({100 * good[0] / total:.2f}%)")
    print(f"  capex per passing    ${dollars(total / 16374)}  (all capex / 16,374 passings)")
    print("== by market ==")
    passings = {1: 2618, 2: 2732, 3: 2288, 4: 4258, 5: 2919, 6: 1559}
    for mid in range(1, 7):
        print(f"  {mkt_name[mid]:<16} capex ${dollars(good[mid]):>12}  passings {passings[mid]:>5}  per passing ${dollars(good[mid] / passings[mid])}")
    attributed = total - good[0]
    print(f"  attributed only ${dollars(attributed)} / 16,374 = ${dollars(attributed / 16374)} per passing")
    print("== wrong numbers ==")
    print(f"  month end instead of as-of   ${dollars(sum(allocate(date(2024, 9, 30)).values()))}")
    print(f"  deleted rows kept            ${dollars(sum(allocate(REPORT_AS_OF, use_deleted=True).values()))}")
    print(f"  CAD treated as USD           ${dollars(sum(allocate(REPORT_AS_OF, fx='none').values()))}")
    print(f"  bill rate, not payment rate  ${dollars(sum(allocate(REPORT_AS_OF, fx='bill').values()))}")
    print(f"  fan-out, no allocation       ${dollars(sum(allocate(REPORT_AS_OF, fan_out=True).values()))}")
    print(f"  opex included                ${dollars(sum(allocate(REPORT_AS_OF, include_opex=True).values()))}")
    billed = sum(Decimal(str(l[5])) for l in capex_lines if date.fromisoformat(tx[l[0]][3]) <= REPORT_AS_OF)
    print(f"  billed (netamount, bill date) ${dollars(billed)}")
    print("== monthly flow check ==")
    for ym in ("2021-06", "2022-12", "2024-08", "2024-09"):
        y, m = map(int, ym.split("-"))
        end = min(add_months(date(y, m, 1), 1) - timedelta(days=1), REPORT_AS_OF)
        start = date(y, m, 1) - timedelta(days=1)
        flow = sum(allocate(end).values()) - sum(allocate(start).values())
        print(f"  {ym} capex paid in month ${dollars(flow)}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Brindle Fiber NetSuite AP generator")
    ap.add_argument("--check", action="store_true", help="compare a fresh generation to data/csv/netsuite without writing")
    ap.add_argument("--quiet", action="store_true", help="skip the profile")
    args = ap.parse_args()

    out = Path(__file__).resolve().parent / "csv" / "netsuite"
    tables = generate()
    if args.check:
        bad = [t for t, rows in tables.items()
               if not (out / f"{t}.csv").exists() or (out / f"{t}.csv").read_text() != to_csv(rows)]
        print("OK: data/csv/netsuite matches the generator" if not bad else f"MISMATCH: {', '.join(bad)}")
        return 1 if bad else 0

    out.mkdir(parents=True, exist_ok=True)
    for t, rows in tables.items():
        (out / f"{t}.csv").write_text(to_csv(rows))
    if not args.quiet:
        profile(tables)
    return 0


if __name__ == "__main__":
    sys.exit(main())
