# Epic 5: Documentation

Stories BF-36 to BF-38. Anchor numbers as at **2024-09-13**: **16,374 passings / 1,316 subscribers / 8.04% penetration**. Business rules and the wrong-number table are in [`docs/BUSINESS_RULES.md`](../docs/BUSINESS_RULES.md). Traps are in [`docs/GOTCHAS.md`](../docs/GOTCHAS.md).

---

### BF-36: Descriptions on every model and column
**As a** data engineer **I want** a description on every model and every column **so that** the semantic layer and the agent have something true to stand on.

**Learning objective:** dbt documentation as an input to downstream systems rather than a deliverable for humans. In this architecture the descriptions become the agent's grounding, which means a sloppy description is a correctness problem.

**Acceptance criteria**
- [ ] Every model in `int` and `anl` has a `description`.
- [ ] Every column in `anl` has a `description`.
- [ ] `passings` and `subscribers` descriptions state explicitly that they are **cumulative point-in-time balances, not monthly flows**, and that summing across months is meaningless.
- [ ] The penetration definition states it is a **ratio of sums** and must never be averaged across markets.
- [ ] `'N/A'` is documented as a real, deliberate value meaning the source was blank, not as missing data.
- [ ] The `'12-31-2030'` sentinel is documented, including why it is in the future.

**Verification:** a script or query over `dbt/target/manifest.json` after `dbt compile` reports **0** models and **0** `anl` columns with an empty description.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-76

---

### BF-37: `persist_docs` into Snowflake
**As a** data engineer **I want** dbt descriptions persisted as Snowflake object and column comments **so that** the agent and any SQL user see them without opening dbt.

**Learning objective:** `persist_docs` config, and the idea that documentation must live where the consumer is. The Cortex agent reads Snowflake metadata, not the dbt docs site.

**Acceptance criteria**
- [ ] `dbt_project.yml` sets `persist_docs: {relation: true, columns: true}` for `anl` at minimum.
- [ ] After a rebuild, comments are present on the fact and all dimensions in Snowflake.
- [ ] A comment in the yml records that this is load-bearing for the agent, not cosmetic, so nobody removes it as noise.
- [ ] Re-running `dbt build` updates a changed description in Snowflake, confirming it is not a one-time write.

**Verification:** `select count(*) from brindle_dev_anl_db.information_schema.columns where table_name = 'FCT_PASSINGS_SUBSCRIBERS_MONTHLY' and (comment is null or comment = '')` returns **0**. Change one description, `dbt build`, and confirm the Snowflake comment reflects the new text.

**Estimate:** S  ·  **Track:** core  ·  **Depends on:** BF-36

---

### BF-38: Generate and review the docs site
**As a** data engineer **I want** the dbt docs site generated and the DAG reviewed **so that** the lineage is inspectable and no orphan or unexpected edge survives.

**Learning objective:** `dbt docs generate` / `dbt docs serve`, and reading the DAG as a review artifact. An unexpected edge in the graph is usually a modelling mistake you cannot see in any single file.

**Acceptance criteria**
- [ ] `dbt docs generate` succeeds.
- [ ] The DAG shows: 6 sources, then 3 `int` models, then 3 dimensions, 1 fact and 1 view. `dim_location` is a leaf: nothing reads it yet (see BF-25).
- [ ] No model is disconnected from the graph. The one expected exception is `dim_date`, a generated calendar with no source upstream.
- [ ] No `anl` model reads a `source()` directly. All go through `int`.
- [ ] The lineage screenshot or description is saved in `docs/`.

**Verification:** `dbt ls --select source:*+ --resource-type model` lists every model except `dim_date`, proving none is orphaned. `grep -l 'source(' dbt/models/anl/*.sql` returns **no files**.

**Estimate:** S  ·  **Track:** core  ·  **Depends on:** BF-37
