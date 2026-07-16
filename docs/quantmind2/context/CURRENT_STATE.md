# Current Implementation State

Generated: 2026-07-16
Verified source commit before this task: `0114f35332073cab00928f753af83c9ba8d83b6a`

## Implemented in existing systems

- QuantMind LightGBM training and model artifacts.
- QuantMind inference through `ModelLoader`, `DataAdapter`, and
  `InferenceService`.
- `QlibBacktestService`, Strategy builders, Executor, Exchange, and
  `RiskAnalyzer`.
- Official V7 Factor Lab Agent generation, Candidate contracts, Docker-only
  generated-code execution, validation metrics, bounded campaigns, and
  Research Memory.

## Partial

- Feature Snapshot: annual Parquet training snapshots exist, but lack immutable
  Factor Registry and Dataset Snapshot lineage.
- FactorSpec: useful metadata exists, but definition, implementation, and data
  references are not fully separated.
- Experiment artifacts: local artifacts and JSON records exist without the
  target immutable cross-domain Experiment Manager.
- Research Memory: Factor Lab has JSON/JSONL memory but no Frozen Test access
  isolation contract for QuantMind 2.0.
- Factor Lab to Qlib: an actual call seam exists, but it is not the target
  Registry-to-Unified-Signal integration.

## Not implemented

- Research Skill runtime
- executable ResearchDecision model and Decision Validator
- QuantMind 2.0 Bounded Code Orchestrator
- Factor DSL / Canonical AST
- Factor Optimization
- immutable Factor Registry
- Frozen Test access isolation
- Registry → Feature Snapshot → LightGBM lineage
- Unified Signal Service
- Project Knowledge API
- Project Knowledge Web UI
- Project Knowledge API and Web UI

## Completed context bootstrap

- `QM2-P0-001 — Context Bootstrap and Implementation Contract` is complete
  and committed as `5504bdb94ddf817976f74a09e323cf8fb1eacf4a`.
- Its immutable historical run remains
  `QM2-P0-001-20260713T183614Z-e9b0c7d` with status
  `completed_uncommitted`, because that was the true workspace state when the
  run was produced.
- `QM2-P0-001F — Finalize and Commit Context Bootstrap` revalidated and
  committed the original scope without changing the original run.
- Latest Implementation Run:
  `QM2-P0-001F-20260714T140245Z-5504bdb`.
- The current latest commit is the commit containing this derived state. Its
  immutable ID is resolved with
  `git log -1 --format=%H -- docs/quantmind2/context/CURRENT_STATE.md`; embedding
  that commit's own hash in its content is not possible.
- The workspace is expected to be clean after the finalization commit; the
  final task response records the verified post-commit status.

No business-domain implementation was introduced by either task.

## Accepted decision-control-execution architecture

- `ADR-0009 — Decision–Control–Execution Separation` is accepted.
- `RESEARCH_DECISION_CONTRACT_V1.md` and its JSON Schema/example define the
  Decision Layer proposal boundary.
- These are architecture contracts only. Research Skill, executable Decision
  Validator, permission/state/budget/idempotency controls, and Code
  Orchestrator v2 remain planned and unimplemented.
- Official V7 Factor Lab remains partial donor evidence: it has bounded loops,
  checkpoints, budget checks, Docker gateway, validation, and memory, but its
  Candidate is Python-first and its drivers do not use a formal
  ResearchDecision/Decision Validator boundary.
- Latest Implementation Run:
  `QM2-P0-001G-20260714T142514Z-05c2db2`.
- The commit containing this state is resolved with
  `git log -1 --format=%H -- docs/quantmind2/context/CURRENT_STATE.md` because a
  commit cannot embed its own hash.

## Persistence reality audit

- `QM2-P0-002A1a — Persistence Mechanism Reality Audit` completed a static,
  code-backed audit at base commit `8188a1e78f0ff74f7beb49d3522c417ed76194fa`.
- The audit records that SQLAlchemy/PostgreSQL persistence is fragmented across
  a shared async manager, sync compatibility pools, service-local engines,
  runtime DDL, bootstrap SQL, and manually documented upgrade SQL.
