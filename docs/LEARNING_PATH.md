# Learning path: dbt and Snowflake, via the Brindle rebuild

A curriculum mapped onto the backlog. Each unit names the concept, the stories that teach
it, and what to read alongside.

**Reading is given by concept name, not URL.** Search the dbt or Snowflake docs for the
named topic. URLs move, and a dead link is worse than a name.

The order matters. Each concept lands on a foundation the previous one laid, and the
hardest idea in the project (a correct total does not imply a correct series) arrives only
once you have enough machinery to test for it.

---

## Unit 0: Before dbt, why the project is shaped the way it is

**Stories:** BF-01 to BF-15

Not dbt, but do not skip it. Three decisions made here set most of what the dbt layer has
to do:

- The source is **restored nightly**, so CDC is impossible, so ingestion is a daily
  full-table sync, so history has to be rebuilt with a **dbt snapshot** (BF-12 leads to
  BF-34).
- The raw load keeps `''` as `''` (`empty_field_as_null = false`), so the `int` layer
  has something to clean (BF-13 leads to BF-21).
- `AGENT` and `USER` are not DCM entities, so the optional platform track splits into a
  declarative `dcm_project/` and an imperative `bootstrap/` (BF-05 leads to BF-43).
  BF-70 is the same account without DCM.

**Read:** dbt docs, *"What is dbt?"*. Enough to know what dbt is not responsible for. dbt
does not move data. The loader does.

---

## Unit 1: Project structure and connection

**Story:** BF-16. **Concepts:** `dbt_project.yml`, `profiles.yml`, targets, `dbt debug`.

A dbt project is two files and a folder of SELECTs. `dbt_project.yml` is the project.
`profiles.yml` is how it reaches a warehouse, and it holds credentials, so keep secrets in
environment variables.

Authentication is where people lose an afternoon. Use a **PAT in the `password:` field**,
never `authenticator: externalbrowser` for anything unattended, and check the PAT is not
restricted to another role (GOTCHA M). [`SETUP.md`](SETUP.md) has a working profile.

**Read:** *"About dbt_project.yml"*, *"Connection profiles"*, *"dbt debug"*, and the
*"Snowflake setup"* connection page.

---

## Unit 2: Configuration inheritance and materializations

**Stories:** BF-17, BF-18. **Concepts:** the `models:` config hierarchy, `materialized`,
`generate_database_name`.

Config in `dbt_project.yml` cascades down the folder tree. Set `int` to views and `anl` to
tables once, at the folder, and no model restates it. When a model does override, the
override means something. That is why `v_by_market_current` being a view inside a table
folder (BF-27) is a readable signal rather than noise.

Then override `generate_database_name`. Models carry a logical alias like `int`,
and the macro owns the physical name `brindle_dev_int_db`. Get this right and a
second environment costs nothing. Get it wrong and physical names leak into every model.

**Read:** *"Materializations"*, *"Configuring models"*, *"Custom databases"*, *"Custom
schemas"*.

---

## Unit 3: Sources and freshness

**Story:** BF-19. **Concepts:** `sources`, `source()`, `loaded_at_field`, freshness.

`source()` does two jobs. It decouples models from physical raw names, and it puts the
table in the DAG so lineage starts at the source.

Freshness is the first operational thing in dbt. Set the threshold from the real cadence:
a **48-hour warn** here, because the sync is daily. A one-hour threshold on a daily sync is
not vigilance. It is an alarm nobody reads.

**Read:** *"Add sources to your DAG"*, *"Source freshness"*.

---

## Unit 4: Macros, written from scratch

**Story:** BF-20. **Concepts:** Jinja, `{% macro %}`, arguments, `dbt show --inline`.

Write `utils_surrogate_key` before you install `dbt_utils`. Concatenate carelessly and
`('a','b')` collides with `('ab','')`. Coalesce NULL to an empty string and NULL and `''`
become the same key. BF-72 is where the package is allowed in.

