# The case: Brindle Fiber, Cohort Performance By Market

Brindle Fiber is a made-up fiber internet provider. The company, its six markets and
every number in this repo are synthetic. Any resemblance to a real ISP is coincidental.

This page is the single source of truth for the business rules and the numbers. Stories
quote numbers from here. If a story and this page ever disagree, this page wins and the
story has a bug.

## The ask

Brindle's leadership reads one report page every month: **Cohort Performance By
Market**. For each of six markets it shows three things, as at a report date:

- **Passings**: homes and businesses the network can serve today
- **Subscribers**: of those, how many are paying customers
- **Penetration**: subscribers as a share of passings

Your job is to produce that page, as at **2024-09-13**, from a messy operational source,
and to prove it is right.

## Architecture

```
data/generate_data.py  ->  data/csv/*.csv            (seeded, 21,075 rows)
        |
        |  core track: straight into Snowflake        optional AWS track: RDS Postgres,
        |  (snowflake/raw/load_raw_from_csv.sql)       then your own loader or Fivetran
        v
Snowflake raw    brindle_dev_raw_db.raw
        |            (source columns + _fivetran_synced + _fivetran_deleted)
        |
        |   optional NetSuite track: data/generate_netsuite.py -> data/csv/netsuite/*.csv
        |   -> brindle_dev_raw_db.netsuite (snowflake/raw/load_netsuite_from_csv.sql)
        v
dbt  int layer   (views, brindle_dev_int_db)     integration: cleaning, grain changes
dbt  anl layer   (tables, brindle_dev_anl_db)    analysis: dimensions, the fact, one view
        v
Snowflake semantic view   sv_brindle_by_market
        |-- optional: Cortex agent
        '-- optional: Sigma workbook
```

`raw` is the landed source. `int` means integration. `anl` means analysis. dbt's own
guides call the same three jobs staging, intermediate, and marts.

Snowflake objects (warehouses, databases, roles, the semantic view) are managed by a
**DCM project** if you take the optional platform track. The plain path (BF-70) creates
the three databases and one transform role in SQL. The few things DCM cannot manage (the
deploy warehouse, the admin database, users, the agent) live in `snowflake/bootstrap/`
as plain SQL.

## The source

Six tables. The shape is ugly on purpose, because the ugliness is what you learn from.

| Table | Rows | Grain | What is deliberately wrong with it |
| --- | --- | --- | --- |
| `markets` | 6 | market | nothing, it is the clean one |
| `hubsites` | 12 | hubsite | nothing |
| `service_areas` | 30 | service area | nothing |
| `pon_zones` | 580 | PON zone | nothing |
| `locations_passed` | 18,253 | location | `in_service_date` is text in `MM-DD-YYYY`, and 1,442 rows hold `''`. `address_type` (529), `structure_type` (505) and `hubsite` (575) have blanks too |
| `subscribers` | 2,194 | subscriber **period** | `service_address_id` repeats up to 3 times. 12 addresses match no location |

The hierarchy is `pon_zones` to `service_areas` to `hubsites` to `markets`. A location
belongs to a market through its `pon_zone_id`. The free-text `hubsite` column on
`locations_passed` is a hand-typed copy and is not used for attribution.

In `subscribers`, each row is an order at an address. `is_active = 1` means the order was
installed, `0` means it was cancelled. `entity` says which part of the business owns the
address (`GREENFIELD`, `ACQUIRED` or `WHOLESALE`) and is constant per address.

One story sits behind the subscriber data. In **March 2022** a billing migration
cancelled a batch of existing orders. Those customers re-signed over the following months,
and every one of them had re-signed by the report date. Keep that in mind when you get to
defect A.

## The business rules

These five rules are the curriculum. Every one of them is easy to get slightly wrong.

1. **Blank dates become a future sentinel.** A blank `in_service_date` maps to
   `'12-31-2030'` before parsing. The sentinel is in the future, so those rows fail rule 2
   on their own. No special exclusion branch is needed. Choosing a sentinel that makes the
   rule do the work is the trick.