- The recommended future Ledger route is the shared async PostgreSQL manager,
  API-owned SQLAlchemy metadata, transaction-neutral repository methods, and a
  versioned SQL migration in an explicit `quantmind2` schema. This is an
  engineering selection only, not an implemented persistence layer.
- At the A1a audit point, Ledger domain and Repository code did not exist;
  later A1b tasks now supersede that implementation-state observation while
  preserving the audit's persistence findings.
- Latest Implementation Run:
  `QM2-P0-002A1a-20260714T145325Z-8188a1e`.

## Implementation Ledger domain model

- `QM2-P0-002A1b1 — Implementation Ledger Domain Model and Invariants`
  implements standard-library, frozen domain objects, stable enums, structured
  errors, value validators, Run state invariants, and direct relationship
  conflict checks.
- The domain package is independent of SQLAlchemy, FastAPI, environment,
  filesystem, network, Git commands, and databases.
- At the A1b1 point, Repository behavior was deferred; A1b2 now supplies its
  Protocol and test-double contract without changing the frozen domain model.
- Latest Implementation Run:
  `QM2-P0-002A1b1-20260714T152420Z-6ec76c0`.

## Implementation Ledger Repository contract

- `QM2-P0-002A1b2 — Ledger Repository Contract and In-memory Test Double`
  implements synchronous `typing.Protocol` contracts, immutable query/page
  values, stable Repository errors, full in-memory relationship cycle checks,
  expected-version checks, append-only details, stable queries, and an atomic
  batch test contract.
- `InMemoryLedgerRepository` is a process-local test double only. It is not a
  production Ledger or persistence authority.
- SQLAlchemy Repository, database transactions, Manifest Parser/Indexer, Git
  consistency service, API, and UI remain unimplemented. A2a1 now supplies
  static core ORM mappings only.
- Latest Implementation Run:
  `QM2-P0-002A1b2-20260714T155151Z-200665b`.

## Implementation Ledger core ORM mapping

- `QM2-P0-002A2a1 — Core Implementation Ledger ORM Mapping` maps only
  ImplementationTask, ImplementationRun, and RunRelationship on the selected
  API Declarative Base.
- The mappings explicitly target `quantmind2`, use JSONB/timestamptz,
  VARCHAR plus named enum checks, named PK/FK/UQ/check/index objects, positive
  version columns, and `ON DELETE RESTRICT`.
- PostgreSQL DDL was compiled statically from SQLAlchemy metadata without an
  Engine, Connection, Session, credentials, or DDL execution.
- This is a mapping contract only. Reference/annotation ORM tables, domain
  mappers, migration, real schema/table creation, PostgreSQL verification, production
  Repository, Session/UoW, and transaction code remain unimplemented.
- QM2-P0-002A2a2a adds static API-Base mappings for ChangedFile,
  ChangedSymbol, TestExecution, and ImplementationArtifact. Their named PK,
  Run FK, natural unique, checks, and indexes compile as PostgreSQL DDL.
- The four detail mappings are metadata only: no Mapper, migration, schema,
  table, database connection, Repository, Session/UoW, Indexer, API, or UI was
  created.
- Latest Implementation Run:
  `QM2-P0-002A2a2a-20260714T164637Z-53efb74`.

## Implementation Ledger ORM mapping

- `QM2-P0-002A2a2b1 — Ledger Component and ADR Reference ORM Mapping`
  maps ComponentReference and ArchitectureDecisionReference on the shared API
  Base using their A1b2 natural identities as composite primary keys.
- Both tables have only a restrictive Run FK. Component Catalog and ADR Index
  remain Git-derived facts and are not database foreign-key targets.
- `QM2-P0-002A2a2b2 — Ledger Limitation and Recommended Task ORM Mapping`
  maps the two remaining annotation objects. Both use globally unique domain
  IDs as primary keys, restrictive Run FKs, enum-derived checks, and explicit
  indexes; the A1b2 Run/object identities are also recorded as named unique
  constraints.
