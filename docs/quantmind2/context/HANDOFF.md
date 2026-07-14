# Codex Handoff

## Repository state

- QuantMind root: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`
- P0-001 commit: `5504bdb94ddf817976f74a09e323cf8fb1eacf4a`
- Current latest commit: the commit containing this handoff; resolve it with
  `git log -1 --format=%H -- docs/quantmind2/context/HANDOFF.md`.
- Dirty before QM2-P0-001F: no, immediately after the P0-001 commit
- Unrelated dirty files: none
- Uncommitted work after the finalization commit: no

## Official Factor Lab source

- Root: `/tmp/quantmind_factor_lab_real_bounded_v7_orchestrator_v1/`
- Source: `/tmp/quantmind_factor_lab_real_bounded_v7_orchestrator_v1/backend/services/engine/factor_lab/`
- Branch: `factor-lab/real-bounded-v7-orchestrator-v1`
- Commit: `c83192c2278767e03f008bc39197b1ba33bfb6a9`
- It remained read-only and clean during QM2-P0-001 and QM2-P0-001F.

## Current position

- Architecture: QuantMind 2.0 Architecture v1, frozen.
- `QM2-P0-001` is complete and committed at
  `5504bdb94ddf817976f74a09e323cf8fb1eacf4a`.
- Original immutable run: `QM2-P0-001-20260713T183614Z-e9b0c7d`, retaining
  historical status `completed_uncommitted`.
- Finalization task: `QM2-P0-001F`, complete.
- Latest run: `QM2-P0-001F-20260714T140245Z-5504bdb`.
- Recommended next task: `QM2-P0-002A — Ledger Domain and Persistence
  Foundation`; it has not started.
- The machine-readable v1 handoff records parent roadmap task `QM2-P0-002`
  because its enum does not yet admit the `QM2-P0-002A` subtask identifier.

## Unconfirmed facts

- Concrete TongDaXin Provider implementation and capability contract.
- Long-term durable location for the official Factor Lab source.
- Unified database migration mechanism for QuantMind 2.0.
- Final artifact storage backend for large snapshot and ledger artifacts.
- A first-class Manifest field for non-correction relationships between runs.

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
