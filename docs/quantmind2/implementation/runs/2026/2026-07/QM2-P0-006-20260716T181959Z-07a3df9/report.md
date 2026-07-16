# QM2-P0-006 Implementation Report

## 1. Task Summary

Implemented Factor Validation v1 with audited production-label parity,
immutable temporal data and labels, Train-only orientation, Validation-only
selection, and an independent one-time Frozen Test. Status at report generation
is `completed_uncommitted`.

## 2. Goal

Close the supervised research loop for all 14 QM2-P0-005 Trials without
leaking labels into DSL/Optimization or using Frozen results for reselection.

## 3. Scope

Label reality audit/contract, immutable Label Snapshot and Validation Dataset,
split/purge/embargo, strict Validation Spec, full-period Factor Values, daily
IC/RankIC/ICIR/coverage, Train orientation, eligibility/order, immutable Result
and Selection, isolated Frozen access/lock/result, CLI, tests, contracts and
Project Memory.

## 4. Explicit Non-goals

No Registry/promotion, Agent loop, new parameter search, structure mutation,
post-Frozen tuning, LightGBM, Qlib, signal, portfolio, backtest, Sharpe,
trading, API/UI/database, training/inference changes, dependency installation,
lockfile, Factor Lab edit, amend or push.

## 5. Preflight State

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch/base: `master` / `07a3df9e5809b4b87e31736e00994521af896ebf`
- Dirty before: no; unrelated dirty files: none.
- Factor Lab before digest:
  `42d16e39b36f95c9663426d979ef950064ff76b4b4eaa8fd70acd262b14965e5`.
- Existing venv supplied pandas/numpy/pyarrow/pytest; no package was installed.

## 6. What Changed

Added `backend/services/engine/factor_validation`, offline CLI, strict JSON
Schema, unit/real-artifact tests, three contracts, context updates and this Run.
Large Parquet/Factor Values/validation artifacts remain under
`/private/tmp/qm2-p0-006-validation` and are not committed.

## 7. Why It Changed

Mechanical Optimization cannot establish predictive evidence. This layer
separates label materialization, temporal evidence, candidate selection and
Frozen confirmation while preserving exact Study/Trial/Template/Instance/
Values lineage.

## 8. Files Changed

The Manifest records the exact repository-relative paths and hashes. No
training, inference, Qlib, trading, dependency, lockfile, runtime configuration
or Factor Lab source changed.

## 9. Important Classes / Functions / Documents

- `LabelContract`, `FactorValidationSpec`, `FrozenTestAccessContext`
- `build_production_labels`, `build_validation_dataset`
- `calculate_split_metrics`, `train_orientation`, `selection_eligibility`
- `evaluate_validation`, `validate_validation_result`
- `evaluate_frozen`, `validate_frozen_result`
- `FACTOR_LABEL_CONTRACT_V1.md`, `FACTOR_VALIDATION_V1.md`,
  `FROZEN_TEST_PROTOCOL_V1.md`

## 10. API Changes

None. Offline CLI commands are `audit-label`, `build-dataset`, `validate-spec`,
`plan`, `evaluate-validation`, `evaluate-frozen`, `validate-result`, `inspect`.

## 11. Database Changes

None.

## 12. Configuration / Environment Changes

None. All runtime roots were explicit arguments under `/private/tmp`.

## 13. Runtime Flow

Audit current loader -> materialize features and independent labels -> publish
immutable Dataset/Snapshot -> verify both Studies/all 14 Trials -> recompile
against new Snapshot -> compute Train orientation -> compute Validation metrics
-> publish immutable Result/Selection -> lock protocol -> read only selected
candidate Frozen labels -> publish immutable Frozen Result -> exact replay.

## 14. Architecture Impact

Implements the Factor Validation/Frozen isolation portions of ADR-0003,
ADR-0006 and ADR-0007. The component is partial research infrastructure, not
production alpha or Registry authority.

## 15. Security Impact