Four macros, four ideas: hashing a key (`utils_surrogate_key`), hashing an attribute set
for change detection (`utils_change_hash`), normalising blanks (`coalesce_to_unknown`), and
generating a fixed row (`generate_unknown_record`). The last two keep the `int` layer and
the Unknown member pattern DRY.

**Read:** *"Jinja and macros"*, *"About macros"*, *"dbt show"*.

---

## Unit 4b: The package, after the macro

**Story:** BF-72. **Concepts:** `packages.yml`, `dbt deps`, `dbt_utils.generate_surrogate_key`.

Models keep calling your macro. The package is there so you can see the collision it
closes, and so the next project does not start from a blank file. The hashes will not
match. Yours is SHA-256. The package is MD5. The behavior that matters is that both
return two different values for `('a','b')` and `('ab','')`.

**Read:** *"Packages"*, *"dbt_utils"*.

---

## Unit 5: The integration layer and `ref()`

**Stories:** BF-21, BF-22. **Concepts:** `ref()`, the DAG, layering, grain.

`raw`, `int`, and `anl` are the only layer names in this project. `raw` is the landed
source, declared with `source()`, not a model folder. `int` means integration: cleaning
and grain changes. `anl` means analysis: dimensions, facts, and the presentation view.
dbt's guides call those jobs staging, intermediate, and marts. The work is the same.
The names in a job posting are the other words.

`ref()` is the most important function in dbt. It resolves to a relation **and** declares
a dependency, which is how dbt works out the build order. `dbt ls --select +model_name`
shows you what it inferred.

The `int` layer is where cleaning happens, and nothing is dropped there. `int_location`
parses `MM-DD-YYYY` out of text and maps blanks to the sentinel `'12-31-2030'`. The
sentinel is in the future, so those 1,442 rows fail the passings rule on their own, with no
exclusion branch. Choosing a sentinel that makes a later rule do your work is a real
technique.

`int_subscriber` changes grain, from 2,194 order rows to 1,631 addresses. Watch that model
closely, because *how* you collapse the grain is exactly where defect A hides. The column
`first_active_service_eff_date` exists to prevent it.

**Read:** *"ref function"*, *"How we structure our dbt projects"*.

---

## Unit 6: Project variables

**Story:** BF-23. **Concept:** `vars:` and `var()`.

One idea: the as-of date exists once, in `vars:`. Two models with two hardcoded dates is a
bug you find six months later, when nobody remembers which one was right.

**Read:** *"Project variables"*, *"var"*.

---

## Unit 7: Dimensional modelling and the Unknown member

**Stories:** BF-24, BF-25. **Concepts:** surrogate keys, conformed dimensions, the Unknown
member, the SELECT scaffold.

An inner join silently drops unmatched facts. An outer join silently produces NULL labels.
Both hide the problem. A real Unknown row keyed `'0'`, unioned onto the dimension, makes
the problem **countable**, and once it is countable it can be tested (Unit 9).

`dim_date` owning `year_month`, `month_end_date` and `year_number` is not just tidiness.
The fact carries copies of the first two for convenience, and that coincidence is what
lets an unqualified `NON ADDITIVE BY` bind to the wrong table in Unit 13.

`dim_location` is built but nothing joins to it yet, because the fact is at market grain.
That is deliberate. It is the conformed dimension the By PON stretch goal needs.

**Read:** *"How we structure our dbt projects"* (the marts section). For the pattern
itself, any Kimball reference on *conformed dimensions* and the *unknown member*.

---

## Unit 8: The fact, balances not flows

**Stories:** BF-26, BF-27. **Concepts:** grain, point-in-time balances, the as-of point,
ratio of sums.

Three rules carry the whole project.

**Balances, not flows.** Passings and subscribers are cumulative. A month contains all
prior months, so summing across months is meaningless. That one property is why the
semantic view needs `NON ADDITIVE BY` and the agent needs an explicit instruction.

