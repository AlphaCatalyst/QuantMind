# QuantMind 2.0 Initial Roadmap

| Task | Status | Priority | Dependencies | Objective | Explicit non-goals | Acceptance summary |
|---|---|---|---|---|---|---|
| QM2-P0-001 Context Bootstrap and Implementation Contract | completed_uncommitted | P0 | none | Establish repository context, ADR, report, manifest, handoff, validation | No business code, DB, API | Machine and human bootstrap validates and records itself |
| QM2-P0-002 Ledger Persistence and Project Knowledge API Foundation | planned | P0 | 001 | Index immutable Git implementation runs and expose read APIs | No web UI or business domains | Git/hash conflicts are visible and queryable |
| QM2-P0-003 TDX Provider Capability Verification | planned | P0 | 001 | Verify concrete provider and capability schemas | No dependency selection without approval; no ingestion | Every capability has verified evidence or explicit unavailable status |
| QM2-P0-004 Collection Control Plane and Raw Store | planned | P0 | 003 | Full/incremental collection, retry, checkpoint, immutable raw partitions | No normalization or snapshot publish | Partial failure preserves committed raw partitions and correct checkpoint |
| QM2-P0-005 Normalization, Corporate Actions and Data Quality | planned | P0 | 004 | Normalize market semantics and gate quality | No factor computation | Critical quality failures block publish readiness |
| QM2-P0-006 Dataset Snapshot Publish and Qlib Adapter v1 | planned | P0 | 005 | Publish immutable snapshots and atomic Qlib views | No research/model implementation | Only published snapshots are consumable and views reconcile to source |
| QM2-P0-007 Core Research Domain and Registry Identities | planned | P0 | 001 | Separate immutable research object identities | No DSL execution or validation algorithms | Each identity is independently versioned and referenced |
| QM2-P0-008 DSL v1 and Agent Output Contract | planned | P0 | 007 | Canonical AST and parameterized Agent output | No structure evolution or Python main path | DSL candidates validate and hash canonically |
| QM2-P0-009 DSL Factor Compute and Materialization | planned | P0 | 006,008 | Deterministic DSL compute and Parquet materialization | No optimizer or official backtest | Cache identity binds AST, parameters, snapshot, engine version |
| QM2-P0-010 Random Factor Optimization v1 | planned | P0 | 009 | Budgeted random search for window, weight, threshold | No Bayesian, model, portfolio, or structure search | Trials are immutable, reproducible, deduplicated, and Frozen-Test-free |
