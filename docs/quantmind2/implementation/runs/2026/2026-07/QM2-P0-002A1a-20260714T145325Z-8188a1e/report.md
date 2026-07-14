# Implementation Report: QM2-P0-002A1a

## 1. Task Summary

`QM2-P0-002A1a — Persistence Mechanism Reality Audit` completed a read-only
static audit of QuantMind's actual ORM, engines, sessions, transactions,
migration paths, test database patterns, and database configuration. It records
an evidence-backed persistence selection for a future Implementation Ledger and
adds bounded consistency checks. It creates no persistence implementation.

## 2. Goal

Give `QM2-P0-002A1b` a factual base: identify which current PostgreSQL/
SQLAlchemy route should host Ledger contracts, distinguish formal service paths
from compatibility/test/deprecated paths, expose migration and transaction
risks, and preserve Git/ADR/PostgreSQL authority boundaries.

## 3. Scope

- Static source, import, caller, entrypoint, deployment, test, and configuration
  audit in the QuantMind repository.
- Formal reality document with explicit code-confirmed, engineering-choice,
  unconfirmed, and blocker labels.
- Project Memory updates without changing accepted ADRs.
- Validator and targeted context tests for evidence, handoff, accepted ADR
  immutability, and absence of Ledger runtime implementation.
- One immutable Implementation Run and one local commit.

## 4. Explicit Non-goals

No Ledger domain model, Repository interface, ORM model, database table,
migration, Manifest Indexer, Git consistency service, API, UI, TDX, Dataset
Snapshot, Factor DSL, Optimization, Validation runtime, Registry, LightGBM,
Qlib, business code, configuration, dependency, lockfile, or Factor Lab change.
No service, database, migration, Qlib, model, Electron, or campaign was run.

