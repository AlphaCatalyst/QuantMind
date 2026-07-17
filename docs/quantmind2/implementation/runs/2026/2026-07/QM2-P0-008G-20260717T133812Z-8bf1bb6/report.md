# QM2-P0-008G Implementation Report

## Task Summary

QM2-P0-008G reconciles the Baseline and External Agent Registry siblings into one immutable multi-parent canonical Registry and applies a fixed Development-evidence gate for future Fresh Validation. It does not run Agent, Optimization, Development, formal Validation, Frozen Test, promotion, model, signal, Qlib, or backtest work.

## Goal, Scope, and Explicit Non-goals

The scope is Registry reconciliation, admission policy/result, bounded evidence verification, sanitized memory outcome, CLI, schemas, tests, documentation, and Project Memory. Source snapshots and Campaign artifacts remain unchanged. No dependency, lockfile, database, API, UI, runtime configuration, Factor Lab source, or historical Implementation Run was modified.

## Preflight State

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`
- Base: `8bf1bb6daa6ed444ac5b4924595aeb4f0690d249`
- Dirty before: false; unrelated dirty files: none.
- Factor Lab official source was read-only. Its established 18-source-file digest is `c25252a40ff9d5f74c596af9faa4c15a599f15ce0031f719a42cd2f04a80409c` before and after.

## Registry Branch Diagnosis

Original `frs_436f4a966ea0c00ee2182c665813cd74cc13bb900a7022604ad9efc26849f2d9` is the exact `previous_registry_snapshot_id` of both Baseline `frs_d40bfd7497ad56d3f71fd16dd7363222d32a5528e8780ca3765c27ca3c584718` and External `frs_7ab0a844d791abf4dbd62c5558a7261078875bbc0b3606aa1b02ce591cf01054`. This is a sibling graph, not continuation. Across 32 source Entry occurrences, 14 identical ancestor Entries deduplicate; four Baseline and one External additions yield 19 Entries. All three source snapshots validate. Both siblings have zero Decisions.

## What Changed and Why

- `RegistryReconciliation` implements stable source ordering, exact duplicate deduplication, conflict hard failure, immutable evidence, and exact replay.
- Registry Snapshot v2 binds sorted multi-parent lineage while v1 identity/reading remains unchanged.
- `FreshValidationAdmissionPolicy` freezes mandatory safety/statistical gates and candidate budgets.
- source evidence verification validates immutable Campaign, Study/Trial hashes and identities, Factor Values, Registry lineage, Development identity/quarantine, and pre-Development orientation without recomputation.
- `FreshValidationAdmissionResult` publishes bounded candidate summaries only; no daily IC, label, raw row, or Frozen result is copied.
- canonical Registry Entries retain `research_registered` and gain only policy/result/outcome/reasons/rank evidence.
- sanitized Agent memory exposes only advanced/not-advanced outcome names.

## Runtime Flow and Proof

The command `python tools/quantmind2/fresh_validation_admission.py evaluate-admission --output-root /private/tmp/qm2-p0-008g-final` validated both Campaign branches, merged Entries, evaluated five candidates, and published:

- reconciliation `frr_9112702e368326365d6f4adb144633c7d0cf3ae59baa61ed76270ae86e93cb32`;
- policy `fvap_e8af2fd66f311a35160e073258c3f910fe13fe767d0cd4389b90f536c6394efa`;
- admission result `fvar_89e61fe674bff1d10d46c9bea3913a456f236bbc191578291529736480a831ab`;
- canonical Registry `frs_f0a08cc472270cf80f2ae8c1141de17871dacbe2edccba8eb4ffe05ca45d3ba4`.

Three Baseline factors were admitted. Baseline liquidity-range was rejected by the total budget. External `fi_207c3b82f4b9f3a77e064513ad03a64e6e2d69dc939e6fc1e68aa4fc8fad0549` remained orientation `+1`; its selected Trial's stored, oriented 2025 mean RankIC is `-0.03098286034429056`, so it was rejected by `DEVELOPMENT_MEAN_RANK_IC_BELOW_GATE`. No direction flip, Trial reselection, metric recomputation, threshold relaxation, or Frozen access occurred. Exact replay validates and returns all three existing output identities.

## Architecture, Security, and Data Lineage Impact

The Registry now distinguishes linear v1 snapshots from immutable v2 multi-parent reconciliation. Project Memory names exactly one canonical Registry. Admission is explicitly upstream of future formal Validation and downstream of contaminated Development. Agent/Optimizer/Frozen boundaries are unchanged. Promotion candidate, approved, and active counts remain zero. No production database, secret, network call, or executable Agent code was introduced.

## Tests Executed and Results

- Targeted Registry/admission/Campaign tests: 63 passed.
- DSL/Optimization/Validation/Dataset/Ledger/Context regression: after updating the expected current task, 119 passed and 8 environment-gated real-artifact tests skipped; these are rerun in final verification.
- Focused Context Bootstrap and new tests: 38 passed; bootstrap 39 checks passed.
- Actual CLI proof and exact replay: passed.
- JSON parsing, schema checks, `py_compile`, `git diff --check`, final diff-scope inspection, and Factor Lab digest: recorded in the final Manifest verification entries.
- One exploratory test invocation had 29 passing cases but exited nonzero because repository-wide coverage was below the global 5% threshold for a small selected suite; the formal targeted invocations use `--no-cov` and pass. This was not a test assertion failure.

## Files and Important Symbols

Production additions are isolated to `factor_registry.reconciliation` and `fresh_validation_admission`; compatible changes affect Registry models/parser/snapshot and sanitized research memory. Important symbols include `RegistryReconciliation`, `merge_registry_snapshots`, `FreshValidationAdmissionPolicy`, `CandidateEvidence`, `evaluate_admission`, `collect_candidate_evidence`, `publish_admission_result`, and `reconcile_and_admit`. Documentation, schemas, CLI, tests, and Project Memory are listed in the Manifest.

## API, Database, Configuration, and Dependency Changes

No API endpoint, database migration/table, configuration, environment contract, dependency, or lockfile changed.

## Known Limitations and Compatibility

Artifacts are currently proven under `/private/tmp`; durable artifact storage remains open. Admission uses contaminated Development evidence only to allocate future data and makes no predictive or promotion claim. The three admitted candidates still require candidate lock, future watermark/maturity, and a one-time fresh protocol. Old Registry snapshots retain byte/identity compatibility; rollback is deletion/revert of this commit plus restoring Project Memory to the prior sibling state. Source artifacts are never overwritten.

## Remaining Work and Recommended Next Task

Only `QM2-P0-009 — Fresh Validation Protocol for Admitted Agent-generated Factors` is recommended.

## Git / Workspace State and Artifact Index

This Run is prepared as `completed_uncommitted` with `result_commit=null`, then committed once without amend or push. Runtime artifacts are under `/private/tmp/qm2-p0-008g-final`; the authoritative implementation report and Manifest are in this Run directory.
