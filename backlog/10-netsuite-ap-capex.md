# Epic 10: A second source, NetSuite AP and capex per passing (optional track)

Stories BF-58 to BF-69, then BF-79 to BF-81. Anchor numbers as at **2024-09-13**: **$23,287,443 build capex
paid, 16,374 passings, $1,422.22 capex per passing**. The rules and the wrong-number
table are in [`docs/BUSINESS_RULES.md`](../docs/BUSINESS_RULES.md), under "Source 2".
Traps O to S are in [`docs/GOTCHAS.md`](../docs/GOTCHAS.md).

Start this track after Epic 4. You need the passings fact, the macros, the Unknown member
pattern and the testing habits from the core track, because this epic leans on all of
them. The last story, BF-69, also needs the semantic view from Epic 6, and its evals need
the agent track.

**The question.** Finance wants to know what each home passed has cost to build, by
market. The spend lives in NetSuite as vendor bills and payments. The passings live in
your fact. Nothing joins them except the conformed dimensions you already built.

---

### BF-58: Land the NetSuite source
**As a** data engineer **I want** the NetSuite AP tables landed next to the network data **so that** there is a second source to model against the same dimensions.

**Learning objective:** a second connector means a second raw contract. An ERP connector lands the ERP's own table names and reports deletes as a flag, not by removing rows.

**Acceptance criteria**
- [ ] `snowflake/raw/load_netsuite_from_csv.sql` has been run as `brindle_ingest_rl`, loading six tables into `brindle_dev_raw_db.netsuite`.
- [ ] You have run `python data/generate_netsuite.py --check` and it passes.
- [ ] Every table has `_fivetran_synced` and `_fivetran_deleted`, and you can say what `_fivetran_deleted = true` means for a NetSuite row.
- [ ] The load's own last check, the sum of every bill line, returns `0.00`, and you can explain why in `NOTES.md` before reading GOTCHA O.

**Verification:** the load prints `currency` 2, `account` 8, `vendor` 12, `transaction` 3204, `transactionline` 9977, `nexttransactionlinelink` 2359, then **10** deleted transactions and a bill-line sum of **0.00**.

**Estimate:** S  ·  **Track:** netsuite  ·  **Depends on:** BF-13 or BF-71, BF-35

---

### BF-59: Profile the ERP data before modelling
**As a** data engineer **I want** a written profile of the NetSuite tables **so that** every rule in the AP models traces to something I measured.

**Learning objective:** ERP data is clean in a different way from operational data. The types are right and the values are tidy, but the structure (header rows, signed amounts, link tables, currencies, soft deletes) will mislead anyone who has not looked.

**Acceptance criteria**
- [ ] Transaction types counted: 2,326 `VendBill` (6 deleted) and 878 `VendPmt` (4 deleted).
- [ ] The mainline convention described: line 0 of every transaction has `mainline = 'T'` and carries the header total with the opposite sign.
- [ ] Currencies measured: 409 transactions are in CAD, from two vendors (Lakeshore Fibre Supply, Maple Conduit Co), each transaction with its own `exchangerate`.
- [ ] Link cardinality measured in both directions: one payment covers up to 9 bills, and 53 bills were paid in two installments.
- [ ] Capex lines measured: 5,392 live bill lines post to `FixedAsset` accounts. 146 have a blank `custcol_bf_service_area` and 165 more are typed in lower case or padded.
- [ ] Timing measured: 62 live payments are dated after 2024-09-13, starting with the 2024-09-15 run.
- [ ] Findings recorded in `NOTES.md`, each with its query.

**Verification:** `select max(n) from (select nextdoc, count(*) n from nexttransactionlinelink where not _fivetran_deleted group by 1)` returns **9**. `select count(*) from (select previousdoc from nexttransactionlinelink where not _fivetran_deleted group by 1 having count(*) > 1)` returns **53**. Blank service areas on live `FixedAsset` bill lines count **146**.

**Estimate:** M  ·  **Track:** netsuite  ·  **Depends on:** BF-58

---

