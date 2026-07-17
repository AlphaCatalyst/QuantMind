# QM2-P0-007 Implementation Report

## 1. Task Summary

Implemented Factor Registry v1 and its Promotion Contract. The real immutable
research evidence registers 14 Factor Instances as 10 Validation-rejected, one
Validation-passed-not-selected, and three Frozen-rejected. No Entry is a
promotion candidate, approved, or active.

## 2. Goal

Create a content-addressed, immutable and traceable Registry that preserves
Optimization, Validation, Selection, Frozen and correction lineage without
letting Agent, Optimizer, Validation, or Registry automatically approve Factors.

## 3. Scope

- Frozen domain objects, enums, strict parsers and JSON Schemas.
- Evidence verification and deterministic status derivation.
- Conservative Promotion Policy and explicit Promotion Decisions.
- Atomic immutable Registry Snapshot, exact existing and safe readers.
- CLI build/validate/inspect/list/plan-decision/apply-decision.
- Real 14-entry Registry proof, documentation, tests and Project Memory.

## 4. Explicit Non-goals

No new research execution, Optimization, Validation, Candidate Selection,
Frozen access, metric recomputation, Agent campaign, automatic approval or
activation, Registry database, API/UI, LightGBM, Qlib, signal, portfolio or
backtest implementation.

## 5. Preflight State

- Repository: `quantmind-main` at the requested absolute root.
- Branch: `master`.
- Base commit: `ff4a61bf04e3e8194b6883831aa8a5d36ddb06d8`.
- Working tree: clean; unrelated dirty files: none.
- Factor Lab was read-only. Its 18-file non-cache source digest before work was
  `8d06c49e622b8d8031eb6283caa4e1d2df81642a108e3b0d1650d01b845c9aee`.
- Two requested document paths had moved: the DSL and Values contracts were
  read from `docs/quantmind2/contracts/FACTOR_DSL_V1.md` and
  `docs/quantmind2/contracts/FACTOR_VALUES_V1.md`; no document was moved.

## 6. What Changed

Added a separate `factor_registry` package, CLI, strict Entry/Policy/Decision
schemas, implementation contracts, real-evidence tests, stable Registry
queries, context validation updates and this Run. Updated current state,
handoff, catalog, terminology and roadmap to the exact next task.

## 7. Why It Changed

Validation metrics and Frozen observations are research evidence, not promotion
authority. Registry provides the missing immutable boundary between evidence,
governed status, explicit decisions, and future consumers.

## 8. Files Changed

Changes are limited to `backend/services/engine/factor_registry/`, its tests,
`tools/quantmind2/`, `docs/quantmind2/`, and the context-bootstrap test. The
Manifest carries the complete repository-relative path inventory and hashes.

## 9. Important Classes / Functions / Documents

- `FactorPromotionPolicy`, `RegistryEntry`, `FactorPromotionDecision`,
  `RegistrySnapshot`.
- `build_entries_from_evidence`, `derive_status`, `promotion_gate`,
  `plan_decision`, `publish_snapshot`, `validate_registry_snapshot`.
- `load_registry_snapshot`, query helpers, and the Registry CLI.
- `FACTOR_REGISTRY_V1.md` and `FACTOR_PROMOTION_CONTRACT_V1.md`.

## 10. API Changes

No HTTP API or production endpoint changed. A local Python reader and CLI were
added.

## 11. Database Changes

None. No connection or migration was performed.

## 12. Configuration / Environment Changes

None. No dependency, lockfile or runtime configuration changed. Runtime
Registry output is under `/private/tmp/qm2-p0-007-registry`.

## 13. Runtime Flow

```text
Optimization + Validation + Selection + Frozen + 006F correction
-> evidence verification -> 14 Registry Entries -> Policy gates
-> immutable Registry Snapshot -> read-only query
```

A legal explicit Decision would create a successor Snapshot. No real approve or
activate Decision was created.

## 14. Architecture Impact

