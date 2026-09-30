# Backlog

81 stories in eleven epics. BF-01 through BF-69 keep their original numbers. BF-70
through BF-81 were added later and sit in the epic where you do them, not at the end of
the list. Every story has acceptance criteria and a **Verification**: an exact command
or query with its expected result.

## How to work a story

1. Read the story, then the GOTCHAS it names.
2. Build it.
3. Run the verification exactly as written. If the result differs, the story is not done,
   however finished it looks. [`../docs/BUSINESS_RULES.md`](../docs/BUSINESS_RULES.md) has
   a table of common wrong numbers and their causes.
4. Write anything surprising in your `NOTES.md`.

If a verification cannot be run as written, that is a bug in the backlog. Note it for
BF-57 and move on.

## Estimates and tracks

**Estimates** assume you are learning the concept as you go: **S** is under half a day,
**M** is about a day, **L** is two days or more.

**Tracks:** `core` needs only Snowflake and a laptop. `platform`, `aws`, `incremental`,
`agent`, `sigma` and `netsuite` are optional. Skip a track and skip its stories. Option A
is BF-13 or BF-71, not both. The platform track replaces BF-70.

| Track | Stories | Effort |
| --- | --- | --- |
| core | 43 | about 40 days |
| platform | 6 | about 4 days |
| aws | 4 | about 3 days |
| incremental | 2 | about 1.5 days |
| agent | 4 | about 3.5 days |
| sigma | 6 | about 5.5 days |
| netsuite | 15 | about 16.5 days |

## Epics

| Epic | File | Stories |
| --- | --- | --- |
| 1. Foundations and environment | [01-foundations.md](01-foundations.md) | BF-01 required. BF-03 to BF-08 platform. BF-02 is option B |
| 2. Source and ingestion | [02-source-and-ingestion.md](02-source-and-ingestion.md) | BF-70, option A or B, BF-11, BF-12, BF-15 |
| 3. dbt core modelling | [03-dbt-core-modelling.md](03-dbt-core-modelling.md) | BF-16 to BF-27, BF-72, BF-73 |
| 4. Testing and data quality | [04-testing-and-data-quality.md](04-testing-and-data-quality.md) | BF-28 to BF-35, BF-74 to BF-76 |
| 5. Documentation | [05-documentation.md](05-documentation.md) | BF-36 to BF-38 |
| 6. Semantic layer | [06-semantic-layer.md](06-semantic-layer.md) | BF-39 to BF-42 |
| 7. AI agent (optional) | [07-ai-agent.md](07-ai-agent.md) | BF-43 to BF-46 |
| 8. BI presentation in Sigma (optional) | [08-bi-presentation.md](08-bi-presentation.md) | BF-47 to BF-52 |
| 9. Verification and handoff | [09-verification-and-handoff.md](09-verification-and-handoff.md) | BF-53 to BF-57 |
| 10. NetSuite AP and capex per passing (optional) | [10-netsuite-ap-capex.md](10-netsuite-ap-capex.md) | BF-58 to BF-69, BF-79 to BF-81 |
| 11. Incremental models (optional) | [11-incremental.md](11-incremental.md) | BF-77, BF-78 |

## All stories

