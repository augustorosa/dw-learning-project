# Gotchas: if you see X, the cause is Y

Fourteen traps the reference build actually hit, A to N. A is the most important, and the
rest are roughly in the order you will meet them. Roughly half the calendar time on the
original build went into these. Five more, O to S, come with the optional NetSuite track.
They are planted in its data, and they are the ones ERP models fall into most often.

Read this once before you start, so the symptoms look familiar. Come back the moment
something behaves oddly.

The common thread: **most of these do not fail where they break.** Several return a
success response, several point at the wrong thing, and one produces a correct-looking
number over wrong data. Treat a green result as weak evidence.

| # | Symptom | Cause | Stories |
| --- | --- | --- | --- |
| A | Green build, correct headline, wrong history | "Current record" logic instead of first installed order | BF-22, BF-26, BF-31 |
| B | `unknown_rate` fails on a clean dimension | Test placed on a dimension key, not a fact FK | BF-29, BF-30 |
| C | `NON ADDITIVE BY` errors on one term only | Unqualified columns bound to the fact | BF-40 |
| D | `snow dcm plan`: insufficient privileges on your own role | DCM `DEFINE`s the project owner role | BF-04 |
| E | Query acceleration silently off | DCM reverted an undeclared property to its default | BF-06 |
| F | Agent will not deploy through DCM | `AGENT` is not a supported entity | BF-05, BF-43 |
| G | `{"valid": true}`, then `Unknown column` in every cell | Bare column refs on a `warehouse-table` source | BF-49, BF-51 |
| H | `Invalid kind: "table"` | A field inside the element failed the union | BF-50 |
| I | "Warehouse table not found" on a view you just made | Sigma's inventory is cached | BF-48 |
| J | `Invalid access/refresh token` with valid credentials | Wrong Sigma API region | BF-47 |
| K | Postgres 18.x instead of 16.x | `--engine-version` omitted | BF-09 |
| L | DB subnet group creation fails | Needs two AZs even for single-AZ | BF-02 |
| M | `USE ROLE` fails with a permissions error | Role-restricted PAT | BF-16 |
| N | Replication slot gone, LSN reset | Source is restored nightly | BF-12, BF-34 |
| O | Every bill adds up to zero | Mainline rows included | BF-58, BF-61 |
| P | Capex paid is more than double what was billed | Many-to-many fan-out between payments and bill lines | BF-64, BF-66 |
| Q | Capex off by millions, or by a few thousand | CAD treated as USD, or converted at the wrong rate | BF-62, BF-66 |
| R | Capex paid slightly too high, no error anywhere | Deleted NetSuite rows kept | BF-60, BF-65 |
| S | Capex per passing looks cheap, total capex is short | Inner join dropped the Unknown market | BF-67, BF-68 |

Three environment items follow at the end: the `BRINDLE_` prefix, the permissive `layers`
default, and `empty_field_as_null`.

---

## A. Green build, correct headline number, wrong history

**If you see** a green `dbt build`, a reconciliation that lands exactly on
16,374 / 1,316 / 8.04%, and no failing tests, but subscriber counts in 2022 are too low,
**the cause is** qualifying each month on the address's *current* record (its latest
period on or before the as-of point, found with `max(service_eff_date)`) and counting it
only if that period is active. The rule is to qualify on the first **installed** order:
`min(case when is_active = 1 then service_eff_date end)`.

"Current record" logic looks sensible, and that is why it survives review. In this
dataset a billing migration in March 2022 cancelled a batch of orders, and those
customers re-signed months later. Under the current-record logic they disappear from
every month in between:

| Month | Correct | With defect | Error |
| --- | ---: | ---: | ---: |
| 2022-03 | 56 | 21 | −62% |
| 2022-12 | 220 | 196 | −11% |
| 2024-09 | 1,316 | **1,316** | **0%** |

Look at the last row. Every one of those customers had re-signed by September 2024, so
the defect is **invisible at the report month**, which is exactly where the
reconciliation was being checked. Every surface agreed. The build was green. The headline
was right. The history was wrong.

**Fix:** compute `first_active_service_eff_date` in `int_subscriber` and qualify on it in
the fact.

