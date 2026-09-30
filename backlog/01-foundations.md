# Epic 1: Foundations and environment

Stories BF-01 to BF-08. Anchor numbers as at **2024-09-13**: **16,374 passings / 1,316 subscribers / 8.04% penetration**. Business rules and the wrong-number table are in [`docs/BUSINESS_RULES.md`](../docs/BUSINESS_RULES.md). Traps are in [`docs/GOTCHAS.md`](../docs/GOTCHAS.md).

**BF-01 is required.** BF-02 is option B only (Fivetran). **BF-03 to BF-08 are the optional platform track:** DCM, warehouses declared in full, and two-plane RBAC. Skip them and create the account with BF-70 instead. Epic 3 does not care which one you did, as long as the three databases and `brindle_transform_rl` exist.

---

### BF-01: Repo scaffold
**As a** data engineer **I want** the rest of the repository structure in place **so that** every later story has an obvious home and nothing lands in an ad hoc folder.

**Learning objective:** project layout as an architectural statement. The top-level split (`data/`, `postgres/`, `aws/`, `snowflake/`, `dbt/`, `sigma/`, `docs/`) follows the data flow, and `snowflake/` is split into `dcm_project/` and `bootstrap/` because DCM cannot manage everything (GOTCHA F).

**Acceptance criteria**
- [ ] The repo is under git, and the starter kit (`data/`, `postgres/`, `snowflake/raw/`, `.gitignore`) is your first commit, untouched.
- [ ] Directories exist: `snowflake/bootstrap/`, `dbt/models/{int,anl}`, `dbt/macros/{utils,infrastructure}`, `dbt/tests/generic`, `dbt/snapshots`. Add `snowflake/dcm_project/sources/{macros,definitions}` only on the platform track. Add `aws/`, `fivetran/`, `snowflake/agents/` and `sigma/` only when you start those tracks.
- [ ] The provided `.gitignore` is in place. It excludes `.venv`, `dbt/target`, `dbt/logs`, `dbt/dbt_packages`, `dbt/prod-manifest/`, `keys/`, `*.p8`, `.env` and `aws/.brindle-pg-credentials`.
- [ ] No credential file is tracked by git.
- [ ] A `NOTES.md` at the root opens with one paragraph, in your own words, stating the business goal and the three anchor numbers. You will add to it all the way through.

**Verification:** `git ls-files | grep -cE '\.p8$|\.env$|credentials'` returns **0**, and `python data/generate_data.py --check` prints `OK: data/csv matches the generator`.

**Estimate:** S  ·  **Track:** core  ·  **Depends on:** none

---

### BF-02: AWS networking prerequisites
**As a** data engineer **I want** a VPC, two-AZ DB subnet group, and a security group prepared **so that** an RDS instance can actually be created and reached.

**Learning objective:** RDS networking constraints, and that an infrastructure precondition failure often surfaces as an unrelated-looking API error.

**Acceptance criteria**
- [ ] A VPC with subnets in **at least two availability zones** is identified. GOTCHA L: DB subnet groups require two AZs even for `--no-multi-az`. In the reference build, two of three candidate VPCs were single-AZ and unusable.
- [ ] A DB subnet group is created spanning those two AZs.
- [ ] A security group allows inbound 5432 from your workstation IP **and** from the Fivetran egress ranges for your region.
- [ ] Chosen VPC / subnet / security-group IDs are recorded in `aws/provision.sh` as variables, not pasted inline at each call site.

**Verification:** `aws rds describe-db-subnet-groups --db-subnet-group-name <name> --query 'DBSubnetGroups[0].Subnets[].SubnetAvailabilityZone.Name'` returns **two distinct AZ names**.

**Estimate:** S  ·  **Track:** aws  ·  **Depends on:** BF-01

---

### BF-03: The `BRINDLE_` prefix decision
**As a** data engineer **I want** every object this project creates to be `BRINDLE_`-prefixed **so that** we neither collide with nor silently attach to the 182 other databases in the shared account the reference build ran in.

**Learning objective:** naming as a safety mechanism on shared infrastructure. An unprefixed generic name like `deployer_rl` does not fail loudly. It resolves to somebody else's object and starts working, which is worse.

