# Epic 7: AI agent (optional track)

Stories BF-43 to BF-46. Anchor numbers as at **2024-09-13**: **16,374 passings / 1,316 subscribers / 8.04% penetration**. Business rules and the wrong-number table are in [`docs/BUSINESS_RULES.md`](../docs/BUSINESS_RULES.md). Traps are in [`docs/GOTCHAS.md`](../docs/GOTCHAS.md).

---

### BF-43: Agent bootstrap
**As a** data engineer **I want** the agent created imperatively **so that** the DCM gap is handled on purpose instead of discovered mid-deploy.

**Learning objective:** knowing the limits of your declarative tool. `AGENT` and `USER` are not DCM-supported entities (GOTCHA F), so they must be managed elsewhere, and that boundary should be written down rather than implied.

**Acceptance criteria**
- [ ] `snowflake/bootstrap/` contains the agent creation SQL, run after the semantic view exists.
- [ ] A comment states that `AGENT` and `USER` are not DCM-supported entities, and that this was established by reading the Supported Entities table rather than by a failed deploy.
- [ ] `brindle_bi_rl` is granted usage on the agent. It can read the semantic view and nothing in raw.
- [ ] Scripts are idempotent.

**Verification:** as `brindle_bi_rl`, `describe agent snowflake_intelligence.agents.brindle_general_agent` succeeds. The same session querying a raw table returns **"not authorized"**.

**Estimate:** M  ·  **Track:** agent  ·  **Depends on:** BF-42

---

### BF-44: Agent definition grounded on the semantic view
**As a** data engineer **I want** a Cortex agent configured against the semantic view **so that** business users can ask the report question in natural language.

**Learning objective:** agent grounding. The agent's accuracy is a function of the semantic view's structure and the column comments from `persist_docs`, which is why BF-36 and BF-37 came first.

**Acceptance criteria**
- [ ] `snowflake/agents/brindle_general_agent.json` defines the agent against the semantic view.
- [ ] Instructions state that `passings` and `subscribers` are cumulative point-in-time balances and must not be summed across months.
- [ ] Instructions state that penetration is a ratio of sums and must never be averaged across markets.
- [ ] Instructions state the default as-of date, 2024-09-13.
- [ ] Instructions tell the agent to decline out-of-scope questions rather than infer.
- [ ] The agent has no access to raw.

**Verification:** ask the agent "what is penetration by market as at 2024-09-13". It returns six markets whose totals reconcile to **16,374 / 1,316 / 8.04%**.

**Estimate:** M  ·  **Track:** agent  ·  **Depends on:** BF-43

---

### BF-45: Agent evaluations, including the two traps
**As a** data engineer **I want** a stored eval set covering the happy path, both aggregation traps, and an out-of-scope question **so that** agent quality is measured rather than vibed.

**Learning objective:** evaluating an AI surface with deliberate adversarial cases. The traps are the two errors a human analyst makes on this dataset, so they are the right tests.

**Acceptance criteria**
- [ ] `snowflake/agents/evals/q01_happy_path.json`: the happy path, penetration by market at the as-of date.
- [ ] `snowflake/agents/evals/q02_sum_trap.json`: a question that invites summing a point-in-time balance across months. The agent must not sum.
- [ ] `snowflake/agents/evals/q03_ratio_trap.json`: a question that invites averaging per-market penetration. The agent must return the ratio of sums.
- [ ] `snowflake/agents/evals/q04_out_of_scope.json`: something the data cannot answer. The agent must decline, not invent.
- [ ] Each eval records the expected answer with concrete numbers, not a description.

**Verification:** all four evals pass. Specifically: q01 returns **16,374 / 1,316 / 8.04%**. q02's answer equals the **final month's balance**, not a multi-month sum. q03 returns **8.04%**, not the unweighted mean of **8.70%**. q04 produces a refusal with **no** fabricated numbers.

**Estimate:** M  ·  **Track:** agent  ·  **Depends on:** BF-44

---

### BF-46: Agent optimization log
**As a** data engineer **I want** a written record of what changed the agent's behaviour **so that** prompt and grounding changes are knowledge rather than folklore.

**Learning objective:** iterating on grounding rather than on prompt wording. Most agent failures in this project were fixed by improving the semantic view or a column comment, not by rephrasing instructions.

**Acceptance criteria**
- [ ] `snowflake/agents/optimization_log.md` records each change, what it was meant to fix, and whether it worked.
- [ ] Failures traced to grounding (a missing or wrong column description) are distinguished from failures traced to instructions.
- [ ] At least one entry shows a fix applied in the **semantic view or dbt description** rather than the prompt.
- [ ] Unresolved behaviours are listed as known limitations, with the eval that exposes them.

**Verification:** the log contains a dated entry per change, and for each a before/after eval outcome. A reader can point to one entry and say which layer was changed.

**Estimate:** S  ·  **Track:** agent  ·  **Depends on:** BF-45