Strict schemas and IDs, bounded feature universe, no arbitrary Python, no
secret persistence, label-free DSL/Optimizer import-scope tests, no ordinary
Frozen reader, explicit access context, immutable Selection prerequisite and
protocol lock/conflict behavior.

## 16. Data Lineage Impact

Dataset `vd_1ac71a8b1bab36f7d4304fe13c14cbb936f073d0426b76e0c73096a819c3ed62`
binds actual annual source-byte hashes, required terminals/label inputs,
production Label Contract, selected universe, split/purge/embargo, feature
Snapshot and output Parquet hashes. Label Snapshot is independently identified.
Each Trial points to a new Snapshot-bound Instance and Values artifact.

## 17. Tests Executed

- Initial focused test: 9 assertions passed; pytest returned failure only from
  the unrelated whole-repository coverage floor. Acceptance reruns used
  `--no-cov`.
- Focused plus real artifacts: 12 passed, 0 failed/skipped.
- Final related DSL/Optimization/Legacy/Context/Manifest regression and static
  validation are recorded in the Manifest after final execution.

## 18. Test Results and Real Evidence

Production Label is adjusted close T+1 / adjusted open T+1 - 1 for H=1,
float32 inputs, retained extreme opens with weight 0.5, and daily 5-MAD/sample
std z-score as `model_label`. The intended 20% STAR/GEM branch is unreachable
for prefixed real symbols, so the current effective threshold is 9.5%.

The 300-symbol Dataset has 396,392 feature rows. Effective splits are Train
2022-01-04..2023-12-28 (483 dates), Validation
2024-01-02..2024-12-30 (241), quarantined development
2025-01-02..2025-12-30 (242), and Frozen
2026-01-05..2026-06-23 (111). One boundary trading date per split is purged.

All 14 Trials produced full-period Values. Four passed Validation gates.
Selection `fvs_f679a63089f076c11315f522f4d59dc8248731863ec6aafc02b70c9762819e9c`
locked ranks 1–3: `fot_4d78...edf2`, `fot_566b...e7ec`, and
`fot_187f...e12d`. Result is
`fvr_b9f247e42487267754d5e6128beb4f90a379b77853462b6ca25f0f2918c51ab0`.

Frozen Result
`fvt_734478fcc0291910667321669e5b5293f64594efe6f0e5b1334779f4d921c787`
reports oriented mean RankIC -0.004275, 0.000909 and 0.004020 respectively.
The result did not change selection or Optimization and makes no backtest or
future-return claim.

## 19. Known Limitations

- One deterministic 300-symbol universe and one temporal protocol only.
- No regime, turnover, cost, correlation, walk-forward or multiple-testing
  correction in v1.
- Current source adjustment factors are parity-checked, but upstream vendor PIT
  provenance remains unproven.
- Runtime `/private/tmp` artifacts and official Factor Lab source are not
  durable production storage.
- Frozen access is a code boundary/protocol lock, not an authenticated service.

## 20. Compatibility / Migration Notes

New parallel research package only. Existing Alpha158, LightGBM, inference,
Qlib and portfolio behavior is unchanged.

## 21. Rollback Notes

Revert the single QM2-P0-006 commit. Runtime artifacts can be removed
independently; there is no migration or configuration rollback.

## 22. Remaining Work

Factor Registry admission/promotion must reference these immutable artifacts
without recomputing or altering validation. Model/signal/Qlib paths remain
later tasks.

## 23. Recommended Next Task

Only `QM2-P0-007 — Factor Registry v1 and Promotion Contract`.

## 24. Git / Workspace State

Pre-commit noncanonical Run; `result_commit` is null, no amend/push. One
independent commit is required.

## 25. Artifact Index

- This report and Manifest v2.
- Runtime root `/private/tmp/qm2-p0-006-validation`.
- Dataset, Label Snapshot, compatible feature Snapshot, 14 Factor Values,
  Validation Result, Candidate Selection, Frozen protocol lock/result.