**The as-of point.** Each month is measured at `least(month_end_date, report_as_of_date)`.
The report month is measured at 2024-09-13, not the 30th. Use the month end and you get
16,411 passings, not 16,374.

**Penetration is a ratio of sums, never stored per row.** `sum(subscribers) /
sum(passings)`, computed at query time. Averaging the six market rates gives 8.70% instead
of 8.04%, because it weights a 1,559-passing market the same as a 4,258-passing one. If
you store a per-row ratio, someone will eventually average it, because it is right there
and it looks like a number you can average.

**Read:** *"Materializations"* for the table and view choice. For the semantics, look up
*semi-additive facts* and *point-in-time balances*. dbt does not teach this. Dimensional
modelling does.

---

## Unit 8b: A daily build, on Snowflake

**Story:** BF-73. **Concepts:** dbt project objects, `EXECUTE DBT PROJECT`, tasks, cron.

Develop with dbt Core. Schedule with a Snowflake task in the same database and schema as
the project object. The command is `dbt build`, so the tests from the next units ride
along. The task is created suspended. Resume it only after one manual `EXECUTE TASK`
returns the anchor numbers, and suspend it again when you stop, or a trial account pays
for a build every morning.

**Read:** Snowflake docs, *"Schedule execution of dbt project objects"*, *"EXECUTE DBT PROJECT"*.

---

## Unit 9: Generic tests

**Stories:** BF-28 to BF-30. **Concepts:** the four built-in generic tests, custom generic
tests, where a test belongs.

Start with `unique`, `not_null`, `relationships` and `accepted_values`. `relationships` is
dbt's answer to a foreign key, checked at build time on modelled data rather than at write
time. `'N/A'` belongs in your `accepted_values` lists. It is a real, deliberate value here.

Then write a custom generic test: `{% test %}`, the `model` and `column_name` variables, a
threshold argument, and dbt's contract, which is **rows on failure, zero rows on pass**.

Then the harder lesson, **placement**. `unknown_rate` on `dim_market.market_key` fails at
14.3% by construction, because the Unknown row is one of seven. On a **fact FK** the same
test means a join did not resolve. Same test, same threshold, two completely different
meanings depending on where you hang it.

**Read:** *"Add data tests to your DAG"*, *"Writing custom generic data tests"*, *"Test
configurations"*.

---

## Unit 10: Testing the invariant, not the endpoint

**Stories:** BF-31 to BF-33. **Concepts:** singular tests, and the most important lesson in
the project.

A singular test is a plain SQL file in `tests/`. Zero rows means pass. That is the whole
API, and it is enough to encode any rule you can phrase as "find the violations".

**BF-31 is the story.** You swap the subscriber qualification for "current record" logic:
each month, take the address's latest period and count it if that period is active. A
billing migration in March 2022 cancelled a batch of orders, and those customers re-signed
later, so under the new logic they vanish from the months in between. 2022-03 reads 21
instead of 56.

Now the part that matters. Every one of them had re-signed by September 2024, so the
defect is **invisible at the report month**, which is exactly where the reconciliation was
being checked. A green `dbt build` and a correct 16,374 / 1,316 / 8.04% hide it completely.

What catches it is an **invariant**. These are cumulative balances, so they can never go
down. `assert_balances_are_non_decreasing.sql` says that in a handful of lines and fails at
once.

> **A correct total does not imply a correct series. Test the invariant, not the endpoint.**

Then notice the limit. Some history bugs never make a series go down, and this test passes
right over them. An invariant only catches what violates it, which is why BF-53 also
compares every month against a hand-written source query.

Two more invariants follow: the declared grain (`assert_fact_grain_is_month_market`) and
rule 4 (`assert_penetration_is_ratio_of_sums`).

**Read:** *"Singular data tests"*, *"Data tests"*, *"Node selection syntax"*.

---

## Unit 10b: A unit test for the same defect

