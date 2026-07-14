# Implementation Ledger Persistence Reality Audit v1

Status: completed static audit  
Task: `QM2-P0-002A1a — Persistence Mechanism Reality Audit`  
Audit base: `8188a1e78f0ff74f7beb49d3522c417ed76194fa`  
Audit date: 2026-07-14

This document distinguishes four evidence labels:

- **【代码确认】**: directly established by repository source and import/call
  tracing at the audit base.
- **【工程选择】**: the persistence choice recommended for the future Ledger;
  it is not implemented by this task.
- **【尚未确认】**: cannot be proved by static repository evidence.
- **【阻断风险】**: must be resolved before a production migration or database
  rollout can be declared safe.

## 1. Audit Scope

The audit searched the repository for SQLAlchemy, declarative bases, sync and
async engines, session factories, FastAPI dependencies, transactions,
`commit`/`rollback`, Alembic, migration files, SQL DDL, PostgreSQL, SQLite,
database configuration, pool settings, JSON/JSONB, test fixtures, service
entrypoints, and background tasks. The scan covered `backend/`, `config/`,
`data/`, `deploy/`, `requirements/`, `docker-compose.yml`, tests, and root
Python/tool configuration.

Classification used actual imports and entrypoint calls, not file names alone:

1. `backend/main_oss.py` identifies the API, Engine, Trade, and Stream process
   entrypoints.
2. Each service lifespan was traced to database initialization.
3. Session dependencies were traced into representative services and routers.
4. DDL files and runtime DDL were traced to deploy scripts or startup calls.
5. Test-only SQLite and mocks were separated from production imports.
6. Modules explicitly marked deprecated or no longer routed were classified as
   compatibility/deprecated even though importable code remains.

No module was imported for this audit, no service was started, and no database
connection or migration was executed.

## 2. Repository and Commit

| Repository | Branch | Commit | State at preflight |
| --- | --- | --- | --- |
| QuantMind | `master` | `8188a1e78f0ff74f7beb49d3522c417ed76194fa` | clean |
| Official Factor Lab donor | `factor-lab/real-bounded-v7-orchestrator-v1` | `c83192c2278767e03f008bc39197b1ba33bfb6a9` | clean, read-only |

The only official Factor Lab source remains
`/tmp/quantmind_factor_lab_real_bounded_v7_orchestrator_v1/backend/services/engine/factor_lab/`.
Factor Lab is not a persistence authority for the Implementation Ledger.

## 3. ORM Reality

### 3.1 SQLAlchemy and versions

**【代码确认】** QuantMind uses SQLAlchemy in both synchronous and asynchronous
modes. `requirements/production.txt` pins `sqlalchemy==2.0.25`, `asyncpg==0.29.0`,
and `psycopg2-binary==2.9.9`. `requirements/database.txt` declares compatible
minimums and Alembic, while root `requirements.txt` contains unpinned duplicates.
The production pin is the strongest packaged runtime evidence; installed
runtime versions were not queried.

### 3.2 Declarative bases and model families

There is no repository-wide authoritative `Base`.

| Base/model family | Importers/callers | Current use | Classification | Risk |
| --- | --- | --- | --- | --- |
| `backend/services/api/models/base.py:Base` | API user and community models; `backend/shared/schema_registry.py` | API/user/community ORM metadata | formal API main-chain | One Base for two API domains, but not Engine/Trade |
| `backend/shared/database.py:Base` | `backend/services/engine/models/{market_data,stock_tag,task}.py` | Engine core ORM models | formal Engine model family; sync compatibility Base | Base lives beside a separate sync engine while runtime services often use the async manager |
| `backend/services/trade/models/base.py:Base` | trade order/risk/snapshot models | trade core ORM | formal Trade main-chain | Separate from portfolio and simulation Bases |
| `backend/services/trade/portfolio/models/__init__.py:Base` | portfolio models; schema registry | trade portfolio ORM | formal Trade main-chain | Separate metadata and naming conventions |
| `backend/services/trade/simulation/models/__init__.py:Base` | simulation models; schema registry | typed SQLAlchemy 2.0 simulation ORM | formal Trade main-chain | Separate metadata; uses `DeclarativeBase` while most others use legacy `declarative_base()` |
| `backend/services/stream/market_app/models/base.py:Base` | stream market models | stream ORM | formal Stream main-chain | Stream has its own engine and session lifecycle |
| `backend/services/engine/stock_query_app/local_models.py:Base` | stock query local services | direct synchronous PostgreSQL models | formal optional/compatibility | Module-level engine creation bypasses shared manager |
| `backend/services/engine/ai_strategy/storage/database.py:Base` | retained AI strategy storage functions | `ai_strategies` legacy table | explicitly deprecated | Its own engine/session and overlapping strategy authority |
| `backend/services/engine/ai_strategy/persistence.py:Base` | legacy AI strategy persistence | separate AI strategy persistence | compatibility/history | Parallel engine, tables, and commit rules |
| `backend/services/engine/ai_strategy/models/stock_pool_file.py:Base` | AI strategy stock-pool file model | isolated model metadata | unconnected/compatibility | Another independent Base |