**Why it stayed hidden:** nothing tested the *shape* of the series. Passings and
subscribers are cumulative balances, so they can never go down month over month. That
invariant is one short singular test, `assert_balances_are_non_decreasing.sql`, and it
fails immediately.

> **A correct total does not imply a correct series. Test the invariant, not the endpoint.**

**And its limit.** A different bug, using `max(service_eff_date)` over all periods as a
fixed start date, also undercounts history but never makes a series go down, so the
monotonicity test passes right over it. An invariant only catches what violates it. A
month-by-month comparison against a hand-written source query (BF-53) catches the rest.

BF-31 has you reintroduce defect A on purpose. It is the best lesson in the project.

---

## B. `unknown_rate` fails on a dimension that is perfectly clean

**If you see** `unknown_rate` failing at 14.3% on `dim_market.market_key` when
`dim_market` is correct, **the cause is** the test being placed on a dimension key instead
of a fact FK.

`dim_market` has 6 markets plus 1 designed Unknown row. 1/7 is 14.3%, over the 5%
threshold. It fails **by construction**, and would fail on any small dimension. A
three-member dimension would read 25%.

The category error: the Unknown member is a *designed row* in a dimension, so its presence
there says nothing about data quality. On a **fact FK** the same value means a join did
not resolve, which is exactly what the test is for.

**Fix:** apply `unknown_rate` to the fact's `market_key` and `date_key`, and to no
dimension key. On correct data every FK reads 0%, not merely under 5%.

**Generalises to:** a test in the wrong place is not a weak test, it is a meaningless one.
Before writing a test, say out loud where the defect would show up.

---

## C. `NON ADDITIVE BY` errors on one column and accepts two wrong ones

**If you see** `NON ADDITIVE BY (year_month, month_end_date, year_number)` raise an error
naming only `year_number`, **the cause is** that unqualified names resolved against the
**fact**, and the fact has columns called `year_month` and `month_end_date` but not
`year_number`.

So two of three terms bound silently to the wrong table, and the one error pointed at the
least interesting term. Fix only `year_number` and you get a view that compiles and
computes balances against the fact's own date columns instead of the calendar's.

**Fix:**

```sql
NON ADDITIVE BY (calendar.year_month, calendar.month_end_date, calendar.year_number)
```

Table-qualify every term, always, even when it looks redundant.

**Generalises to:** an error on one of three terms tells you nothing about the other two.
**The unqualified form compiles and is wrong.**

---

## D. `snow dcm plan` says you lack privileges on your own role

**If you see**

```
Insufficient privileges to operate on role X.
Your primary role X must have OWNERSHIP granted on ROLE X
```

**the cause is** that the DCM project `DEFINE`s the project owner role, so DCM has to
operate on that role as an object, and managing an object requires owning it. It reads
like nonsense. It is not.

**Fix:**

```sql
GRANT OWNERSHIP ON ROLE brindle_deployer_rl TO ROLE brindle_deployer_rl COPY CURRENT GRANTS;
```

The deployer role also needs `MANAGE GRANTS ON ACCOUNT`, `IMPORTED PRIVILEGES ON DATABASE
SNOWFLAKE`, and `USAGE` on a warehouse it can actually use (`brindle_deploy_wh`).

All of this belongs in `snowflake/bootstrap/01_bootstrap.sql`, with a comment. The
self-ownership grant looks like a copy-paste mistake, and somebody will "clean it up".

---

## E. Query acceleration turns itself off with no diff to point at

**If you see** query acceleration disabled on a warehouse after a DCM deploy, **the cause
is** that the warehouse definition does not declare `enable_query_acceleration`, and DCM
set the undeclared property back to the engine default.

In a declarative tool, an omitted property does not mean "leave it alone". It means "set
it to the default". On the reference build's account that default differed from what the
warehouse had, so the deploy flipped it silently. Because the property was never in the
declaration, there was nothing in the plan diff to notice.

**Fix:** declare every property on every warehouse, including ones equal to the default.
Then `snow dcm plan` reports no drift, and any future change shows up in a diff.

**The real answer** is stretch goal 4: run `snow dcm plan` in CI on every pull request. A
silent revert is only invisible if nobody is diffing.