### BF-60: Declare the second source
**As a** data engineer **I want** the NetSuite tables declared as a dbt source with its own freshness policy **so that** models reference them symbolically and a stalled ERP sync is visible.

**Learning objective:** sources are per connector, and freshness is set per source from that source's cadence. There is no global "ignore deleted rows" switch on a dbt source, so where that filter lives is a design decision.

**Acceptance criteria**
- [ ] `dbt/models/int/_sources_netsuite.yml` declares source `netsuite` with all six tables and a description on each.
- [ ] `loaded_at_field: _fivetran_synced`. In this scenario the ERP syncs every six hours, so freshness warns at 12 hours and errors at 24. A comment says why the numbers differ from the network source's 48 hours.
- [ ] A comment records the decision on deletes: `_fivetran_deleted` is filtered in the `int` layer, in every model that reads a NetSuite table, and nowhere later.

**Verification:** `dbt ls --select source:netsuite` lists **6** tables. `dbt source freshness --select source:netsuite` passes on freshly loaded data.

**Estimate:** S  ·  **Track:** netsuite  ·  **Depends on:** BF-58, BF-19

---

### BF-61: `int_ap_bill_line`
**As a** data engineer **I want** one clean row per bill detail line, with its share of the bill and its market **so that** payments can be allocated without anyone touching a mainline row again.

**Learning objective:** isolating an ERP's structural quirks in one model. After this model, nobody downstream needs to know that mainline rows exist, that deletes are flags, or that service areas are typed by hand.

**Acceptance criteria**
- [ ] Reads `transaction`, `transactionline` and `account` via `source()`, keeping only live rows (`not _fivetran_deleted` on every table read), `type = 'VendBill'` and `mainline = 'F'`.
- [ ] `is_capex` is true when the line's account has `accttype = 'FixedAsset'`.
- [ ] `line_share` is the line's `foreignamount` divided by the sum of `foreignamount` over the bill's detail lines. Shares use `foreignamount` because every line of a bill is in the same currency.
- [ ] `service_area_code` is `upper(trim(custcol_bf_service_area))`, blank mapped to `'N/A'` with your `coalesce_to_unknown` macro.
- [ ] The market is resolved by matching the code to `'SA-' || lpad(service_area_id, 2, '0')` through `int_market_hierarchy`. An unmatched or `'N/A'` code leaves the market unresolved here. It becomes the Unknown member in the fact.
- [ ] No row is dropped for being opex. Filtering to capex is the fact's job.

**Verification:** `select count(*), count_if(is_capex), count(distinct bill_id) from int_ap_bill_line` returns **5880**, **5392**, **2320**. `select count(distinct service_area_code) from int_ap_bill_line where is_capex` returns **31** (30 areas plus `'N/A'`). No bill has `abs(sum(line_share) - 1) > 0.000001`.

**Estimate:** M  ·  **Track:** netsuite  ·  **Depends on:** BF-60, BF-20, BF-22

---

### BF-62: `int_ap_payment_application`
**As a** data engineer **I want** one row per payment applied to a bill, in USD **so that** cash paid is modelled once, at the rate it was actually paid.

**Learning objective:** link tables, and choosing an exchange rate on purpose. The applied amount is in the bill's currency. Converting it at the **payment's** rate measures the cash that left the bank, which is what a capex-paid question is asking.

**Acceptance criteria**
- [ ] Reads `nexttransactionlinelink` joined to the payment in `transaction`, keeping live links to live `VendPmt` rows only.
- [ ] Carries `bill_id`, `payment_id`, `payment_tranid`, `payment_date`, `vendor_id`, and `paid_usd = foreignamount * payment.exchangerate`, with no rounding.
- [ ] A comment explains why the payment rate and not the bill rate, and names the size of the difference (see the wrong-number table).
- [ ] A comment states the cardinality: one payment to many bills, one bill to at most two payments.

**Verification:** `select count(*) from int_ap_payment_application` returns **2349**. Filtered to `payment_date <= '2024-09-13'` it returns **2195** rows and `round(sum(paid_usd), 2)` of **25324883.93**: every dollar paid, capex and opex together.