`backend/shared/schema_registry.py` is a metadata discovery and runtime
`create_all` registry, not a unified Base. It registers seven schema keys across
API, Trade, Engine, and Stream and can detect duplicate table names.

### 3.3 Model conventions

- **Primary keys:** mixed. API models often use auto-increment integers plus
  domain string IDs; Engine `SystemTask.task_id` uses a string UUID identity;
  Trade uses PostgreSQL UUID columns for orders/trades; other tables use
  integer/bigint IDs.
- **Timestamps:** common but not uniform. Mixins exist in API, Trade, Stream,
  and Simulation; code mixes `datetime.now`, `datetime.utcnow`, server-side
  `func.now()`, timezone-aware and naive columns.
- **Soft deletion:** present in selected models such as
  `backend/services/api/user_app/models/user.py:User`, not a global convention.
- **Versioning:** selected records such as
  `backend/services/trade/models/order.py:Order.version` use a version field;
  there is no common optimistic-locking/version mixin.
- **Enums:** mixed Python `Enum` mapped through SQLAlchemy `Enum`, string
  columns, and status strings. There is no single repository policy.
- **JSON:** generic SQLAlchemy `JSON` is common in API/Trade models.
  PostgreSQL-specific `JSONB` is directly used in
  `backend/services/engine/models/market_data.py:MarketDataDaily.features`.
- **PostgreSQL schema:** existing ORM models generally do not set a non-public
  `schema` in `__table_args__`; SQL bootstrap objects are predominantly
  `public.*`.
- **Table naming:** mostly snake_case but prefixes are inconsistent (`qm_`,
  `qlib_`, `trade_`, `sim_`, `community_`, and unprefixed business tables).
- **Dynamic/runtime tables:** multiple services issue raw
  `CREATE TABLE IF NOT EXISTS`, and Trade startup invokes metadata
  `create_all`. Runtime DDL therefore exists outside ORM model declarations.

No existing Base is suitable merely because it is named `Base`; selection must
follow service ownership and session lifecycle.

## 4. Engine and Session Reality

### 4.1 Shared asynchronous main path

The strongest cross-service path is:

```text
environment / unified config
→ backend.shared.database_manager_v2.DatabaseConfig
→ DatabaseManager.initialize
→ sqlalchemy.ext.asyncio.create_async_engine (master and optional slaves)
→ async_sessionmaker(class_=AsyncSession, expire_on_commit=False)
→ get_session(read_only=False/True)
→ service/router code
→ outer master context commit or rollback
→ session close
```

**【代码确认】** `DatabaseConfig` prefers `DATABASE_URL`, then composes values
from `DB_MASTER_HOST`/`DB_HOST`, `DB_MASTER_PORT`/`DB_PORT`, `DB_NAME`,
`DB_USER`, and `DB_PASSWORD`. Pool size, overflow, timeout, recycle, pre-ping,
SQL echo, and pool echo are configurable. `DatabaseManager.initialize()`
creates one master AsyncEngine and zero or more slave AsyncEngines and runs a
`SELECT 1` health check.

