# QM2-R1-005 Implementation Report

## 1. Task Summary

- Task: `QM2-R1-005 — Factor and Strategy Parameter Optimization Overfit Ablation v1`
- Result: completed
- Base: `82f13f92d9accd39e1ec9209c38a66b37ccff457`
- Branch: `master`
- Evidence class: `retrospective_parameter_optimization_ablation`
- Final Assessment: `poa1_15e9398eae7eb3dfadedf7391a8bb597e563050897f8adeaac5ca1f906c69f1a`

## 2. Goal

Separate factor, strategy and combined parameter-search effects for the two
immutable R1-003 Candidates and their equal-weight combination. Compare no,
local and full search without generating a Factor or changing research state.

## 3. Scope

- Recover R1-003 Proposal, Template Definition, Candidate Lock, Trial Detail,
  factor values and equal-weight Assessment evidence from the Artifact Store.
- Execute F0/F1/F2, S0/S1/S2 and O0/O1/O2 under four walk-forward Folds.
- Report 2019–2024, 2025 and 2026H1 gain, Generalization Gap, Winner's Curse,
  rank stability, Fold consistency, plateau width, search intensity and costs.
- Publish and cold-recover six immutable diagnostic Artifact kinds.

## 4. Explicit Non-goals

- No Agent call, new Proposal, Template, Factor or Feature.
- No Tushare/network call, Fresh Validation, Frozen Test or predictive claim.
- No Candidate/Registry state mutation, Promotion or production action.
- No optimizer-default, Qlib algorithm, DSL/AST, orientation, data or strategy
  contract change.

## 5. Preflight State