---

## F. The agent will not deploy through DCM

**If you see** DCM refuse to manage an `AGENT` or a `USER`, **the cause is** that they are
not DCM-supported entities. Semantic View is supported (in preview at the time of
writing). `AGENT` and `USER` are not.

**Fix, which is an architecture decision rather than a workaround:** the semantic view goes
in `snowflake/dcm_project/sources/definitions/12_semantic_views.sql`. The agent and any
service users go in `snowflake/bootstrap/` as plain SQL.

**Generalises to:** read the Supported Entities table *before* you design your object
management, not after a failed deploy. This one shaped the whole repo layout.

---

## G. `{"valid": true}`, then `Unknown column` in every single cell

**If you see** a Sigma workbook that passes `spec/verify`, creates successfully, and then
shows `Unknown column "[MARKET_NAME]"` in every cell, **the cause is** bare column
references against a `warehouse-table` source.

Physical columns on a `warehouse-table` source must be **table-prefixed**:

```
[V_BY_MARKET_CURRENT/MARKET_NAME]     <- resolves
[MARKET_NAME]                          <- passes verify, renders nothing
```

`spec/verify` checks the spec's **shape**. It does not resolve column references against
the warehouse. `{"valid": true}` means "well-formed", not "correct".

**Fix:** table-prefix every physical column reference in `sigma/workbook_by_market.json`.

**And change your habit:** the only way to know is to create the workbook and **export its
data**. Verify at the output, not at the gate. It is the same shape of error as A: a
success signal over wrong content.

---

## H. `Invalid kind: "table"` when the kind is obviously `table`

**If you see** Sigma return `Invalid kind: "table"` on an element whose kind is correctly
`table`, **the cause is** that some field *inside* the element failed the discriminated
union, and the validator can only report the discriminator it used to pick the branch. It
never means the kind is wrong.

**How the reference build found it:** bisection, with `sigma/bisect_spec.py`. Submit
smaller and smaller specs until the error disappears, then add fields back one at a time.
Source, columns, `format` and `groupings` all validate. **Element-level `filters` on a
table element does not.**

**Fix, which is better than a fix:** push the month restriction into a dbt view,
`v_by_market_current`, and remove `filters` from the Sigma element. A filter in dbt can
carry a test. A filter buried in a workbook spec cannot. Sigma stays presentation only, and
the constraint pushed the design somewhere better.

**Generalises to:** on a union-type validation error, the named field is where the
validator gave up, not where you went wrong. Bisect.

---

## I. "Warehouse table not found" on a view you created two minutes ago

**If you see** Sigma unable to find a brand-new view while older tables in the same schema
resolve fine, **the cause is** Sigma's cached connection inventory.

**Fix:**

```
POST /v2/connections/{connectionId}/sync
{"path": ["BRINDLE_DEV_REPORTING_DB", "ANL"]}
```

Make this part of the deploy path, not a manual step you remember after ten confused
minutes.

**Telling it apart from G:** this one fails when the table is *referenced* ("not found").
G gets past the reference and fails when the workbook *renders* ("Unknown column").

---

## J. Valid credentials, `Invalid access/refresh token`

**If you see**

```json
{"code":"invalid_request","message":"Invalid access/refresh token"}
```

from the Sigma API with credentials you know are good, **the cause is** the wrong API
region. The region cannot be worked out from the credentials, and every wrong region
returns this exact message. It reads like a credential problem and sends you off to rotate
a secret that was fine.

**Fix:** confirm your organization's API base URL before touching the credentials. When
this error appears, change the region first. It costs one request.

---

## K. RDS gave you a much newer Postgres

**If you see** an RDS instance running a newer Postgres than you intended, **the cause
is** leaving `--engine-version` off `aws rds create-db-instance`. The default is the newest
supported version, and it moves. The reference build got 18.3. Newer than your ingestion
tool supports means you find out at connector setup, not at provisioning.

**Fix:** pin it. `aws/provision.sh` sets `--engine-version` explicitly to a 16.x release.

---

## L. DB subnet group creation fails on a single-AZ instance