`DatabaseManager.get_master_session()` owns an async context. It commits after
a successful yield, rolls back on an exception, and closes. Read-only sessions
use round-robin slaves when configured, fall back to master, and close.

### 4.2 Entrypoint call chains

#### API main-chain

```text
backend/main_oss.py
→ backend.services.api.main:app
→ lifespan
→ backend.shared.config_manager.init_unified_config
→ backend.shared.database_pool.init_default_databases (sync compatibility pool)
→ backend.shared.database_manager_v2.init_database (async shared manager)
→ service-specific ensure_tables calls
→ API dependencies/services use shared get_session
```

Examples include `backend/services/api/user_app/database.py:get_db`,
`backend/services/api/routers/community/deps.py`, and user/auth/profile services.
FastAPI generator dependencies provide request-scoped sessions in routes; many
services also open their own shared session context.

#### Engine main-chain

```text
backend/main_oss.py
→ backend.services.engine.main:app
→ lifespan
→ init_unified_config
→ database_pool.init_default_databases (sync pool)
→ model_registry_service.ensure_tables
→ _bootstrap_qlib_runtime
→ BacktestPersistence.ensure_tables / OptimizationPersistence.ensure_tables
```

Engine persistence services such as model inference, pipeline, strategy loop,
Qlib backtest, and Qlib optimization use the shared async `get_session` and raw
SQL. Engine also retains synchronous consumers of `database_pool.get_db` and
special-purpose sync engines.

#### Trade main-chain

```text
backend/main_oss.py
→ backend.services.trade.main:app
→ lifespan
→ database_manager_v2.init_database
→ schema_registry.create_registered_tables(master engine, trade schema keys)
→ manual_execution_persistence.ensure_tables
→ routers/services use backend.services.trade.deps.get_db
→ deps delegates to database_manager_v2.get_session
```

`backend/services/trade/database.py` defines another async engine and an
`init_db()` that calls `create_registered_tables`, but current Trade dependencies
use the shared async manager. It is a parallel compatibility path, not the
selected Ledger path.

#### Stream main-chain

`backend/services/stream/main.py` and
`backend/services/stream/market_app/database.py` use a stream-specific async
engine/session factory and explicit commit/rollback behavior. This subsystem is
not an API/Project Knowledge persistence authority.

#### Background/Celery path

`backend/services/engine/tasks/celery_tasks.py` uses both `asyncio.run()` around
shared async persistence services and a special synchronous engine/session for
dispatch logs. The sync helper issues runtime DDL and commits directly. Other
background workers open shared async sessions through `get_session` and often
commit explicitly.

### 4.3 Synchronous compatibility path

`backend/shared/database_pool.py` builds named synchronous SQLAlchemy engines
using psycopg2. Its `get_db()` closes but does not commit or roll back; callers
own transaction completion. API and Engine initialize this pool because
synchronous strategy/AI/Qlib code still consumes it. It is not a safe default
for a new async API-owned Ledger.

`backend/shared/database.py` also creates a module-level synchronous engine,
Base, and SessionLocal. Its `init_db()` deliberately skips `create_all` and
points to `data/quantmind_init.sql`. Engine ORM models import its Base, while
their runtime sessions may come from other mechanisms.

## 5. Transaction Reality

| Concern | Code-confirmed behavior | Ledger implication |
| --- | --- | --- |
| Outer shared write transaction | `DatabaseManager.get_master_session` commits after success, rolls back on exception | Suitable for one atomic repository unit if inner code never commits |
| Inner commits | Many API, Engine, training, Trade, and Stream services call `commit()` themselves inside a shared session context | Atomic boundaries are inconsistent; Ledger repository contract must not copy inner-commit behavior |
| Sync pool | `database_pool.get_db` only closes; individual callers commit/rollback | Caller-dependent and unsuitable as default Ledger contract |
| Explicit engine transaction | `schema_registry.create_registered_tables` and scripts use `engine.begin()` | Used primarily for DDL/scripts, not a general repository unit-of-work abstraction |
| Nested transaction | `backend/services/api/routers/community/audit.py` uses `session.begin_nested()` | Nested/savepoint use exists but is isolated, not a platform convention |
| Read/write split | `get_session(read_only=True)` can use a slave and fall back to master | Read-after-write may be stale if routed to a replica; consistency-sensitive Ledger reads need master/explicit policy |
| Request scope | API dependencies yield one shared session per dependency invocation | A request may still open multiple sessions if services create their own contexts |
| Cross-service sharing | API/Trade/Engine share the manager implementation and database configuration, not a Python Session object across processes | Atomicity cannot cross process/service boundaries without a higher-level protocol |