Working in your own trial account? Do it anyway. The habit is the point, and your first shared account will not warn you.

The one exception is `snowflake_intelligence.agents`, a location Snowflake requires for agents (optional track). Only the agent inside it carries the prefix, and teardown leaves that database in place.

**Acceptance criteria**
- [ ] A short decision record in `docs/` states the rule, the 182-database context, and the failure mode being avoided.
- [ ] `snowflake/dcm_project/sources/macros/naming_macro.sql` centralises prefixing so no definition file hardcodes the literal prefix.
- [ ] All warehouses, databases, account roles, and database roles carry the prefix.
- [ ] The rule covers service users and the agent, which live outside DCM.

**Verification:** after Phase 0 deploy, `SHOW DATABASES` / `SHOW WAREHOUSES` / `SHOW ROLES` filtered to this project's objects yields **zero** unprefixed names. Grep the DCM sources: the literal string `BRINDLE` appears only in `naming_macro.sql`.

**Estimate:** S  ·  **Track:** platform  ·  **Depends on:** BF-01

---

### BF-04: Snowflake bootstrap and deployer role privileges
**As a** data engineer **I want** an imperative bootstrap script that creates the deployer role with the privileges DCM needs **so that** `snow dcm plan` can run at all.

**Learning objective:** the boundary between imperative bootstrap and declarative management. Something has to create the thing that runs the declarative tool, and that something cannot itself be declarative.

**Acceptance criteria**
- [ ] `snowflake/bootstrap/01_bootstrap.sql` creates `brindle_deployer_rl`.
- [ ] It grants `MANAGE GRANTS ON ACCOUNT`.
- [ ] It grants `IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE`.
- [ ] It creates `brindle_deploy_wh` (XSMALL, auto-suspend 60) and grants the deployer `USAGE` on it. DCM cannot run before a warehouse exists, so this one warehouse is imperative.
- [ ] It creates `brindle_admin_db`, which holds the DCM project object, and grants the deployer ownership of it.
- [ ] **It grants the role ownership of itself:** `GRANT OWNERSHIP ON ROLE brindle_deployer_rl TO ROLE brindle_deployer_rl COPY CURRENT GRANTS;` (GOTCHA D). Without this, `snow dcm plan` fails with "Insufficient privileges to operate on role X. Your primary role X must have OWNERSHIP granted on ROLE X", because DCM `DEFINE`s the `project_owner` role.
- [ ] The script is idempotent, so it is safe to re-run.
- [ ] A comment in the file explains *why* the self-ownership grant exists, since it looks like a mistake.

**Verification:** as the deployer role, `SHOW GRANTS ON ROLE brindle_deployer_rl` lists a row with `privilege = 'OWNERSHIP'` and `grantee_name = 'BRINDLE_DEPLOYER_RL'`. Then `snow dcm plan` proceeds past the privilege check.

**Estimate:** M  ·  **Track:** platform  ·  **Depends on:** BF-03

---

### BF-05: DCM project skeleton and first plan
**As a** data engineer **I want** a DCM project with a manifest and ordered definition files **so that** Snowflake objects are declared in version control rather than clicked.

**Learning objective:** declarative object management with DCM: `manifest.yml`, numbered source files for ordering, `snow dcm plan` versus `snow dcm deploy`, and the Supported Entities table as something you check *before* designing (GOTCHA F).

**Acceptance criteria**
- [ ] `snowflake/dcm_project/manifest.yml` lists the definition sources in deterministic order.
- [ ] Definitions are numbered by dependency: `01_warehouses.sql`, `02_databases.sql`, `03_database_roles.sql`, `04_functional_roles.sql`, `12_semantic_views.sql`.
- [ ] The DCM Supported Entities documentation has been read, and the finding recorded: Semantic View is supported (Preview), **`AGENT` and `USER` are not**.
- [ ] A decision record states that consequence: the semantic view lives in DCM, and the agent plus service users live in `snowflake/bootstrap/` as imperative SQL.

**Verification:** `snow dcm plan` on `snowflake/dcm_project/` exits **0** and writes a plan describing the objects it would create. No privilege error.