**If you see** `create-db-subnet-group` rejected, or an RDS create failing on subnet
coverage, even though you passed `--no-multi-az`, **the cause is** that DB subnet groups
need subnets in **at least two availability zones** whatever the instance's multi-AZ
setting.

**Fix:** use a VPC with subnets in two or more AZs. In the reference build, two of three
candidate VPCs were single-AZ and simply unusable. Check this first. It is a five-second
query that saves an hour.

---

## M. `USE ROLE` fails with a permissions error on a valid PAT

**If you see** a PAT authenticate and then fail on `USE ROLE` with a confusing permissions
message, **the cause is** that the PAT is restricted to a different role. The token is
valid and authentication worked. It is the role switch that is blocked, and the error
describes a privilege problem instead of a token restriction.

**Fix:** issue an unrestricted PAT, or restrict it to exactly the role dbt uses. dbt takes
the PAT in the `password:` field of `profiles.yml`.

**Related, and worse:** do **not** use `authenticator: externalbrowser` for anything
unattended. It waits on a browser prompt instead of failing, so a scheduled run appears to
be running forever.

---

## N. Replication slot gone, LSNs reset, `xmin` unreliable

**If you see** CDC from the Postgres source breaking every day, **the cause is** that the
source is **restored nightly from backup**. A restore destroys replication slots and
resets LSNs. `xmin` and `ctid` are not stable across it either, so no incremental-key
strategy survives.

**Fix, which is a strategy decision:** a daily **full-table** sync, plus a `dbt snapshot`
with `strategy='check'` to rebuild the history the source no longer carries.

**Generalises to:** ingestion strategy is dictated by how the source is operated, not by
preference. Someone will propose CDC as an improvement. The decision record from BF-12
exists to answer them.

---

## Environment items that are not errors but will bite you

### The `BRINDLE_` prefix

**If you see** a role, warehouse or database behaving strangely (grants you did not make,
a role that already existed), **the cause is** an unprefixed generic name colliding with
somebody else's object.

The reference build ran in a shared account with **182 databases**. A name like
`deployer_rl` does not fail loudly. It resolves to an existing object and starts working,
and you are now changing someone else's role.

**Fix:** prefix everything `BRINDLE_`, centralised in
`snowflake/dcm_project/sources/macros/naming_macro.sql`. On a shared account the prefix is
not tidiness. It is a safety mechanism.

### Omitting `layers` grants raw rather than withholding it

**If you see** `brindle_bi_rl` able to read the raw database, **the cause is** a
functional role that does not declare `layers`. The default is **permissive**, not
restrictive. `brindle_bi_rl` must declare `layers: [int, anl]`.

**And the point:** do not read the yml and conclude it is fine. Assert the negative case.
Open a session as `brindle_bi_rl`, query a raw table, and confirm you get "Object does
not exist or not authorized" (BF-08). An access control you have not tested negatively is
an access control you have not tested.

### `empty_field_as_null = false`

**If you see** `select count(*) from locations_passed where in_service_date = ''` return
**0** in Snowflake when the source has **1,442**, **the cause is** the CSV load turning
empty strings into NULL. Snowflake's default is `empty_field_as_null = true`.

In this dataset `''` versus NULL is the **entire** data-quality signal: 1,442 blank dates,
529 blank `address_type`, 505 blank `structure_type`, 575 blank `hubsite`. Coerce them and
the `int` layer has nothing to clean, the `'N/A'` logic never fires, and the project
quietly loses its subject. Nothing errors. The row count is still 18,253.

**Fix:** `empty_field_as_null = false` on the file format, as in
`snowflake/raw/load_raw_from_csv.sql`. Check the 1,442 count in Snowflake after
every load, not just at the source.

---

## NetSuite track: O to S

### O. Every bill adds up to zero

**If you see** a bill, or all bills, summing to exactly 0, or a bill total that is exactly
double, **the cause is** the mainline. Line 0 of every NetSuite transaction
(`mainline = 'T'`) restates the header total with the opposite sign, so it cancels the
detail lines. Take absolute values to "fix" the zero and you get double instead.

Inside the allocation it shows up differently. Leave mainline rows in the `line_share`
denominator and it sums to zero, so the query divides by zero. Take absolute values there
and every share halves, and capex comes out at $11,643,722.