- All eleven currently targeted Ledger objects now have static ORM mappings.
  This is metadata only: Domain mappers, migration, `quantmind2` schema/table
  creation, PostgreSQL Repository, database access, Indexer, API, and UI remain
  unimplemented. No annotation row has been written.
- Latest Implementation Run:
  `QM2-P0-002A2a2b2-20260714T175052Z-646c4db`.

## Ledger Domain / ORM Mapper contract

- `QM2-P0-002A2a2c1 — Ledger Mapper Identity and Conversion Contract` fixes
  Mapper contract version 1.0.0, pure conversion boundaries, all eleven object
  round trips, enum/time/JSON/null/error rules, and deterministic ChangedFile
  and ChangedSymbol identity vectors.
- Frozen Domain/ORM `ImplementationRun.repository_root` is interpreted as a
  logical repository identity. Manifest v1's absolute path is execution context
  and requires an explicit future Indexer binding; it is not directly copied.
- This is a documentation and verification contract only. No Mapper Python,
  Core/Detail/Reference/Annotation mapper, migration, schema/table, database
  connection, Repository, Session/UoW, Indexer, API, or UI exists.
- Latest Implementation Run:
  `QM2-P0-002A2a2c1-20260714T181338Z-1d5affb`.

## Complete Ledger Mapper layer

- `QM2-P0-002A2a2c2a — Mapper Foundation and ImplementationTask Mapper`
  implements safe transport-neutral Mapper errors, contract version 1.0.0,
  reusable exact Enum/aware-UTC datetime/tuple-JSON conversions, and pure
  bidirectional ImplementationTask conversion.
- New Domain Tasks produce new ORM records with `version=1`; stored positive
  versions are validated but excluded from Domain. Existing-record updates,
  replay, conflict, optimistic concurrency, and transactions remain Repository
  responsibilities.
- `QM2-P0-002A2a2c2b — ImplementationRun Domain-to-ORM Mapper` adds pure
  bidirectional Run conversion, exact five-Enum conversion, aware UTC times,
  nullable commit/hash fields, logical repository identity preservation, and
  ORM-only version handling. Domain construction remains state authority.
- `QM2-P0-002A2a2c2c — Complete Remaining Ledger Domain-to-ORM Mappers`
  completes explicit bidirectional mapping for all eleven Ledger Domain
  objects. It adds RunRelationship, four Detail, two Reference, and two
  Annotation mapper families while preserving the Task and Run contracts.
- ChangedFile and ChangedSymbol technical IDs now use the frozen NFC/UTF-8/LF
  SHA-256 algorithms. Reverse mapping recomputes and rejects mismatched stored
  IDs. Parent Run context is explicit and must match each Domain object.
- Full Domain and ORM business-field round trips, all nine identity vectors,
  Enum and invalid-record cases, field/inventory drift, safe-error behavior,
  and no-side-effect guards are verified.
- Manifest Parser/Indexer, repository identity binding, PostgreSQL Repository,
  and business Session/UoW remain unimplemented.
- Latest Implementation Run:
  `QM2-P0-002A2a2c2c-20260715T050423Z-30edead`.

## Ledger migration and isolated PostgreSQL verification

- `QM2-P0-002A2b` adds explicit migration `0001`, exact-byte SHA-256
  checksums, `_schema_migrations`, ordered plan/status/validate/up/down, one
  transaction per migration, a stable advisory transaction lock, and guarded
  rollback.
- Fresh install now calls the same migration runner after base bootstrap;
  Ledger DDL is not duplicated in `quantmind_init.sql`.
- A disposable PostgreSQL 15 container verified the eleven business tables,
  87 columns, 97 named constraints, 49 explicit indexes, exact ORM/catalog
  parity, valid data, 18 invalid writes, `RESTRICT`, idempotent up, checksum
  drift rejection, rollback atomicity, down, reapply, and cleanup.
- This evidence is isolated verification only. No production database was
  migrated. PostgreSQL Repository, business Session/UoW, Manifest
  Parser/Indexer, Git consistency service, API, and UI remain unimplemented.
