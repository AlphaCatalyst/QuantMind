# Component Catalog

## QM2-R2-003 addition

- `quantmind2.autonomous_factor_program` — implemented at
  `backend/services/engine/autonomous_factor_program`; owns three-Lane
  orchestration, Program evidence partitions, global novelty/search exposure,
  minimum-coverage early stop, Lane and Union locks, 2021–2024 Pass/Fail
  validation, HAC/BH control, survivor-only registration, Fresh Locks, cold
  validation and exact replay.

## QM2-R2-001 addition

- `quantmind2.autonomous_factor_campaign` — implemented at
  `backend/services/engine/autonomous_factor_campaign`; owns the frozen
  Campaign Spec, aggregate-memory Round Planner, static Admission, bounded
  orchestration, checkpoints, terminal Candidate/Near-miss reporting, cold
  recovery and exact replay.
- It composes the existing Agent, Factor DSL, default-first governance,
  formal Qlib and Artifact Store. It cannot use Fresh/report-period selection
  evidence, run Strategy/Combined optimization, fetch market data, promote a
  Candidate or claim production suitability.

## QM2-R1-010 addition

- `quantmind2.breadth_gated_momentum` — implemented at
  `backend/services/engine/breadth_gated_momentum`. It binds immutable Signal
  D to the formal PIT breadth state, publishes fixed U/G/R retrospective
  diagnostics, and accumulates no-backfill Fresh evidence from Tushare.
- The component cannot call Agent or Optimization, mutate Candidate/Registry,
  or promote. The Fresh state remains accumulating below the frozen
  60/5/20/3 minimums.

## QM2-R1-009 addition

- `quantmind2.momentum_tail_alpha` — implemented at
  `backend/services/engine/momentum_tail_alpha`; diagnoses the immutable
  R1-008 Signal D through deciles, tail metrics, fixed gross Top-N baskets,
  2023 decomposition, beta/style/breadth exposure, stability, transition and
  decay, then publishes five Store-backed Artifact kinds. It is retrospective
  only, has no PIT industry attribution or formal Top-N costs, and cannot
  create Candidates, Registry state or Promotion evidence.

## QM2-R1-008 addition

- `quantmind2.low_frequency_momentum` — implemented at
  `backend/services/engine/low_frequency_momentum`; pre-registers four fixed
  signals and B0/L1 protocols, runs annual/full-period formal Qlib evidence,
  applies frozen eligibility, and supports Store recovery and zero-call replay.

## QM2-R1-004 addition

- `quantmind2.momentum_alpha_diagnostics` — implemented at
  `backend/services/engine/momentum_alpha_diagnostics`. It owns immutable
  semantic audit, cross-sectional metrics, beta/style/contribution/cost/regime
  diagnostics, failure classification, Store publication, cold recovery and
  exact replay for the locked R1-003 signals. It does not own Factor creation,
  Optimization, Registry state transition, Strategy selection or Promotion.

## QM2-R1-003 addition

- `quantmind2.skip_recent_momentum` — implemented at
  `backend/services/engine/skip_recent_momentum`. It owns the complete
  Agent-response through Experiment evidence chain, bounded six-subfamily
  research, four-Fold locks, formal Qlib evaluation and zero-call replay.
  Results remain retrospective and research-only.

## QM2-R1-002 addition

- `quantmind2.momentum_factor_iteration` — implemented at
  `backend/services/engine/momentum_factor_iteration`. It owns the 36-feature
  Momentum Catalog, PIT regime diagnostics, family/complexity gates, bounded
  external-Agent orchestration, four-fold parameter selection and neighborhood
  stability, fixed formal Qlib evidence, research-only locks, optional
  ensembles, immutable Store artifacts and exact replay. It does not own data
  collection, Strategy Optimization, Promotion, Fresh Validation, LightGBM,
  API or UI.

## QM2-R1-005 addition

- `quantmind2.parameter_optimization_ablation` — implemented at
  `backend/services/engine/parameter_optimization_ablation`; owns immutable
  recovery of the R1-003 defaults/search spaces, F0/F1/F2, S0/S1/S2 and
  O0/O1/O2 walk-forward diagnostics, formal Qlib evidence, overfit
  classification, Store publication, cold recovery and exact replay.
- It is retrospective and advisory only. It creates no Factor, makes no Agent
  or network call, preserves `research_registered`, performs no Promotion and
  cannot change optimizer defaults. Both Factors have one three-point
  parameter, so their F1 and F2 factor spaces are identical.

## QM2-R1-001 addition