**Fix:** `mainline = 'F'` in `int_ap_bill_line`, and nowhere else needs to know mainline
rows exist.

### P. Capex paid is more than double what was billed

**If you see** capex paid of $51,313,872 when bills only total about $23.4M, **the cause
is** a fan-out. A payment links to bills, and a bill has several lines, so joining payment
applications straight to bill lines repeats each payment once per line.

**Fix:** allocate. Each line gets `paid_usd * line_share`. Then prove it with the
conservation test: for every payment application, the allocated pieces add back to what
was paid.

**Generalises to:** when a join crosses a many-to-many, money needs a rule for how it
splits, and a test that the split conserves it.

### Q. Capex off by millions, or by a few thousand

**If you see** $24,740,578, **the cause is** adding CAD amounts to USD amounts. Two
vendors bill in CAD, and `foreignamount` is in the transaction's own currency.

**If you see** $23,291,769, a few thousand high, **the cause is** converting at the bill's
exchange rate instead of the payment's. Both rates are real. The question, "what have we
paid?", picks the payment's.

The second one is the dangerous one. It conserves cash, passes every test, and is off by
less than 0.02%. Only a hand-written reconciliation catches it.

### R. Capex paid slightly too high, and nothing errors

**If you see** $23,382,345, **the cause is** NetSuite rows that were deleted but kept.
Fivetran does not remove a row deleted in the source. It sets `_fivetran_deleted = true`.
Four payments were deleted and re-entered, so without the filter they are paid twice. (In a
real NetSuite account a voided payment usually stays, with a zero amount or a reversing
entry, so check how your own connector reports voids.) Six
duplicate bills were deleted too. They have no payments, so they only show up if you
measure billed amounts.

**Fix:** filter `not _fivetran_deleted` on every NetSuite table you read, in the `int`
layer, and test that no deleted transaction reaches the fact.

### S. Capex per passing looks cheap, and total capex is short

**If you see** total capex of $22,697,520 and $1,386.19 per passing, **the cause is** an
inner join between capex and passings. The Unknown market has capex ($589,924 of lines
nobody tagged with a service area) and no passings, so an inner join drops it without a
word.

**Fix:** build the grain from the dimensions (every month crossed with every market,
Unknown included) and **left** join each fact's aggregate onto it. That is drill-across
done properly.

**Generalises to:** before any join between two facts' worth of data, ask what exists on
one side and not the other. Here it is unattributed spend on one side, and on the other,
months before any capex was paid.

---

## The pattern across the first fourteen

Nine of them produce a **misleading success or a misdirected error**:

- **A**: green build, correct headline, wrong history
- **B**: a real failure pointing at the wrong object
- **C**: one error term hiding two silent ones
- **D**: a privilege error that reads like nonsense
- **E**: a change with no diff at all
- **G**: `{"valid": true}` over a workbook that renders nothing
- **H**: an error naming the one field that was fine
- **J**: a region problem wearing a credential error's clothes
- **M**: a token restriction wearing a privilege error's clothes

So the habit to build is narrow and specific: **decide what observable outcome would prove
the thing works, and check that. Not the status code, not the validator, not the total.**

Every story in the backlog ends with a **Verification** for exactly this reason.

The NetSuite five add a variation: none of them raises an error. O, P and R move money by
large amounts that a reconciliation spots quickly. The bill-rate half of Q and the Unknown
spend in S are off by a small amount, and small errors in money are the hardest to notice
and the most expensive to explain later.

## Fixed in this version: the as-of cutoff used to test nothing

In the original seed data every real `in_service_date` fell on or before 2024-09-01, a
fortnight before the as-of date. So `18,253 − 1,442 blanks = 16,811` exactly, and the
`in_service_date <= as-of` rule excluded nothing on its own. You could delete the
comparison and every test would still pass and every number would still reconcile. It was
found by querying an assumption instead of trusting the brief.

The generator now plants 437 locations with real dates after the as-of date, 37 of them
inside September 2024. The cutoff has something to bite on, and a missing or wrong cutoff
now lands on a distinct wrong number (16,811 or 16,411, see
[`BUSINESS_RULES.md`](BUSINESS_RULES.md)).