2. **A location is a passing only if it is in service by the as-of point.** Parsed
   `in_service_date <= as-of point`. For any month, the **as-of point** is
   `least(month_end_date, report_as_of_date)`. For every month before the report month
   that is the month end. For 2024-09 it is **2024-09-13**, not 2024-09-30.
3. **A subscriber counts only if all of these hold**, deduped to one row per
   `service_address_id`:
   - the address resolves to a location (the 12 orphans are excluded)
   - `entity = 'GREENFIELD'`
   - `sum(is_active) >= 1`, meaning at least one order was ever installed
   - `first_active_service_eff_date <= as-of point`, where
     `first_active_service_eff_date = min(case when is_active = 1 then service_eff_date end)`

   Once an address has had an installed order, it counts from that date onward. A later
   cancelled order does not remove it. Churn is out of scope for this model.
4. **Penetration is a ratio of sums, never stored per row.** It is
   `sum(subscribers) / sum(passings)`, computed at query time. Averaging per-market ratios
   weights the 1,559-passing Foxglove Ridge the same as the 4,258-passing Dunmore Plains,
   and gives the wrong answer.
5. **Passings and subscribers are cumulative point-in-time balances**, not monthly flows.
   A month contains all prior months. Summing them across months is meaningless.

## The anchor numbers

Everything reconciles to these three, as at **2024-09-13**:

| Metric | Value |
| --- | --- |
| Passings | **16,374** |
| Subscribers | **1,316** |
| Penetration | **8.04%** |

They were computed three independent ways before this repo was published: in plain Python
inside the generator, in SQL over the CSV files, and in SQL over a Postgres load. All
three agree.

If your number is 16,373 you are not "close". You are wrong, and the cause is knowable.

### By market

| Market | Passings | Subscribers | Penetration |
| --- | ---: | ---: | ---: |
| Foxglove Ridge | 1,559 | 196 | 12.57% |
| Cobalt Hills | 2,288 | 234 | 10.23% |
| Ashford Valley | 2,618 | 244 | 9.32% |
| Briar Coast | 2,732 | 208 | 7.61% |
| Evergreen Lakes | 2,919 | 209 | 7.16% |
| Dunmore Plains | 4,258 | 225 | 5.28% |
| **Total** | **16,374** | **1,316** | **8.04%** |

The unweighted mean of the six market rates is **8.70%**. That is the wrong answer to
"what is our penetration", and it is the answer a naive dashboard or agent gives.

### Reference values the stories check against

| Check | Value |
| --- | --- |
| Source rows, all six tables | 21,075 |
| Blank `in_service_date` | 1,442 |
| Real `in_service_date` after 2024-09-13 | 437 (37 of them between 14 and 30 September 2024) |
| Passings arithmetic | 18,253 − 1,442 blank − 437 not yet in service = 16,374 |
| Distinct subscriber addresses (`int_subscriber` rows) | 1,631 |
| GREENFIELD share of subscriber addresses | 92.8% (1,514 of 1,631) |
| Orphan subscriber addresses | 12 (21 period rows), 11 of which would otherwise qualify |
| `dim_market` rows | 7 (6 plus Unknown) |
| `dim_location` rows | 18,254 (18,253 plus Unknown) |
| `dim_date` rows | 120 (2021-01 to 2030-12) |
| Fact rows | 270 (45 months, 2021-01 to 2024-09, times 6 markets) |
| Sum of passings over the nine months of 2024 | 129,127 (the sum trap) |
| Sum of subscribers over 2024-07 to 2024-09 | 3,062 (the sum trap again, versus the correct 1,316) |

### Defect A, for BF-31

Defect A qualifies each month on the address's latest period as of that month and counts
it only if that period is active. Here is what it does to total subscribers:

| Month | Correct | With defect A | Error |
| --- | ---: | ---: | ---: |
| 2022-02 | 50 | 50 | 0% |
| 2022-03 | 56 | 21 | −62% |
| 2022-06 | 100 | 65 | −35% |
| 2022-12 | 220 | 196 | −11% |
| 2023-06 | 365 | 356 | −2% |
| **2024-09** | **1,316** | **1,316** | **0%** |

The monotonicity test fails on 5 market-months. The report month is exactly right.

## If your number is X, the cause is Y

Every one of these is a real mistake, and each one lands on a distinct number.