- `quantmind2.expanded_factor_iteration` — implemented at
  `backend/services/engine/expanded_factor_iteration`; owns existing-Factor
  definition recovery, Fixed-100 Feature Catalog v2 computation and quality,
  structural/equivalence redundancy, bounded external-Agent proposals,
  four-Fold parameter isolation, fixed formal Qlib evaluation, research-only
  Candidate locking, immutable Store publication, recovery and exact replay.
  Current evidence is retrospective and mixed, with no Promotion authority.

## QM2-P0-017 addition

- `quantmind2.strategy_optimization` — implemented at
  `backend/services/engine/strategy_optimization`; owns the strict three-field
  search contract, deterministic Study/Trial identities, formal Qlib annual
  metrics, eligibility, stable ordering, sensitivity, Candidate Locks and
  research-only Results.
- It depends on Unified Signal, existing Qlib, Tushare Fixed-100 lifecycle and
  the Artifact Store. It does not own Factor/Signal/model/risk optimization or
  Promotion. All current Locks are retrospective, parameter-unstable and
  ineligible for production.

## QM2-P0-016 additions

- `quantmind2.signal_service` — implemented at
  `backend/services/engine/unified_signal`; owns strict Factor inputs,
  transformation, fixed/equal combination, missingness quality, identities and
  immutable `unified_signal` artifacts.
- `quantmind2.strategy_layer` — implemented at
  `backend/services/engine/strategy_layer`; owns fixed V1 Strategy Specs,
  execution plans, deterministic desired targets, formal Qlib result import,
  canonicality and the research-only Strategy Registry.
- Both components are offline/store-backed V1 implementations. They do not
  provide Agent calls, parameter optimization, LightGBM, Promotion, API or UI.
  The current Qlib source exposes actual positions but not formal pre-trade
  target weights.

## `quantmind2.security_termination`

- Status: implemented
- Responsibility: represent governed termination/settlement evidence, classify
  formal Qlib exposure, and gate canonical strategy and benchmark conclusions
- Source/target: `backend/services/engine/security_termination/`
- Key symbols: `SecurityTerminationEvent`, `SecurityTerminationPolicyV1`,
  `run_termination_audit`
- Dependencies: formal Qlib, Tushare authority and Artifact Store
- Limitations: no governed corporate-action settlement evidence exists for the
  audited 2025 benchmark positions; TopkDropout does not expose formal daily
  target weights
- Evidence: four 2025 Qlib parity reruns, immutable Store audit, cold recovery
  and exact replay in QM2-P0-015G

## `quantmind2.research_artifact_store`

- Status: implemented
- Responsibility: immutable content-addressed large research-artifact storage,
  Domain validation, inventory, integrity and verified recovery
- Source/target: `backend/services/engine/artifact_store/`
- Key symbols: `ResearchArtifactStore`, `FileSystemResearchArtifactStore`,
  `StoredArtifactDescriptor`, `import_artifact`, `materialize_artifact`,
  `scan_store_integrity`, `build_reachability_plan`
- Dependencies: existing Dataset, DSL, Optimization, Validation, Registry,
  Campaign, Admission and Fresh formal Validators
- Limitations: local filesystem only; cloud backend, metadata API/UI and
  deletion GC are not implemented
- Evidence: verified real migration and recovery in QM2-P0-010

## `quantmind2.artifact_runtime`

- Status: implemented
- Responsibility: Store-backed reference, policy, verified resolution,
  materialization, publication, exact replay and research-state recovery
- Source/target: `backend/services/engine/artifact_runtime/`
- Key symbols: `ArtifactRuntimePolicy`, `StoreBackedArtifactRef`,
  `ArtifactRuntimeContext`, `resolve_artifact`, `publish_domain_artifact`,
  `recover_research_state`
- Dependencies: `quantmind2.research_artifact_store` and unchanged Domain
  validators
- Limitations: single-host/process cache and locks; no cloud/distributed
  backend, database catalog, API/UI, Qlib or LightGBM cutover
- Evidence: empty-cache Store-only recovery and exact replay in QM2-P0-011

The machine-readable catalog is authoritative for the initial component list.
Statuses describe current implementation, not architectural intention.