**Story:** BF-74. **Concept:** dbt unit tests.

The singular test watches the fact. The unit test watches `int_subscriber` with three
fixture rows: installed, cancelled, installed again. The expected start date is the first
installation. Swap `min` for `max` and the unit test fails while the September total is
still nowhere in sight. Singular tests and unit tests answer different questions. Keep
both.

**Read:** *"Unit tests"*.

---

## Unit 11: Snapshots and freshness as operations

**Stories:** BF-34, BF-35. **Concepts:** `dbt snapshot`, SCD2, `check` versus `timestamp`.

Snapshots exist here for a specific reason. The source is restored nightly and carries no
history. Without a snapshot, history is simply gone. Unit 0's constraint becomes Unit 11's
requirement.

`strategy='check'` rather than `timestamp`, because there is no trustworthy updated-at
column, and a nightly restore would reset one anyway. Run it twice on unchanged data and
the second run must add nothing. If it does, your `check_cols` includes something volatile,
very likely `_fivetran_synced`.

Then treat freshness as operational. A freshness warning means **ingestion** is broken. A
test failure means the **model** is wrong. Different owners, different fixes.

**Read:** *"Snapshots"*, *"Snapshot configurations"*, *"Source freshness"*.

The vendor dimension in BF-79 is the other kind of history. This snapshot keeps a source
the restore would overwrite. That one keeps a dimension someone will join to.

---

## Unit 11b: Prod, and building only what changed

**Stories:** BF-75, BF-76. **Concepts:** a second target, `state:modified+`, `--defer`.

`generate_database_name` was written so a prod target costs no model edits. BF-75 is the
first time that claim is run. BF-76 saves the prod manifest and builds `state:modified+`
with `--defer`, so a one-model change does not rebuild the project. The GitHub workflow
is the command written down. It reads `SNOWFLAKE_PAT` from a secret. You run the command
locally until you have a CI account.

**Read:** *"About state"*, *"Defer"*.

---

## Unit 12: Documentation as an input

**Stories:** BF-36 to BF-38. **Concepts:** `description`, `persist_docs`, `dbt docs
generate`.

Here is the reframe. In this architecture documentation is not a deliverable for humans.
It is the **grounding for an agent**. `persist_docs` writes descriptions into Snowflake
comments, and the agent reads Snowflake metadata, not your docs site. A wrong description
is a correctness bug with a delayed, confidently wrong symptom.

Then generate the docs and actually read the DAG. An unexpected edge, like an `anl` model
reading `source()` directly, is a modelling mistake you cannot see in any single file.

**Read:** *"Documentation"*, *"persist_docs"*, *"doc blocks"*.

---

## Unit 13: The semantic layer, and the clause that compiles while wrong

**Stories:** BF-39 to BF-42. **Concepts:** Snowflake semantic views, relationships,
metrics, `NON ADDITIVE BY`.

A semantic view is a second implementation of your business rules, sitting on top of the
fact. It can disagree with the fact, which is why BF-41 reconciles it separately instead of
trusting it.

`NON ADDITIVE BY` is what stops a balance being summed across time, and it holds the
sharpest trap in the project:

```sql
-- silently wrong: binds to the FACT's own year_month
NON ADDITIVE BY (year_month, month_end_date, year_number)

-- correct
NON ADDITIVE BY (calendar.year_month, calendar.month_end_date, calendar.year_number)
```

Unqualified, two of the three terms bind to the fact's own columns and only the third
errors. **The unqualified form compiles and is wrong.** The lesson reaches well past this
clause: an error on one of three terms tells you nothing about the other two.

**Read:** Snowflake docs, *"Semantic views"*, *"CREATE SEMANTIC VIEW"*.

---

## Unit 14: Grounding an agent (optional track)

**Stories:** BF-43 to BF-46. **Concepts:** grounding, adversarial evaluation, DCM limits.