**【代码确认】** The shared async context can support atomic Ledger writes
within one session. **【阻断风险】** Existing widespread explicit commits mean a
future Ledger repository must make transaction ownership explicit; otherwise a
multi-record index update can partially commit before the outer context exits.

## 6. Migration Reality

### 6.1 Alembic

**【代码确认】** Alembic appears in dependency files, but the repository has no
`alembic.ini`, migration `env.py`, Alembic `versions/` tree, or deployment call
to `alembic upgrade`. There is therefore no code-confirmed operational Alembic
mechanism. Alembic must not be claimed as the current authoritative migration
path solely because the package is declared.

### 6.2 Bootstrap and hand-written SQL

`data/quantmind_init.sql` is the fresh-install bootstrap. The deployment call is:

```text
deploy/deploy.sh:step10_init_database
→ docker exec ... psql
→ stdin from data/quantmind_init.sql
```

The same script starts the PostgreSQL 15 container first. This is the only
repository-confirmed deployment invocation of a full schema file.

`data/upgrade_v1.1.0.sql` and
`data/migrations/upgrade_v1.4.0_stock_tag.sql` are hand-written, version-labelled
PostgreSQL scripts. They include `BEGIN`/`COMMIT` and documented manual `psql`
instructions. The repository does not contain an ordered migration runner,
applied-version table, checksum ledger, or downgrade scripts.

**【尚未确认】** Static evidence cannot prove whether operators execute these
upgrade files in any deployed environment, in which order, or with which
verification. The deploy script does not apply them.

### 6.3 Runtime DDL

Runtime DDL is active in several formal paths:

- `backend/shared/schema_registry.py:create_registered_tables` calls
  `metadata.create_all` and is invoked by Trade startup.
- API startup calls `ensure_admin_tables`, model registry `ensure_tables`, and
  model inference `ensure_tables`.
- Engine startup calls model registry, Qlib backtest, and Qlib optimization
  `ensure_tables`.
- Raw DDL also exists in pipeline, strategy-loop, manual-execution, calendar,
  community follow, notification index, and Celery dispatch-log persistence.
- `backend/services/api/user_app/services/profile_service.py` performs a runtime
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.

Runtime DDL is idempotent in places but has no global ordering, downgrade,
checksum, or consistent ownership. It is a compatibility mechanism, not a safe
new Ledger migration authority.

### 6.4 Migration conclusion

- **Current fresh-install authority:** `data/quantmind_init.sql` invoked by
  `deploy/deploy.sh`.
- **Current upgrade evidence:** manually invoked, transaction-wrapped SQL files;
  actual deployment use is **【尚未确认】**.
- **Parallel mechanism:** service startup/runtime DDL and metadata `create_all`.
- **Downgrade support:** not found.
- **Transaction support:** explicit for the two inspected upgrade scripts;
  bootstrap and individual runtime DDL do not form one repository-wide migration
  transaction contract.
- **Forbidden for new Ledger:** runtime `CREATE TABLE`, startup `create_all`, a
  new isolated migration framework, or an unversioned SQL fragment.

## 7. Test Database Reality

- `backend/services/tests/conftest.py` defines markers including `database` but
  does not provide a PostgreSQL engine/session or rollback fixture.
- AI strategy tests mainly mock external calls and `sqlalchemy.create_engine`.
- Selected tests use synchronous `sqlite:///:memory:` or asynchronous
  `sqlite+aiosqlite:///:memory:` and call `create_all`/ad hoc DDL.
- Many service tests replace `get_session`/`get_db` with async context fakes or
  mock Session objects.