**Estimate:** M  ·  **Track:** netsuite  ·  **Depends on:** BF-60

---

### BF-63: `dim_vendor` and `dim_gl_account`
**As a** data engineer **I want** vendor and GL account dimensions **so that** the capex fact can be sliced by who was paid and what for.

**Learning objective:** dimensions from a second source follow the same pattern as the first. Same surrogate key macro, same Unknown member, same scaffold. Consistency across sources is what makes a warehouse feel like one thing.

**Acceptance criteria**
- [ ] `dim_vendor` from `vendor` (live rows only), with category and currency code joined from `currency`, and an Unknown row keyed `'0'`.
- [ ] `dim_gl_account` from `account`, with an `is_capex` flag (`accttype = 'FixedAsset'`) and an Unknown row keyed `'0'`.
- [ ] Both use `utils_surrogate_key` and carry the seven-block scaffold.

**Verification:** `select count(*) from dim_vendor` returns **13**, and `select count(*) from dim_gl_account` returns **9**, of which `count_if(is_capex)` is **3**.

**Estimate:** S  ·  **Track:** netsuite  ·  **Depends on:** BF-60, BF-24

---

### BF-64: `fct_ap_capex_payment`, via an allocation model
**As a** data engineer **I want** a transaction fact of capex paid, allocated down to the bill line **so that** every dollar paid lands on the market and GL account it was spent on.

**Learning objective:** allocation as the fix for a many-to-many join. A payment knows its bills, and a bill knows its lines, but a payment does not know its lines. Joining them directly fans out. Allocating by line share turns the many-to-many into a clean, additive grain.

**Acceptance criteria**
- [ ] `dbt/models/int/int_ap_payment_allocation.sql` joins each payment application to **every** detail line of its bill (capex and opex) and computes `allocated_usd = paid_usd * line_share`. Grain: one row per payment application and bill line.
- [ ] `dbt/models/anl/fct_ap_capex_payment.sql` keeps `is_capex` rows only. Grain is the same as the allocation model.
- [ ] FKs: `vendor_key`, `gl_account_key`, `market_key` (`'0'` when unresolved) and `date_key` for the **payment** month. `dim_date` is month grain, so the payment date itself travels as a degenerate column, with `payment_tranid` and `bill_tranid`.
- [ ] The measure is `paid_usd`: the allocation model's `allocated_usd`, renamed. Not the allocation model's `paid_usd`, which is the whole payment and would bring the fan-out straight back. Never rounded inside the model. Round only when you present a number.
- [ ] Every payment loaded is in the fact, including those after the as-of date. The as-of cutoff is a query-time rule, applied downstream.
- [ ] Full seven-block scaffold.

**Verification:** `select count(*) from int_ap_payment_allocation` returns **5900**. `select count(*) from fct_ap_capex_payment` returns **5406**. `select round(sum(paid_usd), 2) from fct_ap_capex_payment where payment_date <= '2024-09-13'` returns **23287443.42**. By market it matches the table in `docs/BUSINESS_RULES.md` to the dollar, with **589924** on the Unknown market.

**Estimate:** L  ·  **Track:** netsuite  ·  **Depends on:** BF-61, BF-62, BF-63, BF-25

---

### BF-65: Tests for the capex fact
**As a** data engineer **I want** the allocation, grain and join quality of the capex fact under test **so that** the ways ERP models usually break fail the build.

**Learning objective:** the conservation invariant. Whatever you do to split money up, the pieces must add back to the whole. It is the AP version of "balances never go down". And a second look at `unknown_rate`, this time on a fact where the Unknown member carries real money.

**Acceptance criteria**
- [ ] `dbt/tests/assert_payment_allocations_conserve_cash.sql` returns any payment application where `abs(sum(allocated_usd) - paid_usd) > 0.005` in `int_ap_payment_allocation`. It passes with 0 rows.
- [ ] A grain test on `fct_ap_capex_payment` over payment, bill and bill line.
- [ ] `relationships` from every FK to its dimension.
- [ ] `unknown_rate` on `market_key` with the default 5% threshold. It passes at about 2.7% of rows. Write down, in the yml, what a rise past 5% would mean (people have stopped typing the service area) and who would fix it (the AP team, not you).
- [ ] A singular test that fails if any `payment_tranid` or `bill_tranid` in the fact belongs to a transaction flagged `_fivetran_deleted` in the source.

