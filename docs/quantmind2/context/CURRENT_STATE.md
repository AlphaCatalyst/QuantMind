# Current Implementation State

Generated: 2026-07-14
Verified source commit before this task: `05c2db2b0797c6c173b4916d7f70dc97853dc5ec`

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
- authoritative Dataset Snapshot service
- Frozen Test access isolation
- Registry → Feature Snapshot → LightGBM lineage
- Unified Signal Service
- Project Knowledge API
- Project Knowledge Web UI
- Implementation Ledger PostgreSQL index

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

## Next task

`QM2-P0-002A1 — Ledger Persistence Mechanism Audit and Domain Contract` is the
only recommended next task and has not started.