- No shared in-memory Repository implementation was found.
- No general transaction rollback fixture was found.
- No repository CI configuration proving a PostgreSQL service was found.
- Some tests can run without a database under pytest; standard-library
  `unittest` can cover pure domain rules, canonicalization, manifest parsing,
  and fake-repository contracts.
- SQLite tests do not prove PostgreSQL JSONB, schema qualification, concurrent
  uniqueness, replica behavior, or PostgreSQL transaction semantics.

**【阻断风险】** A generic `DATABASE_URL` may point to a real environment, and
some modules create engines at import time. Future integration tests must fail
closed unless an explicitly isolated test PostgreSQL URL/schema is supplied.
This task did not import those modules or inspect secret-bearing local `.env`
contents.

Recommended future test layering (not implemented here):

1. A1b domain and repository-contract tests: pure `unittest`/pytest with fakes,
   no SQLAlchemy engine.
2. A2 ORM/migration tests: static metadata/SQL checks plus an explicitly
   isolated PostgreSQL integration target; never production-like defaults.
3. A3 indexer/consistency tests: temporary Git repository and fake repository,
   then isolated PostgreSQL integration for uniqueness/transactions.
4. API tests: dependency override/fake repository first; isolated PostgreSQL
   only for integration tests.

## 8. Configuration and Secret Handling

### 8.1 Sources and precedence

The shared async manager prefers `DATABASE_URL`, then split `DB_*` variables.
The sync pool follows the same general pattern. Unified YAML configuration and
legacy settings add other fallbacks. Docker Compose injects both split values
and complete URLs. Services do not uniformly consume one configuration object.

Pool controls are implemented in `DatabaseConfig`: `DB_POOL_SIZE`,
`DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE`, `DB_POOL_PRE_PING`,
`DB_ECHO`, and `DB_ECHO_POOL`. No consistent PostgreSQL SSL configuration was
found in the shared manager path.

### 8.2 Secret risks

No secret value is reproduced in this audit.

| Path | Keys/behavior | Risk |
| --- | --- | --- |
| `docker-compose.yml` | `DB_PASSWORD`, embedded `DATABASE_URL`, source DB URL defaults | Credential-bearing defaults are repository-visible |
| `config/settings.py` | DB host/user/password defaults and composed URL | Hard-coded credential-bearing fallback |
| `backend/config/settings.py` | default `DATABASE_URL` | Hard-coded credential-bearing fallback |
| `config/database/all_databases.yaml` | default PostgreSQL URL | Credential-bearing default in configuration |
| `backend/shared/database.py` | credential-bearing fallback URL | Import can create an engine using fallback configuration |
| `backend/services/engine/tasks/celery_tasks.py` | credential-bearing sync fallback | Background task can silently target fallback database |
| `backend/shared/database_manager_v2.py:DatabaseConfig.__init__` | logs only the portion after `@` when announcing configured URL | This specific line masks user/password by omission |
| `backend/shared/database_manager_v2.py:DatabaseManager.initialize` | logs `master_url` directly | May disclose the complete credential-bearing URL |
| local `.env` files | environment-specific values | Contents were deliberately not read or emitted |

**【工程选择】** Ledger must consume the existing environment-derived shared
manager without storing or logging a URL, username, password, or token in its
domain objects, Run manifests, repository logs, or API responses. Connection
logging must use driver/host/port/database-only safe metadata; changing that
logging is outside this audit task.

## 9. Competing Persistence Mechanisms

| Option | Compatibility | Transactions/query/concurrency | Migration/rollback | Testing/maintenance | Recommendation |
| --- | --- | --- | --- | --- | --- |
| A. Shared API/Engine SQLAlchemy + established SQL path | Highest; matches PostgreSQL and API async code | Async transactions, indexed queries, PostgreSQL concurrency | Existing versioned SQL is manual; no downgrade | Reuses dependencies but needs isolated PG integration | **Yes**, with the exact choices in section 11 |
| B. Runtime `CREATE TABLE` | Common in legacy runtime code | Can transact, but startup races and partial schema drift are possible | No ordered history or downgrade | Easy initially, costly to audit | No |
| C. Independent SQLite Ledger | Low for deployed multi-process services | Different JSON/schema/locking/concurrency semantics | Would create a second mechanism | Easy unit setup, poor production fidelity | No |
| D. JSON files as sole Ledger | Existing immutable Git Runs remain authoritative artifacts | No robust concurrent query transaction or uniqueness | Git can roll back files but JSON index replacement/races remain | Useful source artifacts, inadequate query index | No as sole index; Git manifests remain authority |
| E. Existing PostgreSQL DB with `quantmind2` schema | Compatible with A and isolates names | PostgreSQL transactions and indexed queries | Requires explicit schema-qualified versioned SQL and verified privileges | Clear ownership; PG integration needed | **Yes**, as the physical placement for A |

