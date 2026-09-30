# Epic 8: BI presentation in Sigma (optional track)

Stories BF-47 to BF-52. Anchor numbers as at **2024-09-13**: **16,374 passings / 1,316 subscribers / 8.04% penetration**. Business rules and the wrong-number table are in [`docs/BUSINESS_RULES.md`](../docs/BUSINESS_RULES.md). Traps are in [`docs/GOTCHAS.md`](../docs/GOTCHAS.md).

---

### BF-47: Sigma API client and the region problem
**As a** data engineer **I want** an authenticated Sigma API client **so that** the workbook can be created programmatically instead of clicked.

**Learning objective:** API-first BI, and that an authentication error message is not always about authentication.

**Acceptance criteria**
- [ ] `sigma/sigma_api.py` handles OAuth token exchange and request retry.
- [ ] The base URL is configurable and the correct region is recorded. The reference build used **`https://api.sigmacomputing.com`**. Yours may differ.
- [ ] A comment records GOTCHA J: the API region is **not discoverable from the credentials**, and every wrong region returns `{"code":"invalid_request","message":"Invalid access/refresh token"}`, which reads like a credential problem but is a region problem.
- [ ] Credentials come from `sigma/.env`, which is gitignored.

**Verification:** a whoami or list-connections call returns **HTTP 200** with a JSON body. If it returns `invalid_request`, change the region before touching the credentials.

**Estimate:** M  ·  **Track:** sigma  ·  **Depends on:** BF-27

---

### BF-48: Sigma service user, connection and inventory sync
**As a** data engineer **I want** a Sigma connection to Snowflake whose inventory includes newly created objects **so that** `v_by_market_current` is actually addressable.

**Learning objective:** metadata caching in BI tools. A tool's view of your warehouse is a cached snapshot, and "not found" may mean "not refreshed".

**Acceptance criteria**
- [ ] `snowflake/bootstrap/` creates `brindle_sigma_user` with default role `brindle_bi_rl`, authenticating by key pair. The private key lives under `keys/`, which is gitignored. `USER` is not a DCM entity (GOTCHA F).
- [ ] A Sigma connection to Snowflake exists, authenticating as that service user.
- [ ] After creating or replacing `v_by_market_current`, the inventory is refreshed with `POST /v2/connections/{id}/sync` and body `{"path":["DB","SCHEMA"]}`.
- [ ] A comment records GOTCHA I: a view created two minutes earlier returns "Warehouse table not found" while older tables in the same schema resolve fine.
- [ ] The sync call is part of the deploy path, not a manual remedial step.

**Verification:** immediately after creating the view, list warehouse tables via the API: the view is **absent**. Call sync, list again: the view is **present**. Querying a raw table as `brindle_sigma_user` returns **"not authorized"**.

**Estimate:** M  ·  **Track:** sigma  ·  **Depends on:** BF-47

---

### BF-49: Workbook spec with table-prefixed column references
**As a** data engineer **I want** the workbook spec to reference physical columns table-prefixed **so that** cells render values instead of an unknown-column error.

**Learning objective:** the difference between schema validity and semantic validity. A spec can satisfy the schema and reference nothing that exists.

**Acceptance criteria**
- [ ] `sigma/workbook_by_market.json` sources from the `warehouse-table` `v_by_market_current`.
- [ ] Every column reference is **table-prefixed**: `[V_BY_MARKET_CURRENT/MARKET_NAME]`, never bare `[MARKET_NAME]`.
- [ ] A comment records GOTCHA G: a workbook validated with `{"valid": true}`, was created, then rendered `Unknown column "[MARKET_NAME]"` in **every single cell**. A bare reference passes verify and renders nothing.
- [ ] Penetration is a workbook-level calculation over the two measures, consistent with ratio-of-sums, not a column read from the warehouse.
- [ ] No bare `[COLUMN]` reference remains anywhere in the spec.

**Verification:** `grep -o '\[[A-Z_]*\]' sigma/workbook_by_market.json` returns **no** un-prefixed physical column references. After creation, an exported cell contains a market name, not `Unknown column`.

**Estimate:** M  ·  **Track:** sigma  ·  **Depends on:** BF-48

---

### BF-50: Bisect the `Invalid kind` error and keep filters out of Sigma
**As a** data engineer **I want** to reproduce and diagnose Sigma's `Invalid kind: "table"` error **so that** I understand why the month filter lives in dbt.

**Learning objective:** debugging a discriminated-union validator, and recognising that a filter belonging in the warehouse is an architectural improvement rather than a workaround.

**Acceptance criteria**
- [ ] `sigma/bisect_spec.py` submits progressively reduced specs to isolate the offending field.
- [ ] The bisection reproduces GOTCHA H: `Invalid kind: "table"` **never** means the kind is wrong. It means a field inside the element failed the union, and the validator can only report the discriminator.
- [ ] The finding is confirmed: source, columns, `format`, and `groupings` all validate, but **element-level `filters` on a table element does not**.
- [ ] The spec therefore contains **no** element-level `filters`. The month restriction is in `v_by_market_current` (BF-27).
- [ ] A comment records the upside: the filter becomes testable in dbt and Sigma stays presentation-only.

**Verification:** running the bisect script prints a pass/fail per field, with exactly **one** failing field: `filters`. `grep -c '"filters"' sigma/workbook_by_market.json` returns **0**.

**Estimate:** M  ·  **Track:** sigma  ·  **Depends on:** BF-49

---

### BF-51: Create the workbook and export its data
**As a** data engineer **I want** the workbook created and its data exported **so that** rendering is proven by values rather than by a validation response.

**Learning objective:** verify at the output, not at the gate. `{"valid": true}` is the gate, and exported data is the output.

**Acceptance criteria**
- [ ] The workbook is created via the API from `sigma/workbook_by_market.json`.
- [ ] Its data is **exported** as CSV or JSON and inspected.
- [ ] The export has 6 market rows plus a total.
- [ ] No cell contains `Unknown column`.
- [ ] A note states that `spec/verify` returning `{"valid": true}` was not sufficient evidence, and that creation plus export is the minimum bar.

**Verification:** the export contains **6** market rows, `sum(passings)` = **16374**, `sum(subscribers)` = **1316**, penetration = **8.04%**. `grep -c 'Unknown column' <export>` returns **0**.

**Estimate:** M  ·  **Track:** sigma  ·  **Depends on:** BF-50

---

### BF-52: Reconcile Sigma against the fact, market by market
**As a** data engineer **I want** the Sigma export compared per market against the warehouse **so that** Sigma is confirmed at row level, not just in total.

**Learning objective:** total-level reconciliation is necessary but not sufficient. Two offsetting per-market errors produce a correct total, which is a variant of the defect-A lesson.

**Acceptance criteria**
- [ ] A per-market comparison of the export against `v_by_market_current` shows zero differences in passings and subscribers.
- [ ] Sigma's penetration matches the ratio of sums per market, and the total is not the mean of the six.
- [ ] The comparison output is saved for BF-53.
- [ ] The note records why the per-market check exists and not just the total.

**Verification:** the comparison reports **0** differing rows across 6 markets. Sigma's total penetration reads **8.04%**, and is confirmed not to equal the unweighted mean of the per-market ratios.

**Estimate:** S  ·  **Track:** sigma  ·  **Depends on:** BF-51
