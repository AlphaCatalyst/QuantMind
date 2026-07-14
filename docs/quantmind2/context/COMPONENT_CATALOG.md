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
| `quantmind2.project_knowledge` | partial | File bootstrap in QM2-P0-001; API/UI/index DB not implemented |
| Remaining QuantMind 2.0 research/data components | planned | Frozen architecture only |