- Repository root: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`
- HEAD/base: `82f13f92d9accd39e1ec9209c38a66b37ccff457`
- Worktree: clean
- Unrelated dirty files: none
- R1-004 Report, Manifest, Project Memory and diagnostic contract were read
  without modification to its immutable Run.

## 6. What Changed

- Added the independent `parameter_optimization_ablation` domain, metrics,
  protocol, Artifact producer/validator and Store-backed execution/replay.
- Registered six Artifact kinds with Store validation and runtime cache paths.
- Added a ten-command CLI and 26 focused tests.
- Added the frozen ablation contract and Project Memory entries.
- Added this Implementation Report and Manifest v2.

## 7. Why It Changed

The prior experiments showed historical improvement followed by 2025/2026H1
degradation. This task establishes diagnostic evidence that separates factor
parameters, strategy parameters and combined search intensity while holding
the Factor structures, Dataset, Universe and formal Qlib execution fixed.

## 8. Candidate and Parameter Audit

| Object | Agent default | Original full space | R1-003 final report | Orientation |
|---|---:|---|---:|---:|
| Candidate A, momentum baseline deviation | `baseline_window=20` | `[10,20,40]` | `40` | `-1` |
| Candidate B, momentum plus pullback reward | `high_distance_weight=0.5` | `[0.25,0.5,0.75]` | `0.75` | `-1` |

Both Candidates expose one three-point parameter. F1 and F2 therefore contain
the same set. Revision 2 compares canonical parameter hashes rather than list
order and truthfully records `factor_f1_equals_f2_space=true`.

## 9. Fold and Selection Contract

Research/evaluation pairs are 2019–2020/2021, 2019–2021/2022,
2019–2022/2023 and 2019–2023/2024. Each selected Trial receives a content
derived `poafl1_` identity before evaluation is requested. 2025 and 2026H1 are
report-only. A mode-independent `poac1_` configuration identity prevents the
F1/F2 mode label from altering the frozen tie-break.

## 10. Factor Ablation Results

Under fixed TopK20/n_drop5/rebalance5, 2019–2024 CSI300 excess for A/B/ensemble
is 29.01%/-7.76%/28.36% at F0 and 31.98%/-2.58%/15.85% at F1/F2. Later-period
average excess falls for B and the ensemble. Candidate A improves in 2026H1
but not 2025. F1/F2 select A window 40, B weight 0.25 and ensemble 40/0.5.

## 11. Strategy Ablation Results

With F0 Factors, S1 selects 30/5/5 for all three objects. S2 selects 20/0/10,
30/10/10 and 30/5/5 for A/B/ensemble. S1 research excess rises by 31.82pp and
31.08pp for A/B but report gain averages +0.77pp and -3.70pp. S2 research gain
is -6.67pp/+23.11pp/-10.48pp for A/B/ensemble.

## 12. Combined Ablation Results

O1 research gain is +9.55pp/+32.19pp/-11.61pp for A/B/ensemble; average report
gain is -0.64pp/-2.21pp/-1.46pp. O2 research gain is
+18.08pp/+32.19pp/-11.61pp; average report gain is
-2.04pp/-2.21pp/-1.46pp. Search intensity raises research excess while later
average excess monotonically falls for Candidate A and Candidate B.

## 13. Generalization, Ranking and Stability

- CSI300-excess Generalization Gap for O1 A/B/ensemble:
  +10.18pp/+34.40pp/-10.15pp.
- CSI300-excess Generalization Gap for O2 A/B/ensemble:
  +20.12pp/+34.40pp/-10.15pp.
- 162 rank-stability rows cover all four Evaluation Years plus final 2025 and
  2026H1 reports. Median Spearman is 0.4104; median Kendall is 0.2381.
- 108 Winner's-Curse records identify 39 evaluation-year reversals and six
  final cases where both 2025 and 2026H1 selected-minus-median are non-positive.
- No case has positive gross improvement fully consumed into non-positive net
  improvement by costs. Cost is not the primary overfit mechanism.

## 14. Fold Consistency and Parameter Plateau

F1/F2 Candidate A adjacent-match rate is 1.0; Candidate B and ensemble are
0.667. Exact-match rates are zero. Factor plateaus are acceptable for A and
broad for B/ensemble. Strategy and combined Fold choices are generally not
exact; O2 adjacent rates are 0.333/0.333/0.0 for A/B/ensemble. Plateau evidence
is not sufficient to overcome the negative generalization evidence.

## 15. Classification and Framework Decision

| Layer | Local/light | Full | Advisory decision |
|---|---|---|---|
| Factor | A inconclusive; B likely overfit; ensemble inconclusive | same | `default_first_optimize_only_on_failure` |
| Strategy | A inconclusive; B likely overfit; ensemble inconclusive | same labels | `default_first_optimize_only_on_failure` |
| Combined | A/B likely overfit; ensemble inconclusive | same labels | `suspend_parameter_optimization` |

`apply_automatically=false`. The result changes no runtime default or state.

## 16. Artifact Store and Runtime Flow

Final contract revision 2 Artifacts:

1. Spec `poa1_033893bef91bd5b3ffa660caa813cd2fa06d76d497e1e7a660c7b7462ac93dd4`
2. Factor `poa1_8f4109c7d2dd09ca772e700e2a2c9ea2a07387a233d4821e02e48a8470ca2a05`
3. Strategy `poa1_aa240a6ff8ec1f6255463a6eb704f6b148a659a5bb1dbb20d8e59ed3f66766b8`
4. Combined `poa1_baf2ce5933efa3c9587fc248649ef329d0cc7aebfbeeac490a37cbd8ed23c11f`
5. Rank stability `poa1_b9b7552c401e231460800d9860fa2275b278f8e61d6518cb769cfa14914fffcb`
6. Assessment `poa1_15e9398eae7eb3dfadedf7391a8bb597e563050897f8adeaac5ca1f906c69f1a`

Cold recovery restores all six. Store status is healthy, Missing 0 and
Unreferenced 0. Exact replay reports Factor Optimization 0, Strategy
Optimization 0, Qlib 0, Agent 0, network 0, Promotion 0, new artifacts 0 and
new blobs 0.

## 17. Immutable Revision Note

Pre-final runs exposed two evidence corrections before the Implementation Run
was closed. One preliminary Spec omitted the source R1-003 Assessment. Contract
revision 1 then compared equal parameter lists by order and reported a false
F1/F2 equality summary. These Store artifacts remain immutable and are not in
the final Assessment lineage. Contract revision 2 binds the source Assessment,
uses set equality and is the only revision selected by replay. No historical
R1-003 or R1-004 Artifact was modified.

## 18. API Changes

None. The CLI is an offline engineering/research entry point, not an API.

## 19. Database Changes

None. No migration, schema, table or database connection was used.

## 20. Configuration / Environment Changes

None. No dependency or lockfile was changed. Offline ephemeral runtime
packages were selected by `uv --no-project --offline` for tests and Qlib.

## 21. Architecture, Security and Data Lineage Impact

The implementation adds a diagnostic consumer of existing Factor Optimization,
Strategy Optimization, Qlib and Store boundaries. It does not merge optimizer
layers. Tushare remains the only data authority. No credential is accepted or
stored. Dataset, Candidate, Template, Factor Instance, signal and source
Assessment IDs are explicit in immutable lineage.

## 22. Tests Executed and Results

- Focused unit tests: 26 passed.
- Relevant regression: 114 passed, 38 existing numeric warnings.
- Real Study: 1,470 unique formal Qlib results, 0 rejected.
- Cold recovery/exact replay: passed, six recovered, all calls/new objects 0.
- JSON, py_compile, Context Bootstrap, Git diff and post-commit Planner are
  recorded in the Manifest; no unexecuted test is described as passed.
- Two setup attempts failed before regression execution: one referenced a
  nonexistent test path; one omitted `jsonschema`. The corrected command is
  the 114-test result above.

## 23. Known Limitations

- 2025/2026H1 are contaminated retrospective reports, not Fresh Validation,
  Frozen Test or predictive evidence.
- F1 equals F2 for both frozen Factor Templates; factor search-size effect is
  not identifiable.
- The existing Qlib service attempts model-registry resolution; `asyncpg` was
  absent in the offline runtime, so it logged the established non-blocking
  fallback before each signal backtest. No database connection occurred.
- The official bounded Factor Lab directory contains no normal files in the
  current external environment and was not modified.

## 24. Compatibility, Rollback and Remaining Work

Existing Factor/Strategy optimization, Candidate, Registry and Qlib behavior
is unchanged. Code rollback is the single task commit. Store Artifacts are
immutable evidence and are not deleted by rollback. Applying any advisory
decision requires a separately authorized task. No successor is authorized.

## 25. Git / Workspace State and Artifact Index

- Implementation Run: `QM2-R1-005-20260722T052636Z-82f13f9`
- Manifest: adjacent `manifest.json`
- Suggested commit: `feat(qm2): diagnose parameter optimization overfit`
- Commit: one new commit, no amend, no push
- Expected final worktree: clean