| You got | Instead of | Most likely cause |
| --- | --- | --- |
| 16,811 passings | 16,374 | The as-of cutoff does nothing. You excluded blanks but not future dates |
| 16,411 passings | 16,374 | You used the month end (2024-09-30) instead of the as-of date for the report month |
| 18,253 passings | 16,374 | There is no date filter at all |
| 1,327 subscribers | 1,316 | Orphans leaked in. The subscriber-to-location join is outer, not inner |
| 1,419 subscribers | 1,316 | The GREENFIELD filter is missing |
| 1,502 subscribers | 1,316 | You qualified on the first order of any status (`min(service_eff_date)`), so addresses whose orders were all cancelled count |
| 1,533 subscribers | 1,316 | You counted installed order rows, not distinct addresses |
| 8.70% penetration | 8.04% | You averaged the six market rates |
| blank count 0 | 1,442 | The raw load turned `''` into NULL (`empty_field_as_null`) |

---

# Source 2: NetSuite accounts payable (optional track)

Epic 10 adds a second source: vendor bills and payments from Brindle's ERP, shaped like a
NetSuite extract landed by Fivetran. Every vendor is made up. The network build drives the
spend, so capex follows the build-out month by month and market by market.

## The ask

Finance wants **build capex per passing**, by market, as at **2024-09-13**: what has
Brindle paid to build its network, divided by the homes and businesses that network can
now serve.

## The source

Six tables in `brindle_dev_raw_db.netsuite`, with NetSuite's own names.

| Table | Rows | Grain | What will mislead you |
| --- | ---: | --- | --- |
| `currency` | 2 | currency | nothing |
| `account` | 8 | GL account | only `accttype = 'FixedAsset'` is capex |
| `vendor` | 12 | vendor | two vendors bill in CAD |
| `transaction` | 3,204 | bill or payment header | `type` is `VendBill` or `VendPmt`. `exchangerate` is per transaction. `status` is as of the extract. 10 rows are deleted |
| `transactionline` | 9,977 | transaction line | line 0 is the **mainline**: the header total with the opposite sign. Amounts are signed. `custcol_bf_service_area` is typed by hand |
| `nexttransactionlinelink` | 2,359 | bill applied to payment | many-to-many: a payment pays up to 9 bills, and 53 bills are paid in two installments. 10 rows are deleted |

`foreignamount` is in the transaction's own currency. `netamount` is in USD at the
transaction's own rate. On the link table, `foreignamount` is the amount applied, in the
bill's currency.

## The business rules

These carry on from rules 1 to 5 above.

6. **Deleted means gone.** Any row with `_fivetran_deleted = true` is ignored, on every
   table, before anything else happens. That covers six duplicate bills and four payments
   that were deleted and re-entered, plus their lines and links.
7. **Bill detail is `mainline = 'F'`.** Mainline rows restate the header. Include them and
   a bill sums to zero, or to double if you take absolute values.
8. **Capex is lines on `FixedAsset` accounts.** Opex lines, including the ones that sit on
   construction bills, are out.
9. **Capex counts when it is paid, in USD at the payment's rate.** For each live
   application of a live payment to a live bill, `paid_usd = link.foreignamount *
   payment.exchangerate`. The payment date decides the month, and the same as-of point
   applies as for passings: `least(month_end_date, report_as_of_date)`.
10. **A payment is allocated to bill lines by share.** Each line gets `paid_usd *
    line_share`, where `line_share` is the line's `foreignamount` over the sum of
    `foreignamount` on the bill's detail lines, capex and opex together. The allocated
    pieces of one payment application always add back to its `paid_usd`.
11. **The market comes from the service area on the line.** `upper(trim(
    custcol_bf_service_area))` is matched to `SA-01` through `SA-30`. Blank or unmatched
    means the Unknown market. That money is real, so it stays in totals.
12. **Capex per passing is a ratio of sums.** `sum(capex paid to date) / sum(passings)`.
    For the company it uses **all** capex, Unknown included. For a market it uses that
    market's capex, so the six market figures do not add up to the company figure, and
    that is correct.

Capex paid in a month is a **flow**: it adds up across months. Capex paid to date is a
**balance**, like passings: it does not.