| Story | Title | Track | Est. | Depends on |
| --- | --- | --- | --- | --- |
| [BF-01](01-foundations.md) | Repo scaffold | core | S | none |
| [BF-02](01-foundations.md) | AWS networking prerequisites | aws | S | BF-01 |
| [BF-03](01-foundations.md) | The `BRINDLE_` prefix decision | platform | S | BF-01 |
| [BF-04](01-foundations.md) | Snowflake bootstrap and deployer role privileges | platform | M | BF-03 |
| [BF-05](01-foundations.md) | DCM project skeleton and first plan | platform | M | BF-04 |
| [BF-06](01-foundations.md) | Warehouses with every property declared | platform | S | BF-05 |
| [BF-07](01-foundations.md) | Databases and the two-plane RBAC model | platform | M | BF-06 |
| [BF-08](01-foundations.md) | Prove the RBAC negative case | platform | S | BF-07 |
| [BF-70](02-source-and-ingestion.md) | Plain SQL account | core | M | BF-01 |
| [BF-09](02-source-and-ingestion.md) | Provision RDS Postgres with a pinned engine version | aws | M | BF-02 |
| [BF-10](02-source-and-ingestion.md) | Load the source into Postgres | aws | S | BF-09 |
| [BF-11](02-source-and-ingestion.md) | Reproducible synthetic data | core | S | BF-01 |
| [BF-12](02-source-and-ingestion.md) | Decision record: why full-table sync, not CDC | core | S | BF-11 |
| [BF-13](02-source-and-ingestion.md) | Raw load from CSV, reproducing the Fivetran contract | core | M | BF-12, and BF-70 or BF-07 |
| [BF-71](02-source-and-ingestion.md) | Raw load from SQL inside Snowflake | core | M | BF-12, and BF-70 or BF-07 |
| [BF-14](02-source-and-ingestion.md) | Wire up Fivetran properly | aws | M | BF-10, and BF-13 or BF-71 |
| [BF-15](02-source-and-ingestion.md) | Profile the dirty data before modelling | core | M | BF-13 or BF-71 |
| [BF-16](03-dbt-core-modelling.md) | dbt project, profile, and PAT authentication | core | M | BF-70 or BF-07 |
| [BF-17](03-dbt-core-modelling.md) | Layer config: int as views, anl as tables | core | S | BF-16 |
| [BF-18](03-dbt-core-modelling.md) | Custom `generate_database_name` | core | M | BF-17 |
| [BF-19](03-dbt-core-modelling.md) | Sources with freshness | core | S | BF-18, and BF-13 or BF-71 |
| [BF-20](03-dbt-core-modelling.md) | Custom utility macros instead of dbt_utils | core | M | BF-19 |
| [BF-72](03-dbt-core-modelling.md) | Compare the hand-written key with `dbt_utils` | core | M | BF-20 |
| [BF-21](03-dbt-core-modelling.md) | `int_location`: parse the date, plant the sentinel | core | M | BF-72 |
| [BF-22](03-dbt-core-modelling.md) | `int_subscriber` and `int_market_hierarchy` | core | M | BF-21 |
| [BF-23](03-dbt-core-modelling.md) | The `vars:` entry for `report_as_of_date` | core | S | BF-22 |
| [BF-24](03-dbt-core-modelling.md) | `dim_market` with an Unknown member | core | M | BF-23 |
| [BF-25](03-dbt-core-modelling.md) | `dim_location` and `dim_date` | core | M | BF-24 |
| [BF-26](03-dbt-core-modelling.md) | `fct_passings_subscribers_monthly` | core | L | BF-25 |
| [BF-27](03-dbt-core-modelling.md) | `v_by_market_current` presentation view | core | S | BF-26 |
| [BF-73](03-dbt-core-modelling.md) | Daily dbt build as a Snowflake task | core | M | BF-27, BF-72 |
| [BF-28](04-testing-and-data-quality.md) | Generic tests on keys and relationships | core | M | BF-73 |
| [BF-29](04-testing-and-data-quality.md) | Custom generic test: `unknown_rate` | core | M | BF-28 |
| [BF-30](04-testing-and-data-quality.md) | Place `unknown_rate` on fact FK edges, not dimension keys | core | S | BF-29 |
| [BF-31](04-testing-and-data-quality.md) | Make it fail on purpose: reintroduce the subscriber-balance defect | core | L | BF-30 |
| [BF-74](04-testing-and-data-quality.md) | Unit test the re-sign on `int_subscriber` | core | M | BF-31 |
| [BF-32](04-testing-and-data-quality.md) | Singular test: grain uniqueness | core | S | BF-31 |
| [BF-33](04-testing-and-data-quality.md) | Singular tests: attributability and ratio-of-sums | core | M | BF-32 |
| [BF-34](04-testing-and-data-quality.md) | Snapshot `locations_passed` with `strategy='check'` | core | M | BF-33 |
| [BF-35](04-testing-and-data-quality.md) | Source freshness as an operational check | core | S | BF-34 |
| [BF-75](04-testing-and-data-quality.md) | A `prod` target | core | M | BF-35, BF-73 |
| [BF-76](04-testing-and-data-quality.md) | Build only what changed | core | M | BF-75 |
| [BF-36](05-documentation.md) | Descriptions on every model and column | core | M | BF-76 |
| [BF-37](05-documentation.md) | `persist_docs` into Snowflake | core | S | BF-36 |
| [BF-38](05-documentation.md) | Generate and review the docs site | core | S | BF-37 |
| [BF-39](06-semantic-layer.md) | Semantic view skeleton in DCM | core | M | BF-38 |
| [BF-40](06-semantic-layer.md) | Table-qualify `NON ADDITIVE BY` | core | M | BF-39 |
| [BF-41](06-semantic-layer.md) | Reconcile the semantic view to the anchor numbers | core | M | BF-40 |
| [BF-42](06-semantic-layer.md) | Prove the semantic view resists the two aggregation traps | core | M | BF-41 |
| [BF-43](07-ai-agent.md) | Agent bootstrap | agent | M | BF-42 |
| [BF-44](07-ai-agent.md) | Agent definition grounded on the semantic view | agent | M | BF-43 |
| [BF-45](07-ai-agent.md) | Agent evaluations, including the two traps | agent | M | BF-44 |
| [BF-46](07-ai-agent.md) | Agent optimization log | agent | S | BF-45 |
| [BF-47](08-bi-presentation.md) | Sigma API client and the region problem | sigma | M | BF-27 |
| [BF-48](08-bi-presentation.md) | Sigma service user, connection and inventory sync | sigma | M | BF-47 |
| [BF-49](08-bi-presentation.md) | Workbook spec with table-prefixed column references | sigma | M | BF-48 |
| [BF-50](08-bi-presentation.md) | Bisect the `Invalid kind` error and keep filters out of Sigma | sigma | M | BF-49 |
| [BF-51](08-bi-presentation.md) | Create the workbook and export its data | sigma | M | BF-50 |
| [BF-52](08-bi-presentation.md) | Reconcile Sigma against the fact, market by market | sigma | S | BF-51 |
| [BF-53](09-verification-and-handoff.md) | The reconciliation record | core | M | BF-42, plus BF-45 and BF-52 if you did those tracks |
| [BF-54](09-verification-and-handoff.md) | Full rebuild from scratch | core | L | BF-53 |
| [BF-55](09-verification-and-handoff.md) | Runbook | core | M | BF-54 |
| [BF-56](09-verification-and-handoff.md) | Teardown verified clean | core | S | BF-55 |
| [BF-57](09-verification-and-handoff.md) | Handoff notes: shortcuts, honestly | core | S | BF-56 |
| [BF-58](10-netsuite-ap-capex.md) | Land the NetSuite source | netsuite | S | BF-13 or BF-71, BF-35 |
| [BF-59](10-netsuite-ap-capex.md) | Profile the ERP data before modelling | netsuite | M | BF-58 |
| [BF-60](10-netsuite-ap-capex.md) | Declare the second source | netsuite | S | BF-58, BF-19 |
| [BF-61](10-netsuite-ap-capex.md) | `int_ap_bill_line` | netsuite | M | BF-60, BF-20, BF-22 |
| [BF-62](10-netsuite-ap-capex.md) | `int_ap_payment_application` | netsuite | M | BF-60 |
| [BF-63](10-netsuite-ap-capex.md) | `dim_vendor` and `dim_gl_account` | netsuite | S | BF-60, BF-24 |
| [BF-64](10-netsuite-ap-capex.md) | `fct_ap_capex_payment`, via an allocation model | netsuite | L | BF-61, BF-62, BF-63, BF-25 |
| [BF-65](10-netsuite-ap-capex.md) | Tests for the capex fact | netsuite | M | BF-64, BF-29 |
| [BF-66](10-netsuite-ap-capex.md) | Make it fail on purpose: the fan-out | netsuite | M | BF-65 |
| [BF-67](10-netsuite-ap-capex.md) | `fct_market_build_economics_monthly`: drill across two facts | netsuite | L | BF-66, BF-26 |
| [BF-68](10-netsuite-ap-capex.md) | Capex per passing, reconciled | netsuite | M | BF-67 |
| [BF-69](10-netsuite-ap-capex.md) | Put the economics fact in the semantic view | netsuite | M | BF-68, BF-40 |
| [BF-77](11-incremental.md) | An append-only event table | incremental | S | BF-15, BF-27 |
| [BF-78](11-incremental.md) | `int_service_event` incremental model | incremental | M | BF-77 |
| [BF-79](10-netsuite-ap-capex.md) | SCD2 `dim_vendor` | netsuite | M | BF-63, BF-34 |
| [BF-80](10-netsuite-ap-capex.md) | Accumulating snapshot `fct_ap_bill` | netsuite | L | BF-64 |
| [BF-81](10-netsuite-ap-capex.md) | Flow fact `fct_ap_cash_monthly` | netsuite | M | BF-67 |