**Verification:** `dbt build --select +fct_ap_capex_payment` is green. Set the `unknown_rate` threshold on `market_key` to `0.02` and it **fails**, then set it back. This time the Unknown rows are real: 147 of the 5,406 fact rows (2.72%).

**Estimate:** M  ·  **Track:** netsuite  ·  **Depends on:** BF-64, BF-29

---

### BF-66: Make it fail on purpose: the fan-out
**As a** data engineer **I want** to break the allocation and watch the conservation test catch it **so that** I recognise a many-to-many fan-out the next time I see one.

**Learning objective:** fan-out is the most common way an ERP model inflates money. And a clean-looking join can still be wrong in a way no invariant sees.

**Acceptance criteria**
- [ ] You change `int_ap_payment_allocation` to give each line the full `paid_usd` (drop the `line_share`), and rebuild.
- [ ] You confirm capex paid to date jumps from $23,287,443 to **$51,313,872**, more than double.
- [ ] You confirm the conservation test fails, and record how many applications it names.
- [ ] You revert, and confirm the test passes and the total is back.
- [ ] **Then the quiet one.** Convert at the **bill's** exchange rate instead of the payment's, and rebuild. The total moves by about $4,300 to $23,291,769. The conservation test still passes, because it compares the model with itself. Write down which check would catch it (BF-68's hand-written reconciliation) and revert.

**Verification:** with the fan-out in place, the conservation test fails with **1031** rows, one for every payment application whose bill has more than one detail line. After reverting, it passes with **0**.

**Estimate:** M  ·  **Track:** netsuite  ·  **Depends on:** BF-65

---

### BF-67: `fct_market_build_economics_monthly`: drill across two facts
**As a** data engineer **I want** a monthly fact that puts capex paid next to passings, by market **so that** capex per passing can be asked of one table, at one grain.

**Learning objective:** drill-across. Two facts at different grains are never joined row to row. Each is aggregated to a shared grain, month by market, and the aggregates are joined on the conformed dimensions. This fact also holds a **flow** and a **balance** side by side, which is where the difference stops being theory.

**Acceptance criteria**
- [ ] The grain is built from the dimensions, not from either fact: every month in `dim_date` from 2021-01 through the report month, crossed with **every** row of `dim_market`, Unknown included. That is 45 × 7 = 315 rows.
- [ ] Passings come from `fct_passings_subscribers_monthly`, aggregated to month and market first. The Unknown market has 0 passings, via `coalesce`, not NULL.
- [ ] `capex_paid_in_month` sums `fct_ap_capex_payment` for payments in that month on or before the month's as-of point, the same `least(month_end_date, report_as_of_date)` rule as passings. It is a **flow**.
- [ ] `capex_paid_to_date` is the running total of `capex_paid_in_month` per market. It is a **balance**.
- [ ] No stored capex-per-passing column.
- [ ] Both sides are **left** joined onto the spine. A comment says what an inner join would silently drop (GOTCHA S).
- [ ] Reuse `assert_balances_are_non_decreasing` (or a copy) for `capex_paid_to_date`.

**Verification:** `select count(*) from fct_market_build_economics_monthly` returns **315**. For 2024-09, `sum(capex_paid_to_date)` rounds to **23287443** and `sum(passings)` is **16374**. The Unknown market row for 2024-09 has **0** passings and **589924** capex to date. Excluding the Unknown market, **9** market-months have capex to date but no passings yet, because engineering is paid before anything is built.

**Estimate:** L  ·  **Track:** netsuite  ·  **Depends on:** BF-66, BF-26

---

### BF-68: Capex per passing, reconciled
**As a** data engineer **I want** capex per passing by market as at 2024-09-13, reconciled by hand **so that** finance gets a number I can defend.

**Learning objective:** ratio of sums again, plus the decision about what goes in the numerator. Unattributed spend is still spend.

**Acceptance criteria**
- [ ] `v_capex_per_passing_current` returns seven rows for the report month (six markets plus Unknown), with capex to date, passings, and `div0null(capex_paid_to_date, passings)` computed in the view. Plain division fails on the Unknown row, which has no passings.
- [ ] The company figure is `sum(capex_paid_to_date) / sum(passings)` over **all** rows, Unknown included: $23,287,443 over 16,374 passings is **$1,422.22**. A comment explains why the market figures do not add up to it.
- [ ] A hand-written query over the raw tables reproduces the company total without using any dbt model. Record it in `NOTES.md` next to the fact's number.
- [ ] The three traps are measured and recorded, with the numbers each one gives:
  - an inner join to the passings side drops the Unknown spend: $22,697,520, or $1,386.19 per passing
  - averaging the six market ratios gives $1,455.02
  - summing `capex_paid_to_date` over the months of 2024 gives $186,204,753. The right year-to-date figure sums the flow: $6,669,460

**Verification:** the view's six market rows match the by-market table in `docs/BUSINESS_RULES.md` to the cent (Cobalt Hills top at **1891.33**, Dunmore Plains bottom at **1015.84**). The Unknown row shows **589924** of capex and a null per-passing figure. The hand-written query returns **23287443.42**.

**Estimate:** M  ·  **Track:** netsuite  ·  **Depends on:** BF-67

---

### BF-69: Put the economics fact in the semantic view
**As a** data engineer **I want** the new fact in the semantic layer **so that** capex questions get the same guard rails as passings questions.

**Learning objective:** a flow and a balance in one semantic view. `capex_paid_in_month` adds up across time. `capex_paid_to_date` and `passings` must not. The same clause, `NON ADDITIVE BY`, applies to one and not the other, and it must be table-qualified (GOTCHA C) for the same reason as before.

**Acceptance criteria**
- [ ] `fct_market_build_economics_monthly` is added to the DCM-managed semantic view (or a second one, your call, written down), related to `market` and `calendar`.
- [ ] `capex_paid_in_month` is fully additive.
- [ ] `capex_paid_to_date` and `passings` are `NON ADDITIVE BY (calendar.year_month, calendar.month_end_date, calendar.year_number)`.
- [ ] A `capex_per_passing` metric is a ratio of the two sums.
- [ ] Agent track: add an eval that asks for total capex paid over July to September 2024, and one that asks for capex per passing by market.

**Verification:** a semantic view query over 2024-07 to 2024-09 returns `capex_paid_in_month` of **1526377** (the three months added up) and `capex_paid_to_date` of **23287443** (September's balance, not the sum). `capex_per_passing` for the same query returns **1422.22**.

**Estimate:** M  ·  **Track:** netsuite  ·  **Depends on:** BF-68, BF-40

---

### BF-79: SCD2 `dim_vendor`
**As a** data engineer **I want** vendor history kept when a name changes **so that** a fact from before the change still resolves to the vendor as it was.

**Learning objective:** a Type 2 dimension. BF-34 snapshots the source because the nightly restore throws history away. This story is the other tool: the dimension itself carries effective dates. The vendor extract is still current-state. You have to snapshot it before you overwrite the row, or the old name does not exist anywhere.

**Acceptance criteria**
- [ ] `dbt/snapshots/snp_vendor.sql` uses `strategy='check'`, `unique_key` the vendor id, and `check_cols` that include `companyname` and do **not** include `lastmodifieddate`.
- [ ] You run `dbt snapshot` **before** `snowflake/raw/apply_vendor_change.sql`. That script renames vendor **101** from `Granitepoint Civil` to `Granitepoint Civil Group` and stamps `lastmodifieddate` `2024-06-01`.
- [ ] You snapshot again. One vendor has two versions. A comment says why `lastmodifieddate` is not a check column: the script changes it on purpose, and a timestamp column would make every reload look like a change.
- [ ] `dim_vendor` is rebuilt from the snapshot, not from the current vendor table. Each version has `valid_from`, `valid_to`, and `is_current`. The Unknown row is still keyed `'0'` and is current.
- [ ] `NOTES.md` says what BF-63's 13-row dimension was missing: after the rename, a Type 1 rebuild has 13 rows and the old name is gone.

**Verification:** `select count(*) from dim_vendor` returns **14**. `select count(*) from dim_vendor where vendor_id = 101` returns **2** (use the natural id column you kept; the surrogate key differs per version). `select count_if(is_current)` returns **13**. One of the two vendor-101 names is **Granitepoint Civil** and the other is **Granitepoint Civil Group**, and only the Group row is current.

**Estimate:** M  ·  **Track:** netsuite  ·  **Depends on:** BF-63, BF-34

---

### BF-80: Accumulating snapshot `fct_ap_bill`
**As a** data engineer **I want** one row per bill, with the dates it moved through **so that** an open bill and a bill paid in two installments are visible as nulls and as two different dates.

**Learning objective:** an accumulating snapshot. The grain is the bill, for its whole life. Milestones fill in as they happen. A null later date is the state. It is not a missing join.

**Acceptance criteria**
- [ ] `dbt/models/anl/fct_ap_bill.sql` has one row per **live** bill. Deleted bills are excluded. Grain test included.
- [ ] Columns: `bill_date`, `first_payment_date`, `paid_in_full_date`.
- [ ] `first_payment_date` is the earliest live payment applied to the bill. `paid_in_full_date` is the payment date on which the applied amount reaches the bill's detail-line total. A bill with no payment keeps both later dates null.
- [ ] A comment records the extract: **0** bills are partially paid on the day the file was pulled. Do not go looking for a `Partially Paid` status. The two-date case is the **53** bills paid in two installments, where the first payment and the paid-in-full payment are different days.
- [ ] The seven-block scaffold is on the model.

**Verification:** `select count(*) from fct_ap_bill` returns **2320**. `count_if(first_payment_date is null)` returns **24**, and those 24 also have `paid_in_full_date` null. `count_if(paid_in_full_date is not null)` returns **2296**. `count_if(first_payment_date <> paid_in_full_date)` returns **53**. The grain test passes with **0** rows.

**Estimate:** L  ·  **Track:** netsuite  ·  **Depends on:** BF-64

---

### BF-81: Flow fact `fct_ap_cash_monthly`
**As a** data engineer **I want** capex cash paid stored as its own monthly fact **so that** adding the months up is the correct use of this table and the wrong use of the balance beside it.

**Learning objective:** a flow fact is additive across time. BF-67 already stores `capex_paid_in_month` next to `capex_paid_to_date` on one row. This story gives the flow its own fact, and a test that the pieces equal the transaction fact. Summing `cash_paid` across 2024 is right. Summing `capex_paid_to_date` across 2024 is still the $186,204,753 trap.

**Acceptance criteria**
- [ ] `dbt/models/anl/fct_ap_cash_monthly.sql` is month by market, Unknown included, from 2021-01 through the report month. **315** rows. January 2021 is zero. Payments start in February.
- [ ] `cash_paid` is capex only, the same dollars as `paid_usd` on `fct_ap_capex_payment`, cut off at the same as-of point. It is a flow. There is no paid-to-date column on this fact.
- [ ] `dbt/tests/assert_cash_flow_equals_capex_payments.sql` returns a row when `sum(cash_paid)` disagrees with `sum(paid_usd)` from `fct_ap_capex_payment` for payments on or before `report_as_of_date`, past one cent.
- [ ] A comment points at BF-68: summing the balance across the months of 2024 returns **$186,204,753**. Summing this fact for 2024 returns **$6,669,460**.

**Verification:** `select count(*) from fct_ap_cash_monthly` returns **315**. `select round(sum(cash_paid), 2) from fct_ap_cash_monthly` returns **23287443.42**. `select round(sum(cash_paid), 0) from fct_ap_cash_monthly where year_month like '2024-%'` returns **6669460**. The singular test passes with **0** rows.

**Estimate:** M  ·  **Track:** netsuite  ·  **Depends on:** BF-67