## The anchor numbers

As at **2024-09-13**:

| Metric | Value |
| --- | --- |
| Build capex paid to date | **$23,287,443.42** |
| Passings | **16,374** |
| Capex per passing | **$1,422.22** |

Computed two independent ways before publishing: in plain Python inside
`generate_netsuite.py`, and in SQL over the CSV files. They agree to the cent.

### By market

| Market | Capex paid to date | Passings | Capex per passing |
| --- | ---: | ---: | ---: |
| Cobalt Hills | $4,327,352 | 2,288 | $1,891.33 |
| Foxglove Ridge | $2,631,784 | 1,559 | $1,688.12 |
| Briar Coast | $4,118,766 | 2,732 | $1,507.60 |
| Evergreen Lakes | $4,034,597 | 2,919 | $1,382.18 |
| Ashford Valley | $3,259,555 | 2,618 | $1,245.06 |
| Dunmore Plains | $4,325,465 | 4,258 | $1,015.84 |
| Unknown market | $589,924 | 0 | n/a |
| **Total** | **$23,287,443** | **16,374** | **$1,422.22** |

The Unknown market is 2.53% of the dollars and 2.72% of the fact rows.

### Reference values the stories check against

| Check | Value |
| --- | --- |
| Live bills / live payments | 2,320 / 874 |
| CAD transactions | 409 (408 live) |
| Live capex bill lines | 5,392 (146 with a blank service area, 165 typed messily) |
| `int_ap_bill_line` rows | 5,880 |
| `int_ap_payment_application` rows | 2,349 (2,195 dated on or before the as-of date) |
| All cash paid to the as-of date, capex and opex | $25,324,883.93 |
| `int_ap_payment_allocation` rows | 5,900 |
| `fct_ap_capex_payment` rows | 5,406, of which 147 on the Unknown market |
| `dim_vendor` / `dim_gl_account` rows | 13 / 9 (Unknown included) |
| `fct_market_build_economics_monthly` rows | 315 (45 months × 7 market rows) |
| Market-months with capex but no passings yet | 9, excluding the Unknown market |
| Capex paid in 2024-07, 2024-08, 2024-09 | $770,071, $589,194, $167,111 (total $1,526,377) |
| Year-to-date capex paid, 2024 | $6,669,460 |
| Conservation test failures under the fan-out defect | 1,031 |
| Live bills on `fct_ap_bill` | 2,320 |
| Bills with no payment (both later milestone dates null) | 24 |
| Bills paid in full | 2,296 |
| Bills whose first payment date differs from the paid-in-full date | 53 |
| Bills partially paid on the extract | 0 |
| `dim_vendor` rows after the vendor 101 rename (SCD2) | 14 (13 of them current, including Unknown) |
| `fct_ap_cash_monthly` rows | 315 (same spine as the economics fact) |
| Sum of `cash_paid` through the as-of date | $23,287,443.42 |

## If your number is X, the cause is Y

| You got | Instead of | Most likely cause |
| --- | --- | --- |
| $11,643,722 | $23,287,443 | Mainline rows leaked into the `line_share` denominator as absolute values, so every share is halved. Signed, they make it zero and the query divides by zero |
| $51,313,872 | $23,287,443 | Fan-out: each bill line got the whole payment instead of its share |
| $25,324,884 | $23,287,443 | Opex lines were not filtered out |
| $24,740,578 | $23,287,443 | CAD amounts were added up as if they were USD |
| $23,407,085 | $23,287,443 | You measured capex **billed** by bill date (or "Paid In Full" bills dated on or before the as-of date), not capex **paid** by payment date |
| $23,382,345 | $23,287,443 | Deleted rows were kept. The four re-entered payments count twice |
| $23,315,567 | $23,287,443 | You used the month end, so the 2024-09-15 payment run slipped in |
| $23,291,769 | $23,287,443 | You converted at the bill's exchange rate, not the payment's |
| $22,697,520 | $23,287,443 | An inner join dropped the Unknown market's spend |
| $1,455.02 per passing | $1,422.22 | You averaged the six market ratios |
| $186,204,753 for 2024 | $6,669,460 | You added up capex **to date** across months. Sum capex **in month** instead |