## 5. Preflight State

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`
- Base: `8188a1e78f0ff74f7beb49d3522c417ed76194fa`
- Dirty before: no
- Unrelated dirty files: none
- Factor Lab: clean at `c83192c2278767e03f008bc39197b1ba33bfb6a9`
- Factor Lab source stayed read-only.

## 6. Context Read Confirmation

The required sequence was read: repository `AGENTS.md`, Context Index, Charter,
Architecture v1, Research Decision Contract, Current State, Handoff, Component
Catalog, Known Issues, Roadmap, Database Schema Index, ADR Index, ADR-0005,
ADR-0007, ADR-0009, implementation protocol, and the full QM2-P0-001G report and
manifest.

Confirmed boundaries:

- Git and immutable Run manifests are implementation facts.
- Accepted ADRs are long-lived decisions.
- PostgreSQL is a future query/index projection and cannot replace Git truth.
- This task is audit-only.
- Decision, Control, and Execution authority does not change with persistence.

## 7. Audit Methodology and Search Strategy

Repository searches covered case variants and symbol forms of `sqlalchemy`,
`declarative_base`, `DeclarativeBase`, `sessionmaker`, `scoped_session`,
`AsyncSession`, `create_engine`, `create_async_engine`, `get_db`, `get_session`,
transactions, commit/rollback, Alembic/migrations, DDL, PostgreSQL/SQLite,
database environment keys, JSONB, BaseModel, and ORM.

Directories/files included `backend/`, `config/`, `data/`, `deploy/`,
`requirements/`, `docker-compose.yml`, service tests/fixtures, `.env.example`,
startup entrypoints, database health checks, runtime DDL, and model/backtest/task
persistence.

Formal call chains were established by:

1. resolving service processes from `backend/main_oss.py`;
2. reading API, Engine, Trade, and Stream lifespans;
3. following database initializer imports to engine/session factories;
4. tracing FastAPI dependencies and representative service consumers;
5. tracing `ensure_tables`/`create_all` to startup callers;
6. tracing SQL files to deploy/manual invocation evidence;
7. separating files under tests and modules explicitly marked deprecated;
8. avoiding imports where module-level engine construction could have side
   effects.

No conclusion relied only on a directory or dependency being present.

## 8. ORM Reality

| Item | Path | Symbol | Caller/use | Status | Evidence/risk |
| --- | --- | --- | --- | --- | --- |
| SQLAlchemy 2.0 | `requirements/production.txt` | production pin | packaged backend | formal | `2.0.25`; other requirements duplicate constraints |
| API Base | `backend/services/api/models/base.py` | `Base` | user/community models and schema registry | formal API | selected future Ledger metadata owner; no Ledger model exists |
| Engine Base | `backend/shared/database.py` | `Base` | market/tag/task models | formal/compatibility | coupled to sync engine module while async sessions dominate services |
| Trade Bases | `backend/services/trade/models/base.py`, portfolio and simulation model packages | three `Base` objects | schema registry/Trade startup | formal Trade | fragmented metadata; simulation alone uses `DeclarativeBase` |
| Stream Base | `backend/services/stream/market_app/models/base.py` | `Base` | stream service | formal Stream | service-local ownership |
| Schema registry | `backend/shared/schema_registry.py` | `SCHEMA_SPECS`, `create_registered_tables` | Trade startup | formal Trade | unifies discovery, not Base or migration history |
| AI strategy storage | `backend/services/engine/ai_strategy/storage/database.py` | `Base`, `StrategyRecord` | compatibility calls | deprecated | overlapping strategy tables and own engine |
| Stock query model engine | `backend/services/engine/stock_query_app/local_models.py` | `Base`, `engine`, `SessionLocal` | stock-query subsystem | optional/compatibility | module-level independent sync engine |

Model conventions are mixed: integer, bigint, string UUID, and PostgreSQL UUID
primary keys; client and server timestamps; optional soft delete; isolated
version columns; SQLAlchemy Enum and string status; JSON and PostgreSQL JSONB;
mostly public schema; inconsistent table prefixes; runtime raw tables outside
ORM declarations. There is no global authoritative Base or common record mixin.

## 9. Engine and Session Call Chains

Primary shared asynchronous chain:

```text
DATABASE_URL or DB_* environment
→ backend.shared.database_manager_v2.DatabaseConfig
→ DatabaseManager.initialize
→ master/optional slave AsyncEngine
→ async_sessionmaker(AsyncSession, expire_on_commit=False)
→ get_session(read_only flag)
→ API/Engine/Trade service
→ master outer commit or rollback
→ close
```

API:

```text
backend.services.api.main:lifespan
→ init_unified_config
→ init_default_databases (sync compatibility pool)
→ database_manager_v2.init_database
→ API dependencies and services
→ shared get_session
```

Engine:

```text
backend.services.engine.main:lifespan
→ init_unified_config
→ sync compatibility pool
→ model/qlib ensure_tables startup DDL
→ Engine persistence services use shared async get_session
```

Trade:

```text
backend.services.trade.main:lifespan
→ database_manager_v2.init_database
→ schema_registry.create_registered_tables(master engine)
→ manual execution ensure_tables
→ backend.services.trade.deps.get_db
→ shared get_session
```

Stream uses its own async engine/session. Celery mixes shared async persistence
via `asyncio.run()` with a special sync session and runtime dispatch-log DDL.
The shared sync pool closes sessions but leaves commit/rollback to callers.

## 10. Transaction Reality

The shared master context supplies a usable atomic unit: commit on normal exit,
rollback on exception, and close. However, many callers explicitly commit
inside this context. Sync pool callers own transactions individually. One
community audit path uses `begin_nested`; savepoints are not a general policy.
Read-only sessions may use replicas and can be stale after a write. Sessions are
shared as a mechanism across processes, never as the same object across
services.

The future repository contract must therefore be transaction-neutral: outer
application/unit-of-work owns commit/rollback, repository methods never commit,
and consistency-sensitive reconciliation uses the master. This is a future
contract choice, not code added here.

## 11. Migration Reality and Call Chain

Alembic packages are declared, but no `alembic.ini`, `env.py`, versions tree, or
deployment invocation was found. Alembic is not operationally confirmed.

Fresh install:

```text
deploy/deploy.sh:step10_init_database
→ docker exec ... psql
→ data/quantmind_init.sql
```

Incremental SQL evidence:

- `data/upgrade_v1.1.0.sql`
- `data/migrations/upgrade_v1.4.0_stock_tag.sql`

Both contain transaction wrappers and manual invocation documentation. No
ordered runner, applied-version table, checksums, or downgrade scripts were
found; actual deployment execution is unconfirmed.

Parallel formal startup DDL includes Trade metadata `create_all`, API/Engine
`ensure_tables`, model/Qlib persistence raw DDL, manual execution DDL, and
selected runtime `ALTER TABLE`. This fragmentation is recorded as a risk and is
rejected as the future Ledger migration authority.

## 12. Test Database Reality

The common conftest declares database/integration markers but no isolated
PostgreSQL fixture or rollback fixture. Selected tests use in-memory sync/async
SQLite. Many replace Session/get_session with mocks or async context fakes. No
shared in-memory repository or CI PostgreSQL service was found. Pure context
tests run under the current Python with standard `unittest`; repository
integration behavior was not executed.

Future safe layers are documented as pure A1b domain/fake tests, A2 static
metadata plus explicitly isolated PostgreSQL integration, A3 temporary Git plus
fake repository and isolated PostgreSQL, and API dependency override tests.
SQLite must not certify PostgreSQL schema, JSONB, concurrency, uniqueness, or
transaction behavior.

## 13. Configuration and Secret Handling

Database configuration is fragmented across the shared manager, sync pool,
legacy settings, unified YAML, Docker Compose, and service-local config. The
shared manager prefers `DATABASE_URL` then split `DB_*` variables and exposes
pool tuning. Consistent SSL behavior was not confirmed.

Credential-bearing defaults were found in Docker/config/legacy/background-task
paths. The report and audit intentionally name only paths and keys. One shared
manager log masks credentials by logging text after `@`; engine initialization
also logs the complete master URL and may disclose credentials. No secret value,
token, or complete credential-bearing URL is recorded in this Run.

## 14. Persistence Options Compared

| Option | Finding | Result |
| --- | --- | --- |
| Shared async SQLAlchemy/PostgreSQL | compatible, transactional, queryable, concurrent; migration automation incomplete | selected access mechanism |
| Runtime DDL | present but unordered, non-downgradable, drift-prone | rejected |
| Separate SQLite | easy tests but wrong deployment/concurrency/schema semantics | rejected |
| JSON-only Ledger | immutable Git artifacts remain authority but are insufficient as concurrent query index | rejected as sole index |
| Existing PostgreSQL with `quantmind2` schema | clear namespace without new secret/database domain | selected physical placement, privileges unconfirmed |

## 15. Recommended Ledger Persistence Mechanism

- ORM: SQLAlchemy 2.0 async.
- Base: `backend.services.api.models.base.Base` for future API-owned models.
- Engine: master AsyncEngine owned by
  `backend.shared.database_manager_v2.DatabaseManager`.
- Session: shared `get_session(read_only=False)` with outer transaction
  ownership and no repository-level commits.
- Migration: future versioned, transaction-wrapped PostgreSQL SQL in the
  existing `data/migrations` family, reconcilable with fresh-install bootstrap;
  never startup DDL.
- Placement: current PostgreSQL database, explicit `quantmind2` schema.
- Repository: future `backend/services/api/project_knowledge/` control-plane
  package.
- API: future thin dependency delegating to shared async session management.
- Tests: pure/fake contract, static schema checks, isolated PostgreSQL
  integration, then dependency-overridden API tests.

The choices are recorded only. No selected path/table/package/schema exists.
Before an A2 migration, deployment invocation, applied-version tracking,
schema privileges/search path, and failure recovery are blockers.

## 16. Files Added

- `docs/quantmind2/implementation/LEDGER_PERSISTENCE_REALITY_AUDIT_V1.md`
- this `report.md`
- adjacent `manifest.json`

## 17. Files Modified

- Current State, Component Catalog, Known Issues, Roadmap, Handoff, and Database
  Schema Index human documents.
- Their existing machine-readable JSON counterparts where present.
- Implementation Manifest v1 Schema received one minimal compatibility change:
  Run IDs now admit lowercase task suffixes such as the formal `A1a` task ID.
- `tools/quantmind2/validate_context_bootstrap.py`.
- `backend/services/tests/test_quantmind2_context_bootstrap.py`.

No accepted ADR, architecture file, business code, business-domain schema,
dependency, configuration, lockfile, SQL migration, or Factor Lab file changed.

## 18. Validator and Tests

The validator now checks audit existence/labels, twenty cited evidence paths,
accepted ADR hashes, absence of Project Knowledge runtime and Ledger migration,
absence of key persistence implementation markers, exact human A1b handoff,
legal machine parent task, and existing Factor Lab/source invariants.

Executed verification includes the context validator, 17 targeted unittests,
all QM2 JSON parsing, actual Run manifest validation, whitespace checks, static
forbidden-scope/diff checks, and read-only Factor Lab HEAD/status checks. Final
counts are recorded in the manifest after the Run validates.

## 19. Architecture, Security, and Data-Lineage Impact

Architecture decisions are unchanged. The audit maps the existing persistence
reality to ADR-0005/0007/0009 boundaries. Security impact is documentary: it
records credential defaults and possible URL logging without exposing values or
changing runtime. Data-lineage impact is none: no data moved; Git remains
authority and PostgreSQL remains a future rebuildable index.

## 20. Expected vs Actual

| Requirement | Expected | Actual | Evidence | Status |
| --- | --- | --- | --- | --- |
| ORM/Base audit | all mechanisms and ownership | multiple Bases/model families classified | audit sections 3/10 | passed |
| Engine/session call chains | API/Engine/tasks/test separation | shared async, sync compatibility, service-local, task paths traced | audit sections 4/10 | passed |
| Transactions | commit/rollback/nesting/pool | outer auto-commit and inner commit conflict documented | audit section 5 | passed |
| Migration | Alembic/SQL/runtime/callers | fresh bootstrap confirmed; upgrades/manual/runtime fragmentation classified | audit section 6 | passed |
| Test DB | SQLite/mocks/real PG risk | facts and safe future layers recorded | audit section 7 | passed |
| Secrets | keys/risks without values | config/logging risks recorded, no value emitted | audit section 8 | passed |
| Formal/legacy matrix | all mechanisms classified | matrix with owner/status/risk | audit section 10 | passed |
| Persistence choice | one explicit selection | async shared PG + API Base + versioned SQL + `quantmind2` schema | audit section 11 | passed |
| Alternatives | A-E comparison | all five compared | audit section 9 | passed |
| No implementation | no runtime/table/migration/API | validator and diff checks confirm | validator/tests | passed |
| Project Memory | accurate completion/non-implementation/A1b | human and machine docs updated | context files | passed |
| Factor Lab | read-only and clean | unchanged at expected commit | Git check | passed |

## 21. Known Limitations

- Static audit cannot prove live topology, actual installed package versions,
  deployed schema state, permissions, SSL, replica lag, or production call
  frequency.
- Actual execution/order of manual upgrade SQL is unconfirmed.
- CI PostgreSQL capability is unconfirmed.
- No database integration test ran, by design.
- The final `quantmind2` schema is an engineering choice whose privileges and
  operational approval remain unconfirmed.
- Migration version/checksum and downgrade policy remain unresolved.
- Context schema v1 cannot encode exact `QM2-P0-002A1b`; machine lists use legal
  parent `QM2-P0-002A1` and human docs record the exact task.
- The bounded validator is not a general JSON Schema implementation.
- The containing commit cannot be embedded in its own manifest; Git history
  resolves it after commit.

## 22. Unresolved Questions

- What controlled deployment command applies incremental migrations?
- How are applied versions/checksums and partial failures recorded/recovered?
- Can the deployment role create/use the `quantmind2` schema?
- What isolated PostgreSQL URL/schema and CI service will integration tests use?
- What are retention, rebuild SLA, backup, and disaster-recovery expectations
  for the derived Ledger index?
- Does formalizing a migration-version mechanism require a later ADR/operations
  approval? This task does not create one.

## 23. Compatibility and Rollback

The change is documentation plus bounded project-context validation. Existing
runtime imports, APIs, databases, services, models, data, and configuration are
unchanged. Revert the one containing commit to remove the audit/context/test
changes. No database, migration, data, dependency, API, UI, model, Qlib, or
Factor Lab rollback is needed.

## 24. Git and Self-Reference

At Run generation, the task is complete but uncommitted, so `result_commit` is
null and task status is `completed_uncommitted`. After the required commit, its
containing commit is resolved with:

```text
git log -1 --format=%H -- docs/quantmind2/implementation/runs/2026/2026-07/QM2-P0-002A1a-20260714T145325Z-8188a1e/manifest.json
```

## 25. Recommended Next Task

Only `QM2-P0-002A1b — Ledger Domain Objects and Repository Contract` is
recommended. It must be independent because domain identity, repository
operations, transaction ownership, and error semantics need reviewable
contracts before ORM/migration work. This task did not start it.

Suggested commit message:
`docs(qm2): audit ledger persistence mechanisms`.
