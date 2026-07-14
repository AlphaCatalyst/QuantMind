# Current Implementation State

Generated: 2026-07-14  
Source base commit: `e9b0c7d5d00a870a687fc2daeb3c7aa64a0e2e08`

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

- Factor DSL / Canonical AST
- Factor Optimization
- immutable Factor Registry
- authoritative Dataset Snapshot service
- Frozen Test access isolation
- Registry → Feature Snapshot → LightGBM lineage
- Unified Signal Service
- Project Knowledge API
- Project Knowledge Web UI
- Implementation Ledger PostgreSQL index

## Current task

`QM2-P0-001 — Context Bootstrap and Implementation Contract`

This task establishes repository knowledge, ADR, report, manifest, handoff,
validation, and its own uncommitted Implementation Run. It introduces no
business-domain implementation.

## Next candidates

1. `QM2-P0-002 — Ledger Persistence and Project Knowledge API Foundation`
2. `QM2-P0-003 — TDX Provider Capability Verification`
