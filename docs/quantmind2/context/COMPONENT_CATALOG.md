# Component Catalog

The machine-readable catalog is authoritative for the initial component list.
Statuses describe current implementation, not architectural intention.

| Component | Status | Evidence |
|---|---|---|
| `quantmind.training` | implemented | Existing LocalDockerOrchestrator and training script |
| `quantmind.inference` | implemented | Existing ModelLoader, DataAdapter, InferenceService |
| `quantmind.qlib_backtest` | implemented | Existing QlibBacktestService and Qlib runtime |
| `quantmind.risk` | implemented | Existing RiskAnalyzer |
| `quantmind.feature_snapshots` | partial | 152-column annual Parquet snapshots, incomplete QM2 lineage |
| `factor_lab.official_v7_source` | partial | Official V7 donor capabilities; not yet migrated |
| `quantmind2.project_knowledge` | partial | File bootstrap and persistence reality audit exist; domain/Repository/API/UI/index DB not implemented |
| `quantmind2.research_skill` | planned | ADR-0009 and ResearchDecision contract only; no Skill runtime |
| `quantmind2.decision_validator` | planned | Contract/schema exists; no validation service or permission enforcement |
| `quantmind2.code_orchestrator` | planned | Control responsibilities accepted; no v2 runtime implementation |
| Remaining QuantMind 2.0 research/data components | planned | Frozen architecture only |

The persistence audit selects the future Project Knowledge/Ledger integration
boundary but adds no runtime component: API control-plane ownership,
`backend.shared.database_manager_v2` async PostgreSQL access, API model metadata,
and a future explicit `quantmind2` PostgreSQL schema. See
`docs/quantmind2/implementation/LEDGER_PERSISTENCE_REALITY_AUDIT_V1.md`.