Agent accuracy is mostly a function of the layers underneath: the semantic view's
structure and the comments `persist_docs` wrote. Most failures on the reference build were
fixed in the semantic view or a dbt description, not by rewording the prompt. That is the
habit to build, and the optimization log is where you show it.

The evals that matter are adversarial. They are the two mistakes a human analyst makes on
this data: summing a balance across months (`q02_sum_trap`) and averaging per-market rates
(`q03_ratio_trap`). Plus one question the agent must **decline**, because a confident
invention is worse than a refusal.

**Read:** Snowflake docs, *"Cortex Agents"*, *"Snowflake Intelligence"*.

---

## Unit 15: BI, and the difference between valid and correct (optional track)

**Stories:** BF-47 to BF-52. **Concepts:** API-driven BI, schema validity versus meaning,
pushing logic down.

The unifying idea is that **a validator checks shape, not meaning**. A workbook can
return `{"valid": true}` and render `Unknown column` in every cell (GOTCHA G). An error can
name the one field that was fine (GOTCHA H). The only proof is the exported data.

And the month filter moves into `v_by_market_current`, which is the better design anyway:
a filter in dbt can carry a test, and a filter in Sigma cannot.

**Read:** Sigma docs on the workbook API, connection sync, and warehouse table
references.

---

## Unit 16: Proving it, and handing it over

**Stories:** BF-53 to BF-57. **Concepts:** independent verification, idempotency, honest
handoff.

Several surfaces, several independent implementations, one set of numbers. The source
figure must come from the business rules applied **by hand** in SQL. Copy the dbt logic
and you have verified nothing. Then extend it to every month and compare all 270 rows,
because that is what catches the history bugs no invariant sees.

BF-54 rebuilds from empty, which is the only real test of every idempotency claim in the
project. Then the runbook, the teardown, and honest notes, including every shortcut and
any story whose verification you could not actually perform.

**Read:** *"dbt build"*, and the best-practice guides. The rest of this unit is engineering
discipline rather than dbt.

---

## Unit 17: A second source, and joining facts properly (optional track)

**Stories:** BF-58 to BF-69. **Concepts:** ERP data structures, allocation, the
conservation invariant, transaction facts, drill-across, flows next to balances.

A second source is where a warehouse either becomes one thing or stays two. The NetSuite
data is clean in the ways operational data is not (types, values) and tricky in ways it is
not (header rows, signed amounts, link tables, currencies, soft deletes). Put every one of
those quirks in the `int` layer, once, and the `anl` layer never hears about them.

**Allocation.** Payments link to bills, and bills have lines, so a payment does not know
which lines it paid. Join straight through and every payment repeats once per line.
Allocating by line share turns a many-to-many into an additive grain, and the
**conservation** test (the pieces add back to the whole) is the invariant that proves it.
It is the money version of Unit 10's "balances never go down", and it has the same limit:
converting at the wrong exchange rate conserves perfectly and is still wrong.

**Drill-across.** Two facts at different grains are never joined row to row. Aggregate each
to a shared grain (month by market), build that grain from the conformed dimensions, and
left join both aggregates onto it. The Unknown market is where this matters: it has spend
and no passings, and an inner join quietly deletes $589,924.

**Flows next to balances.** Capex paid in a month adds up across months. Capex paid to
date does not. Seeing both in one fact, and in one semantic view, makes Unit 8's rule
concrete.

Three patterns that column does not finish:

**SCD2 on `dim_vendor` (BF-79).** Snapshot the vendors, then rename vendor 101. The
dimension keeps both names, with effective dates. A Type 1 rebuild keeps 13 rows and
forgets `Granitepoint Civil`.

**Accumulating snapshot (BF-80).** One row per live bill. 24 bills never get a payment,
so the later dates stay null. 53 bills are paid in two installments, so the first
payment date and the paid-in-full date differ. None are partially paid on the extract.