**Estimate:** M  ·  **Track:** platform  ·  **Depends on:** BF-04

---

### BF-06: Warehouses with every property declared
**As a** data engineer **I want** warehouses whose properties are fully declared, including ones equal to the account default **so that** DCM cannot silently revert them.

**Learning objective:** declarative tools reconcile to the declaration, and an omitted property is not "leave it alone". It is "set it to the engine default".

**Acceptance criteria**
- [ ] `01_warehouses.sql` declares `brindle_ingest_wh`, `brindle_transform_wh` and `brindle_anl_wh`, each with size, auto-suspend, auto-resume, and **`enable_query_acceleration` explicitly**, even where the value matches the default.
- [ ] A comment records GOTCHA E: a warehouse that does not declare `enable_query_acceleration` gets DCM's default on every deploy, whatever value it had before, and the plan shows no diff to point at.
- [ ] The rule is written down as project policy: declare every property on every warehouse.

**Verification:** `snow dcm deploy`, then `SHOW WAREHOUSES LIKE 'BRINDLE_TRANSFORM_WH'`. The `enable_query_acceleration` column equals the declared value. Re-run `snow dcm plan` and it reports **no drift**.

**Estimate:** S  ·  **Track:** platform  ·  **Depends on:** BF-05

---

### BF-07: Databases and the two-plane RBAC model
**As a** data engineer **I want** three databases and a two-plane role model **so that** object privileges live on database roles and account roles stay thin.

**Learning objective:** two-plane RBAC. Database roles carry object privileges, and account roles are thin bundles that grant database roles. This keeps grant sprawl inside the database it belongs to.

**Acceptance criteria**
- [ ] Three databases: `brindle_dev_raw_db`, `brindle_dev_int_db`, `brindle_dev_anl_db`.
- [ ] `03_database_roles.sql` defines per-database roles carrying the object privileges.
- [ ] `04_functional_roles.sql` defines the account roles, which only bundle database roles:
  - `brindle_ingest_rl` owns the `raw` schema in the raw database and nothing else (the loader, or Fivetran), because the loader creates its own tables, stage and file format
  - `brindle_transform_rl` reads raw, writes int and anl (dbt)
  - `brindle_bi_rl` reads int and anl (Sigma, the agent, analysts)
- [ ] Each role gets `USAGE` on its own warehouse: `brindle_ingest_rl` on `brindle_ingest_wh`, `brindle_transform_rl` on `brindle_transform_wh`, `brindle_bi_rl` on `brindle_anl_wh`.
  - `brindle_deployer_rl` is created by bootstrap and then managed here (GOTCHA D)
- [ ] `brindle_bi_rl` declares `layers: [int, anl]`.
- [ ] A comment records the trap: **omitting `layers` grants raw rather than withholding it**. The default is permissive, not restrictive.
- [ ] `sources/macros/db_roles_macro.sql` generates the grants so they cannot drift per-database.

**Verification:** `SHOW GRANTS TO ROLE brindle_bi_rl` lists database roles for int and anl, and **no** raw database role.

**Estimate:** M  ·  **Track:** platform  ·  **Depends on:** BF-06

---

### BF-08: Prove the RBAC negative case
**As a** data engineer **I want** an executed negative test showing `brindle_bi_rl` cannot see raw **so that** the permissive-default trap is caught by evidence rather than by reading yml.

**Learning objective:** access control is only correct if the negative case is asserted. A grant you can see proves nothing about a grant you cannot.

**Acceptance criteria**
- [ ] Using a session with `brindle_bi_rl` as the only active role, a query against a raw table fails.
- [ ] The failure is an authorization error, not "table not found for a different reason".
- [ ] The same session **can** read from int and anl.
- [ ] The commands and outputs are recorded in `docs/`.

**Verification:** `USE ROLE brindle_bi_rl; SELECT count(*) FROM brindle_dev_raw_db.raw.markets;` returns an **"Object does not exist or not authorized"** error. The equivalent query against `brindle_dev_anl_db` returns a row count.

**Estimate:** S  ·  **Track:** platform  ·  **Depends on:** BF-07
