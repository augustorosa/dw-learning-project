# Epic 9: Verification and handoff

Stories BF-53 to BF-57. Anchor numbers as at **2024-09-13**: **16,374 passings / 1,316 subscribers / 8.04% penetration**. Business rules and the wrong-number table are in [`docs/BUSINESS_RULES.md`](../docs/BUSINESS_RULES.md). Traps are in [`docs/GOTCHAS.md`](../docs/GOTCHAS.md).

---

### BF-53: The reconciliation record
**As a** data engineer **I want** one document showing the same three numbers from every surface I built **so that** the build is demonstrably correct rather than asserted to be.

**Learning objective:** independent verification. Several surfaces implementing the same rules are several chances to disagree, and the value is in having checked.

**Acceptance criteria**
- [ ] A table in `NOTES.md` with one row per surface: the raw source (raw tables in the core track, Postgres in the AWS track), the dbt fact, the semantic view, plus Sigma and the agent if you did those tracks. NetSuite track: a second table for capex paid to date and capex per passing, with the hand-written query from BF-68.
- [ ] Each row records the actual query or API call used and the value returned.
- [ ] Every surface reads **16,374 / 1,316 / 8.04%**.
- [ ] The raw-source figure is derived with the business rules applied **by hand** in SQL. Copying the dbt logic verifies nothing.
- [ ] The hand-written query is extended to every month and market, and compared to the fact **row by row**, all 270 rows. This is the check that catches the history bugs a monotonicity test cannot (see the end of BF-31).
- [ ] Any discrepancy found and resolved during this exercise is recorded, not quietly fixed.

**Verification:** the document has one row per surface, one distinct query each, and one identical triple of numbers. The 270-row comparison returns **0** differing rows. A reviewer can re-run any row and get the same answer.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-42, plus BF-45, BF-52 and BF-69 if you did those tracks

---

### BF-54: Full rebuild from scratch
**As a** data engineer **I want** the whole stack rebuilt from an empty state in one pass **so that** the reproducibility claim is tested rather than believed.

**Learning objective:** idempotency across the whole pipeline. Every step in this project claims to be re-runnable. This is the story that finds out.

**Acceptance criteria**
- [ ] Tear everything down (by hand from the list in `docs/REFERENCE_RUNBOOK.md`, since BF-56 scripts it later), then rebuild everything you built: bootstrap, DCM deploy, raw load (or AWS, Postgres load and your loader), the NetSuite load if you did that track, `dbt build`, `dbt snapshot`, then the semantic view, and the agent and workbook if you did those tracks.
- [ ] No manual intervention outside documented steps.
- [ ] The anchor numbers come out identical, which also re-proves the generator's determinism.
- [ ] Every manual step discovered during the rebuild is either scripted or added to the runbook.
- [ ] Elapsed time is recorded, so the next person can plan.

**Verification:** after a clean rebuild, the BF-53 reconciliation is re-run and every surface again reads **16,374 / 1,316 / 8.04%**.

**Estimate:** L  ·  **Track:** core  ·  **Depends on:** BF-53

---

### BF-55: Runbook
**As a** data engineer **I want** an operational runbook **so that** somebody who did not build this can run it on a Tuesday morning.

**Learning objective:** operability as a deliverable. A correct pipeline nobody can operate is not finished.

**Acceptance criteria**
- [ ] Daily operation: what runs, in what order, and how you know it worked.
- [ ] Failure playbooks for at least: source freshness warn, a failing test, a DCM plan diff, and (Sigma track) a Sigma render failure.
- [ ] Each playbook names the first diagnostic command to run.
- [ ] The teardown path is documented, including what it does **not** remove (AWS track: `aws/teardown.sh` too).
- [ ] Cost notes: warehouse sizing and auto-suspend, and (AWS track) the RDS instance being the standing cost.

**Verification:** someone who has not touched the project follows the runbook to complete one daily cycle and produce the anchor numbers, without asking a question that is not answered in the document.

**Estimate:** M  ·  **Track:** core  ·  **Depends on:** BF-54

---

### BF-56: Teardown verified clean
**As a** data engineer **I want** teardown to leave no orphans **so that** the account and the bill stay clean.

**Learning objective:** dependency-ordered destruction. Teardown order is the inverse of creation order, and partial teardown is how shared accounts end up with 182 databases.

**Acceptance criteria**
- [ ] A Snowflake teardown path removes the `BRINDLE_`-prefixed databases, warehouses, account roles and database roles, including `brindle_admin_db` and `brindle_deploy_wh` from bootstrap.
- [ ] Agent track: the agent is dropped. Sigma track: `brindle_sigma_user`, the workbook and the connection are removed.
- [ ] AWS track: `aws/teardown.sh` removes the RDS instance, then the DB subnet group, then the security group, in that order.
- [ ] Teardown is idempotent: a second run does not error on already-absent objects.
- [ ] Anything teardown deliberately leaves behind is documented.

**Verification:** after teardown, `SHOW DATABASES LIKE 'BRINDLE%'`, `SHOW WAREHOUSES LIKE 'BRINDLE%'`, `SHOW ROLES LIKE 'BRINDLE%'` and `SHOW USERS LIKE 'BRINDLE%'` each return **0** rows. AWS track: `aws rds describe-db-instances` shows **no** Brindle instance.

**Estimate:** S  ·  **Track:** core  ·  **Depends on:** BF-55

---

### BF-57: Handoff notes: shortcuts, honestly
**As a** data engineer **I want** every shortcut and known gap written down **so that** the next person is not misled by the parts that look finished and are not.

**Learning objective:** honest handoff. An undocumented shortcut is a trap set for a colleague.

**Acceptance criteria**
- [ ] Shortcuts recorded, including at minimum:
  - **Fivetran was never wired up.** The BF-13 CSV load, or your own loader, stands in for BF-14.
  - Dev only. No prod promotion was exercised.
  - The custom `generate_database_name` has never run against a second environment.
  - Anything you skipped or stubbed yourself.
- [ ] Each shortcut names the story that does it properly.
- [ ] Agent track: known limitations from `snowflake/agents/optimization_log.md` are carried forward.
- [ ] Any story in this backlog whose verification you could **not** actually perform is listed. That is a defect in the backlog and the next person needs to know.
- [ ] The stretch goals from `docs/PROJECT_PLAN.md` are restated with your view of the effort now you have built it.

**Verification:** the notes list every shortcut with a story reference. A reader can answer "what in here is not production-ready?" from this document alone, without reading the code.

**Estimate:** S  ·  **Track:** core  ·  **Depends on:** BF-56