**Flow fact (BF-81).** `fct_ap_cash_monthly` is additive. Summing it through the as-of
date returns $23,287,443.42, the same dollars as the transaction fact. Summing
`capex_paid_to_date` across 2024 is still $186,204,753.

**Read:** *"Ref"* and *"Sources"* again for the second source. Kimball on *drill-across*,
*slowly changing dimensions*, *accumulating snapshot facts*, *transaction facts* versus
*periodic snapshots*, and *allocations*. Snowflake docs on semantic view metrics for the
additive and non-additive measures.

---

## Unit 18: Incremental, on a table that can take it (optional track)

**Stories:** BF-77, BF-78. **Concepts:** `materialized='incremental'`, `is_incremental()`,
`unique_key`, `on_schema_change`.

Do not start here, and do not "improve" the passings load into one. BF-12 still holds.
`service_events` is append-only: 1,669 activations and 525 cancellations, watermark
`event_at`. The second build adds nothing. A row on 2024-09-14 adds one. `on_schema_change`
is `fail`, because a new column should be a decision.

**Read:** *"Incremental models"*, *"on_schema_change"*.

---

## Concept-to-story index

| Concept | Stories | Unit |
| --- | --- | --- |
| `dbt_project.yml`, `profiles.yml`, `dbt debug` | BF-16 | 1 |
| Materializations, config inheritance | BF-17 | 2 |
| `generate_database_name` override | BF-18 | 2 |
| Sources, `source()`, freshness | BF-19, BF-35 | 3, 11 |
| Macros, Jinja | BF-20 | 4 |
| `ref()` and the DAG | BF-21, BF-22 | 5 |
| Grain change | BF-22 | 5 |
| `vars:` and `var()` | BF-23 | 6 |
| Surrogate keys | BF-20, BF-24 | 4, 7 |
| Unknown member | BF-24, BF-25 | 7 |
| Conformed dimensions | BF-25 | 7 |
| Point-in-time balance fact, as-of point | BF-26 | 8 |
| Ratio of sums | BF-26, BF-33 | 8, 10 |
| Built-in generic tests | BF-28 | 9 |
| Custom generic test | BF-29 | 9 |
| Test placement | BF-30 | 9 |
| Singular tests, invariants | BF-31 to BF-33 | 10 |
| Snapshots, `strategy='check'` | BF-34 | 11 |
| `description`, `persist_docs` | BF-36, BF-37 | 12 |
| `dbt docs generate` | BF-38 | 12 |
| Semantic views, `NON ADDITIVE BY` | BF-39, BF-40 | 13 |
| Agent grounding, evals | BF-43 to BF-46 | 14 |
| API-driven BI | BF-47 to BF-52 | 15 |
| Independent verification | BF-53, BF-54 | 16 |
| A second source, soft deletes | BF-58 to BF-60 | 17 |
| Link tables, currency conversion | BF-62 | 17 |
| Allocation, conservation invariant | BF-64 to BF-66 | 17 |
| Transaction fact | BF-64 | 17 |
| Drill-across, flow and balance side by side | BF-67 to BF-69 | 17 |
| `dbt_utils` after a hand-written macro | BF-72 | 4b |
| Daily Snowflake task, `EXECUTE DBT PROJECT` | BF-73 | 8b |
| Unit tests | BF-74 | 10b |
| Prod target | BF-75 | 11b |
| `state:modified+`, defer | BF-76 | 11b |
| SCD2 dimension | BF-79 | 17 |
| Accumulating snapshot | BF-80 | 17 |
| Additive flow fact | BF-81 | 17 |
| Incremental model | BF-77, BF-78 | 18 |

## If you only do three stories

**BF-31.** Reintroduce defect A and watch the monotonicity test catch it. A correct total
does not imply a correct series.

**BF-30.** Move `unknown_rate` from a dimension key to the fact's FK edges. The same test
in the wrong place is not a weak test, it is a meaningless one.

**BF-40.** Table-qualify `NON ADDITIVE BY`. The unqualified form compiles and is wrong.