Option A and E are complementary: A chooses the access mechanism; E chooses
the namespace. PostgreSQL remains a derived/queryable index. Git, accepted ADRs,
and immutable Implementation Runs retain their authority under ADR-0005 and
ADR-0007.

## 10. Formal vs Legacy Classification

| Mechanism | Path | Symbol | Caller | Status | Data owned | Risk |
| --- | --- | --- | --- | --- | --- | --- |
| Shared async PostgreSQL | `backend/shared/database_manager_v2.py` | `DatabaseManager`, `get_session` | API services, Trade deps, Engine persistence, workers | formal main-chain required | cross-service business/task records | auto outer commit plus inner commits; URL log risk |
| Shared sync pool | `backend/shared/database_pool.py` | `DatabasePool`, `get_db` | API/Engine startup and sync strategy/Qlib paths | formal main-chain optional/compatibility | strategies and sync consumers | caller-owned transaction |
| Shared sync Base/engine | `backend/shared/database.py` | `Base`, `SessionLocal` | Engine ORM family | compatibility/formal model metadata | market/tag/task tables | model Base coupled to different engine lifecycle |
| API Base | `backend/services/api/models/base.py` | `Base` | user/community models, schema registry | formal API main-chain | API/user/community tables | no namespace policy |
| Trade schema registry | `backend/shared/schema_registry.py` | `create_registered_tables` | Trade lifespan | formal Trade startup | trade tables | runtime DDL, no version history |
| Stream DB | `backend/services/stream/market_app/database.py` | `engine`, `AsyncSessionLocal` | Stream service | formal Stream main-chain | market stream data | separate configuration/lifecycle |
| Qlib persistence DDL | `backend/services/engine/qlib_app/services/*_persistence.py` | `ensure_tables` | Engine lifespan | formal Engine main-chain | Qlib run indexes | runtime migration fragments |
| Celery sync DB | `backend/services/engine/tasks/celery_tasks.py` | `_get_sync_db_session`, `_ensure_dispatch_log_table` | Celery tasks | background-task use | inference dispatch log | embedded fallback, runtime DDL |
| AI strategy legacy storage | `backend/services/engine/ai_strategy/storage/database.py` | `SessionLocal`, `StrategyRecord` | retained compatibility calls | deprecated | legacy AI strategies | overlapping authority |
| Stock-query local models | `backend/services/engine/stock_query_app/local_models.py` | `engine`, `SessionLocal` | stock-query subsystem | formal optional/compatibility | stock/query tables | module-level independent engine |
| SQLite memory engines | selected `backend/services/tests/test_*.py` | test-local engines | tests only | test use | ephemeral fixtures | does not prove PostgreSQL behavior |
| Bootstrap SQL | `data/quantmind_init.sql` | schema dump/bootstrap | `deploy/deploy.sh:step10_init_database` | formal fresh-install | public schema | large snapshot, no incremental ordering |
| Versioned SQL upgrades | `data/upgrade_v1.1.0.sql`, `data/migrations/upgrade_v1.4.0_stock_tag.sql` | manual scripts | documented `psql`; deployment caller not found | compatibility/current upgrade evidence; **【尚未确认】** operational | selected tables | manual order, no applied-version ledger/downgrade |
| Alembic | dependency declarations only | none operational | none found | unconnected | none confirmed | must not be assumed operational |

## 11. Recommended Ledger Persistence Mechanism

This is a choice for later implementation, not an implementation claim.

