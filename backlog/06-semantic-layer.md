# Epic 6: Semantic layer

Stories BF-39 to BF-42. Anchor numbers as at **2024-09-13**: **16,374 passings / 1,316 subscribers / 8.04% penetration**. Business rules and the wrong-number table are in [`docs/BUSINESS_RULES.md`](../docs/BUSINESS_RULES.md). Traps are in [`docs/GOTCHAS.md`](../docs/GOTCHAS.md).

---

### BF-39: Semantic view skeleton in DCM
**As a** data engineer **I want** the semantic view declared in the DCM project **so that** the business-facing definition is version-controlled alongside the rest of the Snowflake estate.

**Learning objective:** Snowflake semantic views (tables, relationships, facts, dimensions, metrics) and managing a Preview entity declaratively.

**Acceptance criteria**
- [ ] `snowflake/dcm_project/sources/definitions/12_semantic_views.sql` declares the view over the fact, `dim_market` and `dim_date`. `dim_location` stays out, because the fact is at market grain and has no location key.
- [ ] Relationships are declared from fact to each dimension.
- [ ] The calendar dimension is **aliased** (for example `calendar`) so it can be referenced explicitly. This alias is what makes BF-40 possible.
- [ ] Dimension and metric descriptions are carried through from the dbt descriptions, not rewritten from memory.
- [ ] `snow dcm plan` shows the semantic view as a create with no error.

**Verification:** `snow dcm deploy`, then `SHOW SEMANTIC VIEWS IN SCHEMA brindle_dev_anl_db.anl` returns **exactly one** row.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-38

---

### BF-40: Table-qualify `NON ADDITIVE BY`
**As a** data engineer **I want** `NON ADDITIVE BY` fully table-qualified **so that** the balance semantics bind to the calendar dimension and not to the fact's own same-named columns.

**Learning objective:** `NON ADDITIVE BY` as the mechanism that stops a point-in-time balance being summed across time, and the harder lesson that **the unqualified form compiles and is wrong**.

**Acceptance criteria**
- [ ] The clause reads `NON ADDITIVE BY (calendar.year_month, calendar.month_end_date, calendar.year_number)`.
- [ ] No bare column name appears in that clause.
- [ ] A comment records GOTCHA C in full: written unqualified, `year_month` and `month_end_date` silently bound to the **fact's own** columns because the fact happens to have columns of those names. Only `year_number` errored, because the fact has no such column, so the error pointed at the least interesting of the three terms and the two real problems stayed silent.
- [ ] The project rule is stated: always table-qualify in this clause, even when it looks redundant.

**Verification:** `grep -n 'NON ADDITIVE BY' snowflake/dcm_project/sources/definitions/12_semantic_views.sql` shows every term prefixed with `calendar.`. Then query the semantic view across two months and confirm the balance measure is **not** summed: the two-month result equals the later month's balance, not the sum of both.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-39

---

### BF-41: Reconcile the semantic view to the anchor numbers
**As a** data engineer **I want** the semantic view to return 16,374 / 1,316 / 8.04% **so that** the semantic view is confirmed as a surface in its own right.

**Learning objective:** semantic-layer verification as a distinct activity. The semantic view is a second implementation of the business rules and can disagree with the fact it sits on.

**Acceptance criteria**
- [ ] A semantic-view query for 2024-09-13 returns the three anchor numbers.
- [ ] Per-market passings and subscribers match the fact market by market, not just in total.
- [ ] Penetration from the semantic view is confirmed to be a ratio of sums.
- [ ] The query used is saved in `docs/` for the BF-53 reconciliation record.

**Verification:** the semantic-view query returns **16374**, **1316**, **0.0804**. A six-row per-market comparison against `v_by_market_current` shows **zero** differing rows.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-40

---

### BF-42: Prove the semantic view resists the two aggregation traps
**As a** data engineer **I want** explicit evidence that the semantic view refuses to sum balances across months or average per-market ratios **so that** the agent built on it inherits correct behaviour rather than luck.

**Learning objective:** semantic layers as guardrails. The value of the layer is not convenience. It is that it makes a wrong question hard to ask.

**Acceptance criteria**
- [ ] A query aggregating the balance over several months returns the **latest balance**, not a sum, courtesy of `NON ADDITIVE BY`.
- [ ] A query for total penetration returns the ratio of sums, and this is shown to differ from the unweighted mean of the six per-market ratios.
- [ ] Both results are recorded with the actual numbers, since these become the agent evals in BF-45.
- [ ] Any trap the semantic view does **not** prevent is written down as a residual risk the agent instructions must handle.

**Verification:** a 3-month aggregate of `subscribers` over 2024-07 to 2024-09 returns **1316**, the final month's balance, not **3062**, the sum. Total penetration returns **0.0804**, and the unweighted mean of per-market ratios returns **0.0870**. Record both.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-41
