# Codex Handoff

## Repository state

- QuantMind root: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`
- Base commit: `e9b0c7d5d00a870a687fc2daeb3c7aa64a0e2e08`
- Dirty before QM2-P0-001: no
- Unrelated dirty files: none
- Uncommitted work after task: yes, QM2-P0-001 files only

## Official Factor Lab source

- Root: `/tmp/quantmind_factor_lab_real_bounded_v7_orchestrator_v1/`
- Source: `/tmp/quantmind_factor_lab_real_bounded_v7_orchestrator_v1/backend/services/engine/factor_lab/`
- Branch: `factor-lab/real-bounded-v7-orchestrator-v1`
- Commit: `c83192c2278767e03f008bc39197b1ba33bfb6a9`
- It remained read-only during QM2-P0-001.

## Current position

- Architecture: QuantMind 2.0 Architecture v1, frozen.
- Current task: `QM2-P0-001`.
- Latest run: `QM2-P0-001-20260713T183614Z-e9b0c7d`.
- Task status: completed_uncommitted after validation.
- Recommended next tasks: QM2-P0-002 or QM2-P0-003 only.

## Unconfirmed facts

- Concrete TongDaXin Provider implementation and capability contract.
- Long-term durable location for the official Factor Lab source.
- Unified database migration mechanism for QuantMind 2.0.
- Final artifact storage backend for large snapshot and ledger artifacts.

## Constraints that must not be broken

- Do not replace LightGBM or Qlib.
- Do not put Python `factor_impl.py` in the v1 standard factor path.
- Keep Factor, Model, and Portfolio optimization separate.
- Keep Research Memory, Project Architecture Memory, and Implementation Ledger separate.
- Do not expose Frozen Test to Agent, Optimizer, or Campaign Memory.
- Do not treat plans, mocks, fixtures, fallbacks, or temporary evidence as implemented production facts.
- Do not modify accepted ADRs silently.

## Next-session read order

Read `CONTEXT_INDEX.md`, Project Charter, Architecture v1, Current State, this
Handoff, task-related ADRs, Component Catalog, the latest relevant
Implementation Run, then current code, Git state, and tests.