| Decision | Recommendation | Evidence status |
| --- | --- | --- |
| ORM | SQLAlchemy 2.0, asynchronous repository adapter | **【工程选择】** based on production pin and shared API path |
| Base | `backend.services.api.models.base.Base` for future API-owned Ledger ORM metadata | **【工程选择】**; Base exists, no Ledger model exists |
| Engine | master AsyncEngine owned by `backend.shared.database_manager_v2.DatabaseManager` | **【代码确认】** existing cross-service engine; **【工程选择】** for Ledger |
| Session | `backend.shared.database_manager_v2.get_session(read_only=False)`; outer application/unit-of-work owns commit/rollback, repository methods never commit | existing behavior **【代码确认】**; ownership rule **【工程选择】** |
| Reads | master session for consistency-sensitive ingestion/reconciliation; replica reads only after explicit staleness policy | **【工程选择】** |
| Migration | versioned, transaction-wrapped PostgreSQL SQL under the existing `data/migrations` family; fresh-install schema must remain reconcilable with `data/quantmind_init.sql`; never startup DDL | **【工程选择】** using current repository mechanism |
| Database/schema | current configured PostgreSQL database, explicit `quantmind2` schema | **【工程选择】**; privileges/search path **【尚未确认】** |
| Repository service | future API control-plane package under `backend/services/api/project_knowledge/` | **【工程选择】**; package does not exist |
| Future API dependency | thin API dependency delegating to shared `database_manager_v2.get_session`; do not use Trade/Stream/local engines | **【工程选择】** |
| Test layers | pure domain/fake repository; static ORM/migration checks; isolated PostgreSQL repository integration; API dependency overrides | **【工程选择】** |

Why this path:

1. It matches the current async PostgreSQL route used by API and cross-service
   persistence without introducing a new dependency or database product.
2. PostgreSQL supports the atomic multi-row index updates, uniqueness,
   concurrency, and query patterns that a derived Ledger index needs.
3. A separate `quantmind2` schema makes ownership explicit without creating a
   separate secret/config/backup domain.
4. Repository code can remain transaction-neutral and allow the control layer
   to bind Run, artifacts, references, and index state in one transaction.
5. Git manifests remain immutable authority; PostgreSQL rows are rebuildable
   indexes and cannot overwrite Git truth.

Why the alternatives are not selected:

- The sync pool has ambiguous caller-owned transaction behavior and blocks an
  async API path.
- Trade, Stream, stock-query, and AI-strategy engines are subsystem-local or
  legacy and would give the Ledger the wrong owner.
- Runtime DDL has no migration history or downgrade.
- SQLite diverges from deployment semantics and adds a second fact store.
- JSON/Git artifacts are authoritative history but cannot alone provide safe
  concurrent query indexing.
- Alembic is a declared dependency, not an operational repository mechanism.

**【阻断风险】** Before A2 creates a migration, the project must verify how an
incremental SQL migration is invoked in deployment, how applied versions are
recorded, whether the configured role can create/use `quantmind2`, and how a
failed or partially applied migration is recovered. A1b may define domain and
repository contracts without resolving these deployment facts, but must not
claim a table exists.

## 12. Rejected Alternatives

Rejected as the Ledger standard: runtime `ensure_tables`, Trade
`metadata.create_all`, Stream-local database, stock-query module engine,
deprecated AI strategy storage, Celery's ad hoc sync engine, standalone SQLite,
JSON-only indexing, and assumed Alembic. These mechanisms remain factual parts
of the current repository; rejection here does not remove or refactor them.

## 13. Risks

1. Multiple Bases and engines permit model/session mismatches.
2. Outer auto-commit plus inner explicit commits obscures atomic boundaries.
3. Runtime DDL can race across processes and drift from bootstrap SQL.
4. No code-confirmed ordered migration runner, applied-version ledger, or
   downgrade path exists.
5. Upgrade-script use in real deployment is unconfirmed.
6. No shared isolated PostgreSQL test fixture or CI PostgreSQL service is
   confirmed.
7. SQLite tests can hide PostgreSQL-specific failures.
8. Some configuration files contain credential-bearing defaults.
9. Shared async engine initialization may log a complete database URL.
10. Replica reads may violate read-after-write expectations.
11. Explicit `quantmind2` schema privileges and backup/restore behavior are
    unconfirmed.

