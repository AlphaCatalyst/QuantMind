# Component Catalog

The machine-readable catalog is authoritative for the initial component list.
Statuses describe current implementation, not architectural intention.

| Component | Status | Evidence |
|---|---|---|
| `quantmind.training` | implemented | Existing LocalDockerOrchestrator and training script |
| `quantmind.inference` | implemented | Existing ModelLoader, DataAdapter, InferenceService |
| `quantmind.qlib_backtest` | implemented | Existing QlibBacktestService and Qlib runtime |
| `quantmind.risk` | implemented | Existing RiskAnalyzer |
| `quantmind.feature_snapshots` | partial | Production annual Parquet is now exposed read-only with exact inventory and a real immutable QM2 Snapshot; training has not switched |
| `factor_lab.official_v7_source` | partial | Official V7 donor capabilities; not yet migrated |
| `quantmind2.project_knowledge` | partial | Bootstrap, Ledger persistence/indexing, strict self-reference-free Manifest v2 production, bounded historical-v2 compatibility and isolated evidence exist; API/UI and production deployment do not |
| `quantmind2.data_foundation` | partial | Daily Bars and Legacy Feature provider boundaries, real legacy immutable Snapshot, quality, validation, safe readers and CLI exist; real TDX and production consumer switches do not |
| `quantmind2.factor_dsl` | partial | Closed typed AST, strict admission, canonical Template/Instance identities and dataset-aware compiler exist; optimization, Registry and Agent loop do not |
| `quantmind2.factor_compute` | partial | Deterministic Snapshot-only executor and immutable Factor Values v1 exist; distributed compute, Registry, validation and production consumers do not |
| `quantmind2.research_skill` | planned | ADR-0009 and ResearchDecision contract only; no Skill runtime |
| `quantmind2.decision_validator` | planned | Contract/schema exists; no validation service or permission enforcement |
| `quantmind2.code_orchestrator` | planned | Control responsibilities accepted; no v2 runtime implementation |
| Remaining QuantMind 2.0 research/data components | planned | Frozen architecture only |

The persistence audit selects the future Project Knowledge/Ledger integration
boundary but adds no runtime component: API control-plane ownership,
`backend.shared.database_manager_v2` async PostgreSQL access, API model metadata,
and a future explicit `quantmind2` PostgreSQL schema. See
`docs/quantmind2/implementation/LEDGER_PERSISTENCE_REALITY_AUDIT_V1.md`.

QM2-P0-002A1b1 adds the pure domain package at
`backend/services/engine/project_knowledge/domain/`: immutable Task, Run,
relationship, change, test, artifact, reference, limitation, and recommendation
objects plus enums/errors/validators. It is not persistence and does not change
the future API control-plane Repository ownership selected by the audit.

QM2-P0-002A1b2 adds persistence-independent Repository Protocols, query values,
errors, and an `InMemoryLedgerRepository` contract test double. The test double
is not a production adapter, durable store, database transaction, or source of
truth.

QM2-P0-002A2a1 adds API-Base SQLAlchemy mappings for only Task, Run, and
RunRelationship. The metadata can compile PostgreSQL DDL but has not created a
schema or table.

QM2-P0-002A2a2a adds API-Base SQLAlchemy mappings for ChangedFile,
ChangedSymbol, TestExecution, and ImplementationArtifact. Their technical IDs,
A1b2 natural unique keys, restrictive Run FKs, enum-derived checks, cross-field
checks, and indexes are static metadata only. ComponentReference,
ArchitectureDecisionReference, Limitation, and RecommendedTask now complete the
eleven static target mappings. The complete explicit Mapper layer now exists;
migration, production Repository, Session/UoW, API, and UI remain planned.

QM2-P0-002A2a2b1 adds static composite-primary-key mappings for
ComponentReference and ArchitectureDecisionReference. The only foreign keys
point restrictively to Run; Component Catalog and ADR Index remain Git-derived
facts rather than database FK authorities.

QM2-P0-002A2a2b2 adds Limitation and RecommendedTask mappings. They use stable
global IDs, restrictive Run FKs, Domain-enum-derived checks, and no Component
or future Task FK. No annotation row, schema, or table was created. Mappers,
migration, deployed schema/tables, Repository, API, and UI remain planned.

QM2-P0-002A2a2c1 adds the Mapper Identity and Conversion Contract plus
recomputable ChangedFile/ChangedSymbol identity vectors. It fixes pure
conversion, logical repository identity, value/error/round-trip, and version
rules for all eleven families. That statement describes the c1 historical
increment; c2c now realizes the full contract.

QM2-P0-002A2a2c2a implements the API persistence Mapper foundation and
ImplementationTask bidirectional conversion. QM2-P0-002A2a2c2b adds
ImplementationRun bidirectional conversion with explicit logical repository
identity, five exact Enums, UTC-aware time, nullable commit/hash fields, Domain
state validation, and ORM-only version handling. QM2-P0-002A2a2c2c completes
RunRelationship, Detail, Reference, and Annotation conversion plus frozen
ChangedFile/ChangedSymbol technical IDs and drift verification. Repository,
migration, database, trusted identity binding, and Indexer layers are now
implemented; API/UI and production deployment remain unimplemented.

QM2-P0-002A2b adds explicit versioned Ledger migration `0001`, a
zero-dependency `psql` runner, fresh-install invocation, and opt-in disposable
PostgreSQL verification. The migration creates and safely rolls back all eleven
business tables; exact ORM/catalog parity, constraints, indexes, valid/invalid
writes, idempotency, checksum drift, rollback atomicity, and reapply are
verified. This does not add a PostgreSQL Repository, business Session/UoW,
Manifest Parser/Indexer, Git consistency service, API, UI, or production
deployment.

QM2-P0-002A3 adds the production asynchronous PostgreSQL Repository contract
implementation and explicit Unit of Work. It reuses the shared DatabaseManager
sessionmaker, never commits inside Repository methods, contains insert races in
savepoints, applies conditional expected-version updates, serializes DAG edge
admission with a transaction advisory lock plus recursive CTE, and preserves
atomic batches. Disposable PostgreSQL 15 and cross-implementation scenarios
verify behavior. QM2-P0-002B adds Manifest/Git parsing and indexing. API/UI,
production deployment, and research business modules remain absent. Historical
Manifest v1 Runs cannot be indexed where required Domain evidence is missing.

QM2-P0-002B1 adds the default Manifest v2 producer and strict exchange
contract. New Runs can now express complete Task/Run/Relationship, all detail,
reference, and annotation families, typed artifact locations, logical
repository identity, Mapper/identity versions, and canonical integrity. v1
remains immutable compatibility. The B1 Run itself passes full Git and isolated
PostgreSQL indexing/replay/conflict verification; no production deployment,
historical backfill, API, or UI was added.