| Component | Status | Evidence |
|---|---|---|
| `quantmind.training` | implemented | Existing LocalDockerOrchestrator and training script |
| `quantmind.inference` | implemented | Existing ModelLoader, DataAdapter, InferenceService |
| `quantmind.qlib_backtest` | implemented | Existing QlibBacktestService and Qlib runtime |
| `quantmind.risk` | implemented | Existing RiskAnalyzer |
| `quantmind.feature_snapshots` | deprecated | Legacy annual Parquet authority was retired and physically purged by QM2-P0-014; implementation code remains only for historical compatibility |
| `factor_lab.official_v7_source` | partial | Official V7 donor capabilities; not yet migrated |
| `quantmind2.project_knowledge` | partial | Bootstrap, Ledger persistence/indexing, strict self-reference-free Manifest v2 production, immutable correction evidence and isolated replay exist; API/UI and production deployment do not |
| `quantmind2.data_foundation` | implemented | Tushare-only fixed-500 raw/normalized/Feature/Label authority, fixed-100 Qlib view, Artifact Store recovery, purge governance and CLI are implemented; incremental updates are separate |
| `quantmind2.factor_dsl` | partial | Closed typed AST, strict admission, canonical Template/Instance identities, dataset-aware compiler and six accepted PIT rolling operators exist; structure evolution, API and UI do not |
| `quantmind2.factor_compute` | partial | Deterministic Snapshot-only executor and immutable Factor Values v1 exist; distributed compute, Registry, validation and production consumers do not |
| `quantmind2.factor_optimization` | partial | Deterministic declared-parameter Study/Trial execution, budgets, mechanical metrics, eligibility, immutable artifacts and replay exist; predictive validation, random/Bayesian search, threshold, Registry/API and distributed execution do not |
| `quantmind2.optimization_governance` | implemented | Default-first Factor/Strategy policies, one-hop rescue budgets, diagnostic-only full search, suspended combined optimization, Candidate metadata gates, Store artifacts and zero-call replay are enforced for new research |
| `quantmind2.default_first_momentum_search` | implemented | Six real Agent rounds evaluate explicit defaults before bounded local rescue on the formal Momentum Dataset and Qlib; the frozen zero-candidate result, complete artifacts, recovery and exact replay are preserved |
| `quantmind2.factor_validation` | partial | Immutable temporal Dataset, Validation Result, Selection and isolated Frozen Result exist; current evidence does not constitute Registry promotion |
| `quantmind2.factor_registry` | partial | Immutable Entry/Policy/Decision/Snapshot artifacts, multi-parent reconciliation, strict evidence lineage, queries and CLI exist; current canonical 20-entry Snapshot has one new research-only Entry and no promotion candidate, approved or active Factor; persistence/API are deferred |
| `quantmind2.research_campaign` | partial | Closed Goal/Decision, generated parameter-contract summary, structured repair, sanitized memory, bounded state machine, novelty, real Optimization/Development/Registry loop and CLI exist; QM2-P0-012 remains partial while QM2-P0-012F completed one real Store-backed external Campaign |
| `quantmind2.research_artifact_store` | implemented | Immutable Store contains and verifies the QM2-R1-007 default-first research chain; current integrity is healthy |
| `quantmind2.artifact_runtime` | implemented | Store-required resolution/publication, runtime counters, Campaign graph recovery and exact replay operate from an empty cache |
| `quantmind2.security_termination` | implemented | Generic evidence-gated policy and formal 2025 Qlib/Fixed-100 termination audit; unresolved benchmark settlement remains noncanonical |
| `quantmind2.corporate_actions` | partial | Tushare capability capture, immutable Raw/Event artifacts, generic settlement engine, benchmark contract and exact replay exist; current live evidence is insufficient, so no benchmark revision is publishable |
| `quantmind2.research_skill` | planned | ADR-0009 and ResearchDecision contract only; no Skill runtime |
| `quantmind2.decision_validator` | planned | Contract/schema exists; no validation service or permission enforcement |
| `quantmind2.code_orchestrator` | planned | Control responsibilities accepted; no v2 runtime implementation |
| Remaining QuantMind 2.0 research/data components | planned | Frozen architecture only |
| `quantmind2.technical_feature_factory` | implemented | Factory v2 combines six accepted rolling operators and six PIT primitives with unlabeled bounded Agent generation, quality/novelty admission, research materialization and immutable Catalog v3 |
| `quantmind2.archetype_alpha_program` | implemented | Three-Lane default-first Alpha research consumes Catalog v2/v3, freezes monotonic/tail tests, applies locked validation/global BH FDR, and supports retrospective-only survivor output |
| `quantmind2.autonomous_research_supervisor` | implemented | Cycle 002 consumes the operator, primitive and Feature v3 catalogs, preserves retrospective/Fresh boundaries, applies stop controls, and provides cold recovery/resume/zero-call replay |

`quantmind2.optimization_governance` applies the corrected R1-005 business
decision without modifying the v1 optimization engines or historical objects.
Its full-search modes are diagnostic consumers only; Candidate selection uses
explicit defaults or a failure-gated local rescue, and Promotion remains out
of scope.

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

QM2-P0-009 adds partial `quantmind2.fresh_validation` under
`backend/services/engine/fresh_validation`. It locks the exact admitted cohort,
maintains append-only exposure and immutable Watermarks, builds post-lock
accrual artifacts, and enforces a one-time earliest-60-date evaluator. The real
source predates the lock, so no real evaluation result or promotion exists.