## 14. Unresolved Facts

- **【尚未确认】** Which operational process applies incremental SQL upgrades.
- **【尚未确认】** Whether deployed databases match `quantmind_init.sql` plus all
  documented upgrades.
- **【尚未确认】** Whether CI provides isolated PostgreSQL.
- **【尚未确认】** Whether the deployment role can create/use `quantmind2` and
  set schema-qualified foreign keys safely.
- **【尚未确认】** Required retention, rebuild SLA, and backup policy for the
  derived Ledger index.
- **【尚未确认】** Whether a formal migration-version table should be introduced;
  that could require a later architecture/operations decision and is not made
  here.
- **【尚未确认】** SSL requirements for each deployed PostgreSQL environment.

## 15. Evidence Index

| Concern | Path | Symbols/callers |
| --- | --- | --- |
| Async engine/session | `backend/shared/database_manager_v2.py` | `DatabaseConfig`, `DatabaseManager.initialize`, `get_master_session`, `get_session`, `init_database` |
| Sync pool | `backend/shared/database_pool.py` | `DatabasePool.register_database`, `get_db`, `init_default_databases` |
| Engine Base | `backend/shared/database.py` | `Base`, `SessionLocal`, `init_db` |
| API Base/dependency | `backend/services/api/models/base.py`; `backend/services/api/user_app/database.py` | `Base`, `get_db`, `get_readonly_db` |
| API startup | `backend/services/api/main.py` | `lifespan` |
| Engine startup | `backend/services/engine/main.py` | `lifespan`, `_bootstrap_qlib_runtime` |
| Trade startup/dependency | `backend/services/trade/main.py`; `backend/services/trade/deps.py` | `lifespan`, `get_db`, `get_read_db` |
| Schema registry | `backend/shared/schema_registry.py` | `SCHEMA_SPECS`, `create_registered_tables` |
| Stream database | `backend/services/stream/market_app/database.py` | `_create_engine`, `AsyncSessionLocal`, `get_db`, `init_db` |
| Background DB | `backend/services/engine/tasks/celery_tasks.py` | `_get_sync_db_session`, `_ensure_dispatch_log_table`, `_run_async` |
| Runtime DDL | `backend/shared/model_registry.py`; `backend/services/engine/services/model_inference_persistence.py`; `backend/services/engine/qlib_app/services/backtest_persistence.py`; `backend/services/engine/qlib_app/services/optimization_persistence.py` | `ensure_tables` methods and startup callers |
| Bootstrap deployment | `deploy/deploy.sh`; `data/quantmind_init.sql` | `step10_init_database` and `psql` invocation |
| Upgrade SQL | `data/upgrade_v1.1.0.sql`; `data/migrations/upgrade_v1.4.0_stock_tag.sql` | transaction-wrapped manual scripts |
| Test fixtures | `backend/services/tests/conftest.py`; `backend/services/engine/ai_strategy/tests/conftest.py` | markers and mocks |
| SQLite tests | `backend/services/tests/test_stock_tag_model.py`; `backend/services/tests/test_simulation_price_valuation_regression.py`; `backend/services/tests/test_simulation_corporate_action_redis_refresh.py` | test-local engines/sessionmakers |
| Dependency versions | `requirements/production.txt`; `requirements/database.txt`; `requirements/dev.txt` | SQLAlchemy/driver/Alembic/pytest declarations |
| Configuration | `docker-compose.yml`; `config/settings.py`; `backend/config/settings.py`; `config/database/all_databases.yaml` | DB keys and defaults (values intentionally omitted) |

## 16. Handoff to QM2-P0-002A1b

`QM2-P0-002A1b — Ledger Domain Objects and Repository Contract` should consume
this audit as a fact boundary. It may define domain identities, repository
operations, transaction expectations, error semantics, and fake-repository
tests. It must continue to treat Git manifests as authority and PostgreSQL as a
derived index. It must not create ORM models, tables, migrations, an indexer,
consistency service, API, or UI unless its own scope explicitly authorizes
those items.

This audit did not start A1b and introduced no persistence implementation.
