# Brindle Fiber: learn Snowflake and dbt by rebuilding a real-shaped report

A hands-on project for junior and intermediate data engineers. You start from an empty
Snowflake account and a folder of deliberately dirty data, and you finish with a tested
dbt project, a Snowflake semantic view, and one report page whose numbers you can prove.

The report is **Cohort Performance By Market** for Brindle Fiber, a made-up fiber
internet provider: passings, subscribers and penetration for six markets, as at
**2024-09-13**.

| Passings | Subscribers | Penetration |
| ---: | ---: | ---: |
| **16,374** | **1,316** | **8.04%** |

The page is not the point. The point is that this page cannot be produced correctly
without learning most of dbt properly, plus real Snowflake modelling discipline. The data
is dirty on purpose. The business rules are the kind people get subtly wrong. And at least
one of the bugs you will meet is invisible to a green `dbt build`.

## Who this is for

- You write intermediate SQL, including window functions and `group by`.
- You can read a 200-line Python script and use git at a basic level.
- **You do not need any dbt experience.** That is what you are here to learn.
- Kimball dimensional modelling helps but is not assumed. Concepts are named as they
  arrive.

## What you will learn

**dbt, properly.** Sources and freshness, `ref()` and the DAG, materializations, a custom
`generate_database_name`, macros written from scratch and then compared with `dbt_utils`,
dimensional modelling with an Unknown member, a point-in-time balance fact, generic,
custom generic, singular and unit tests, snapshots, a prod target, `state:modified+`,
`persist_docs`, docs, and project `vars`. The layers are `raw`, `int` (integration), and
`anl` (analysis).

**Snowflake modelling.** An optional DCM project and two-plane RBAC, a daily task that
runs `dbt build`, semantic views and their sharp edges, and why column comments matter
once an AI agent reads them.

**A second source, optional.** NetSuite vendor bills and payments, with mainline rows,
currencies, soft deletes and a many-to-many link table. You allocate payments down to
bill lines, prove the allocation conserves cash, and drill across to the passings fact to
answer what each home passed cost to build.

**The thing nobody teaches.** A correct headline number does not imply a correct history.
Story **BF-31** has you plant a bug that leaves the report month exactly right and quietly
breaks two years of history, then watch a test catch it. If you only do one story, do
that one.

## Tracks

You pick how much of the stack to build. The core track needs nothing but a Snowflake
account and a laptop.

| Track | What you build | Needs | Stories | Effort |
| --- | --- | --- | --- | --- |
| **Core** | Plain account, raw load, dbt project, daily task, tests, prod target, docs, semantic view, reconciliation | Snowflake (a trial account works), Python, dbt, Snowflake CLI. dbt Projects on Snowflake for the task | 43 | about 8 weeks full time |
| Platform | DCM project, two-plane RBAC, the negative grant test. Replaces BF-70 | The same Snowflake account | 6 | about 4 days |
| Ingestion option B | RDS Postgres and a Fivetran full-table sync into the same raw tables | An AWS account and Fivetran | 4 | about 3 days |
| Incremental | An append-only event table and one incremental model. Does not replace the full refresh | Nothing extra | 2 | about 1.5 days |
| AI agent | Cortex agent on the semantic view, with adversarial evals | Cortex Agents available in your region | 4 | about 3 to 4 days |
| Sigma | A Sigma workbook built through the API | A Sigma account with API credentials | 6 | about 5 to 6 days |
| NetSuite | Vendor bills and payments, capex per passing, plus an SCD2 vendor dimension, an accumulating bill snapshot, and an additive cash fact | Nothing extra. The data is included | 15 | about 3.5 weeks |

Option A is the core raw load: CSV (`BF-13`) or SQL inserts (`BF-71`). One of them.
Effort assumes you are learning each concept as you go. At two days a week, the core
track is about a four month project. That is normal. Details are in
[`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md).

## Start here

1. Read [`docs/00-brindle.md`](docs/00-brindle.md). It is the company story: how a home
   becomes a passing, what the March 2022 billing migration did, and why the September
   page can look right while the history is wrong.
2. Read [`docs/BUSINESS_RULES.md`](docs/BUSINESS_RULES.md). It is short, and every number
   in the project comes from it.
3. Skim [`docs/GOTCHAS.md`](docs/GOTCHAS.md) once, so the symptoms look familiar when you
   meet them. Come back to it the moment something behaves oddly.
4. Set up your tools with [`docs/SETUP.md`](docs/SETUP.md).
5. Open [`backlog/README.md`](backlog/README.md) and start at **BF-01**.

Keep a `NOTES.md` at the root as you go. Several stories ask you to write findings there,
and by the end it is your handoff document.

## What is in the repo

| Path | What it is |
| --- | --- |
| `docs/00-brindle.md` | The company story: passings, the billing migration, the monthly page, the finance question |
| `docs/BUSINESS_RULES.md` | The case, both sources, the business rules, the anchor numbers, and tables of wrong numbers and their causes |
| `docs/SETUP.md` | Accounts, tools, and connection setup for each track |
| `docs/PROJECT_PLAN.md` | Phases, milestones, definitions of done, dependencies, stretch goals |
| `docs/LEARNING_PATH.md` | Which concept each story teaches, in what order, and what to read alongside it |
| `docs/GOTCHAS.md` | The traps the reference build actually hit, as "if you see X, the cause is Y" |
| `docs/REFERENCE_RUNBOOK.md` | What the finished build looks like and how it is operated. Read it at the end, or when you are stuck on what "done" means |
| `backlog/` | User stories in eleven epics, each with acceptance criteria and an exact verification |
| `data/` | The seeded data generators (network data, and NetSuite AP for the optional track) and the CSVs they produce |
| `postgres/` | Source DDL and a load script for the AWS track |
| `snowflake/raw/` | Loads into the raw layer: CSV, the SQL seed, service events, and the NetSuite extract |
| `snowflake/bootstrap/plain_account.sql` | The three databases and one role, when you skip the platform track |

Everything else you build yourself: `snowflake/dcm_project/`, the rest of `snowflake/bootstrap/`,
`dbt/`, and for the optional tracks `aws/`, `postgres/load_to_snowflake.py`, `fivetran/`,
`snowflake/agents/` and `sigma/`.

## Rules of the road

**Run the verification.** Every story ends with an exact command or query and its expected
result. Do not mark a story done because it looks done. If you find a story you genuinely
cannot verify, that is a bug in the backlog. Write it down (BF-57 asks for exactly that).

**Do not chase the headline number early.** It is entirely possible to hit
16,374 / 1,316 / 8.04% with a fact that is wrong in almost every other month. That is
precisely what happened on the original build.

**Do not skip the testing epic to get to the shiny parts.** The tests are where the
learning is.