- Latest Implementation Run:
  `QM2-P0-002A2b-20260715T060812Z-7c83e36`.

## PostgreSQL Ledger Repository and Unit of Work

- `QM2-P0-002A3` implements the complete asynchronous PostgreSQL Repository
  mirror of the frozen A1b2 contract and an explicit async Unit of Work over
  the shared DatabaseManager engine/sessionmaker.
- Task, Run, Relationship, all eight child families, typed lists/history,
  exact replay, immutable conflict, savepoint recovery, expected versions,
  state changes, finalization, and atomic batch behavior are implemented.
- Relationship admission uses one stable PostgreSQL transaction advisory lock
  and a recursive CTE. Independent Sessions verified same/different Task races,
  stale updates, opposing-edge cycle admission, and batch conflict rollback in
  disposable PostgreSQL 15.
- The implementation is persistence access only. No Manifest Parser/Indexer,
  Git consistency service, repository identity resolver, API, UI, production
  migration, or research business feature was added.
- Latest Implementation Run: the `QM2-P0-002A3` Run paired with this task.

## Git-authoritative Ledger indexing

- `QM2-P0-002B — Manifest Parser, Git Consistency and Ledger Indexer`
  implements strict Manifest v1 parsing, explicit logical Repository binding,
  committed Git-object discovery, hash/commit/immutability checks, Domain
  Bundle admission, deterministic multi-pass indexing, JSON CLI commands, and
  isolated tests.
- Historical compatibility at base `d33f2815`: 16 v1 Runs discovered, 15 pass
  mandatory Git evidence, and zero form a complete Domain Bundle. The 001F Run
  declares a result commit different from its containing commit. Every v1 Run
  lacks independent Task status/creation time; populated children also lack
  Ledger identities or required semantics.
- No missing value was inferred. No historical Run was written as a backfill.
  A complete synthetic bundle verified insert, replay, immutable conflict, and
  rollback through disposable PostgreSQL 15. Production deployment/backfill
  has not occurred.
- ADR-0010 fixes logical repository identity and explicit runtime path binding.
- Ledger infrastructure implementation is closed. API/UI, watcher, webhook,
  daemon, and production deployment remain outside this phase.
- Latest Implementation Run:
  `QM2-P0-002B-20260715T090630Z-d33f281`.

## Forward-indexable Manifest v2

- `QM2-P0-002B1 — Manifest v2 Producer and Forward Indexability` implements
  strict Manifest v2 Schema, example, protocol documentation, and the formal
  `new` / `finalize-payload` / `validate` producer used by future Runs.
- Manifest v2 separates logical Repository identity from execution path and
  records Mapper/technical identity versions, stable child identities, typed
  artifact locations, complete Task/Run facts, and canonical integrity.
- Parser, Git consistency, Domain Bundle, Bootstrap, and Indexer accept v2
  without changing the v1 route. A valid v2 Run constructs all eleven frozen
  Ledger Domain families without Report prose or evidence gaps.
- The B1 Run itself uses Manifest v2 and passed committed-Git planning plus
  isolated PostgreSQL indexing, exact replay, immutable-conflict, and
  no-partial-write verification. Production database deployment did not occur.
- All 17 historical v1 Runs remain immutable. At the B1 base, 16 pass mandatory
  Git evidence and zero are fully indexable; QM2-P0-001F retains its declared
  result-commit mismatch.
- Ledger infrastructure is now formally closed. Project Knowledge API/UI,
  production deployment/backfill, watcher, webhook, and daemon remain absent
  and are not the next implementation scope.
- Latest Implementation Run:
  `QM2-P0-002B1-20260716T135059Z-0353435`.

## Next task

## Market data entry and Dataset Snapshot v1

- `QM2-P0-003 — TongDaXin Provider Reality Audit and Dataset Snapshot Entry`
  completed the repository/data-flow audit and implemented the Provider,
  Raw Capture, deterministic normalization, quality gate, immutable Parquet
  Snapshot, reader, validator and CLI boundaries.