Realizes the frozen Factor Registry boundary without merging it into
Optimization or Validation. Research Evidence, Entry, Decision and Snapshot
remain distinct. Family v1 equals Template ID. Agent access is read-only and
excludes Frozen details and promotion authority.

## 15. Security Impact

The closed Decision source enum permits only `human` and `control_layer`.
Approve and activate are separate legal transitions; Agent/Optimizer sources,
stale Snapshot references, weakened safety policies, corrupt artifacts and
illegal transitions fail closed. Actor authentication/authorization remains
deferred.

## 16. Data Lineage Impact

Each Entry records exact Template, Instance, parameters, Dataset Snapshot,
Factor Values, Study/Trial, Validation/Selection/Frozen IDs, Train orientation,
protocols and evidence file hashes. Registry does not copy Parquet, read labels,
or recompute metrics.

## 17. Tests Executed

- Focused Registry suite: 27 passed.
- Real CLI build, evidence validation, inspect, list and exact-existing replay:
  passed; runtime tree digest
  `58b5d535d4aa677508efe183c0d0bb1e433b1a5de8f4cc7435e733cf79cf1ec7`.
- First related regression: 169 passed, 9 skipped, 2 failed because the context
  Schema still ended its next-task enum at QM2-P0-007.
- Second real-artifact regression: 179 passed, 1 context-validator failure due
  to its obsolete exact-next-task invariant.
- After bounded contract updates: context unittest 21 passed and Context
  Bootstrap 39 checks passed.
- Final full related real-artifact regression: 184 passed with zero failures or
  skips. Static checks are recorded in the Manifest and final task response.
- The same 18-file non-cache Factor Lab content-digest-v1 check after work was
  `8d06c49e622b8d8031eb6283caa4e1d2df81642a108e3b0d1650d01b845c9aee`,
  equal to preflight.

## 18. Test Results

All final relevant tests passed. The two intermediate failures were accurately
reproduced and resolved by extending only Project Memory machine contracts to
QM2-P0-008. No Registry production behavior was relaxed.

## 19. Known Limitations

- Offline local artifact only; no Registry database, API/UI or durable storage.
- No actor authentication/authorization service.
- No automatic correlation/redundancy analysis.
- No Registry-to-LightGBM/Qlib consumer path and no active Factor.
- Existing QM2-P0-006 historical Run remains Git-inconsistent; separate 006F
  correction evidence is preserved.
- Real TDX availability remains unresolved.

## 20. Compatibility / Migration Notes

Additive package and documentation only. Existing DSL, Optimization,
Validation, LightGBM, Qlib and Ledger formats are unchanged. Runtime Snapshot
schema and Policy are version 1.

## 21. Rollback Notes

Revert the single QM2-P0-007 commit and delete the optional
`/private/tmp/qm2-p0-007-registry` runtime directory. No database, source data,
research artifacts or production configuration requires rollback.

## 22. Remaining Work

Agent Research Campaign v1 remains unimplemented. Registry persistence/API,
durable artifacts, permissions, redundancy, downstream consumers and
activation also remain deferred.

## 23. Recommended Next Task

Only `QM2-P0-008 — Agent Research Campaign v1`. Agent may propose new Factor
Templates and ResearchDecisions but cannot mutate Registry, read Frozen Test
details, tune from Frozen observations, or approve/activate Factors.

## 24. Git / Workspace State

This Run is produced against base `ff4a61b`. One independent commit named
`feat(qm2): add factor registry v1` is required; no amend or push is authorized.
The final response records the verified post-commit clean state.

## 25. Artifact Index

- Registry source package and CLI.
- Three strict JSON Schemas and two implementation contracts.
- Real runtime Snapshot
  `frs_436f4a966ea0c00ee2182c665813cd74cc13bb900a7022604ad9efc26849f2d9`
  under Policy
  `fpp_6ca41655ea0ec5692ef2799674ef743a8bf91a6cf58718e124163bf033e255a3`.
- This Report and its self-reference-free Manifest v2.