- Current production reality is multi-source: official/remote PostgreSQL,
  local/CSMAR Parquet, feature snapshots and Qlib binary are not bound to one
  authoritative version. Training reads yearly feature Parquet; Qlib backtest
  reads a separate binary provider view.
- The evidenced TongDaXin path is the proprietary `tqcenter.tq` wrapper used by
  standalone legacy scripts, not pytdx/mootdx. The module, local client/data
  directory and canonical unit evidence are unavailable in this environment.
- No real TongDaXin Snapshot was generated. Deterministic Fake Provider tests
  validate the full storage contract and are explicitly marked `provider_id=fake`.
- Calendar, PIT Universe, listing/delisting, corporate actions, ST, limits,
  suspension, industry, finance and index-membership authorities remain open.
- Existing LightGBM training and Qlib backtest have not switched to Dataset
  Snapshot.
- Latest Implementation Run:
  `QM2-P0-003-20260716T142422Z-0114f35` (partial: real TDX environment absent).

## Legacy production feature route

- `QM2-P0-003L — Legacy Feature Parquet Provider and Real Dataset Snapshot`
  binds the actual annual Parquet consumed by existing LightGBM training through
  an explicit read-only Provider and the shared immutable Snapshot authority.
- The latest complete source is 2025: 1,248,108 rows, 5,212 symbols, 243 dates,
  155 columns and exact source SHA-256
  `7fd0316e6f8d936688ef332357fb7589f64c0e127c5f64e3158c584baf28b00f`.
- The real bounded Snapshot is
  `ds_bc82e7bb2c63d2c47677b11cf0f4fc1e5aa11a0ed18ee0bb27e3c8ab667d2ee7`:
  5,931 rows, 100 deterministic symbols, 60 dates, all 152 allowed features,
  zero labels, zero quality errors. Labels remain inaccessible by default.
- Existing production-loader/Provider/Snapshot parity passed. The only allowed
  production conversion is the existing numeric source dtype to `float32` cast.
- Real TDX remains unavailable, but it no longer blocks the Factor DSL route.
  A future TDX Provider adds Daily Bars Snapshots under the same authority model.
- Existing LightGBM training and Qlib backtest have not switched consumers.
- Latest Implementation Run:
  `QM2-P0-003L-20260716T151140Z-7d29df7`.

## Manifest v2 forward-indexability repair

- `QM2-P0-003LF — Manifest Self-reference Fix and 003L Forward-indexability`
  makes the current Run Manifest a protocol carrier rather than a ChangedFile.
- New Manifest v2 production rejects self-reference with
  `MANIFEST_SELF_REFERENCE`; Report remains a valid ChangedFile and Artifact.
- Committed v2 self-reference uses a general, path-based compatibility rule.
  003L now validates and builds a complete Domain Bundle with one structured
  `LEGACY_V2_MANIFEST_SELF_REFERENCE_IGNORED` warning and zero evidence gaps.
- The real 003L Dataset Snapshot, hashes, values, quality and loader-parity
  evidence are unchanged.
- Latest Implementation Run:
  `QM2-P0-003LF-20260716T153535Z-22461e0`.

## Manifest PostgreSQL assertion closure

- `QM2-P0-003LF1 — Fix Manifest Self-reference PostgreSQL Test Assertion`
  corrects the test-only use of nonexistent `AnalyzedRun.git_consistency` to
  the public `AnalyzedRun.evidence` contract.
- The production Planner, Git evidence, Manifest, Indexer, Repository,
  migration, Dataset Snapshot and Legacy Provider behavior are unchanged.
- The opt-in disposable PostgreSQL suite now passes all four tests, including
  real 003L and 003LF planning, first index, exact replay and absence of a
  self-Manifest ChangedFile.
- Latest Implementation Run:
  `QM2-P0-003LF1-20260716T160222Z-da271ac`.

## Next task

`QM2-P0-004 — Factor DSL v1 on Real Legacy Feature Dataset Snapshot` is the
only recommended next task. The Ledger stage remains closed.
