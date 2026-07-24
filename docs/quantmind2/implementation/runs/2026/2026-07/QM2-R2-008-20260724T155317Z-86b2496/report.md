# QM2-R2-008 Implementation Report

## 1. Task Result

`completed_uncommitted`. The executable Label audit, frozen L1/L5/L10
family, 108 fixed LightGBM fits, 36 prediction ensembles, 36 formal Qlib
runs, global nine-hypothesis multiple test, conditional Candidate/Fresh
boundaries, Cycle 004 integration, recovery, resume, and replay are complete.

## 2. Preflight State

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch: `master`
- Base commit: `86b2496dab37201ced1481fa2d214ab322952a71`
- Dirty before: no
- Unrelated dirty files: none
- Factor Lab: read-only and unchanged

## 3. Existing Label Audit

Model metadata declares
`CSZScore(open(T+5)/open(T)-1)`. `docker/training/train.py` does not execute
that metadata expression. It groups by symbol and executes adjusted
`close[T+target_horizon_days] / open[T+1] - 1`. The existing Tushare training
matrix contains `raw_label`, cross-sectional `model_label`, and
`sample_weight`. Formal Qlib strategy holding/rebalancing remains ten
sessions. Audit Artifact: `ela1_c48a0518...274ff`.

## 4. Executable Label Contract

Signal date is T; entry is adjusted open on the first official session after
T; exit is adjusted close on official session T+h. Both observations must be
finite and tradable. Missing quotes, lifecycle exits, and non-tradable
observations stay missing. There is no forward fill, last-price substitution,
or member replacement. The old Label Artifact is not modified.

## 5. Label L1

`trl1_38786d61...cf3a`, `technical_return_1d`: adjusted open T+1 to adjusted
close T+1; non-overlapping control; HAC lag 10.

## 6. Label L5

`trl1_56506cd6...ee3d`, `technical_return_5d`: adjusted open T+1 to adjusted
close T+5 official session; overlapping; HAC lag 10.

## 7. Label L10

`trl1_3ab5acdb...f176`, `technical_return_10d`: adjusted open T+1 to adjusted
close T+10 official session; overlapping; HAC lag 15.

## 8. Label Quality

| Label | Coverage | Finite rows | Daily median | Mean raw | Std raw | Skew | Serial overlap |
|---|---:|---:|---:|---:|---:|---:|---:|
| L1 | 99.925% | 187,929 | 100 | 0.000695 | 0.018447 | 0.667 | -0.0219 |
| L5 | 99.649% | 187,409 | 100 | 0.002137 | 0.045743 | 1.303 | 0.7905 |
| L10 | 99.339% | 186,826 | 100 | 0.003980 | 0.065341 | 1.616 | 0.8949 |

All have Infinity 0 and PIT violations 0. Boundary/missing-quote exclusions
are L1 `98/43`, L5 `490/171`, L10 `980/264`. All quality gates pass.

## 9. Label Overlap and HAC

L5 and L10 explicitly record `overlapping_label=true`; L1 is false. HAC lags
are exactly 10, 10, and 15. All nine daily RankIC hypotheses use these
pre-registered lags before one global BH correction.

## 10. Bundle Freeze

The exact R2-007 IDs are reused: A existing core
`mfbs1_ba2b9f...8a24b`, B expanded `mfbs1_e55d3d...5e415`, and C
de-correlated `mfbs1_19cc24...04d6`. Bundle membership was not regenerated.
Bundle C preserves train-only, label-free quality and redundancy selection.

## 11. Model Configuration

Model Spec `fcms1_27c710...7ad94` is unchanged: existing LightGBM, fixed 200
rounds, no early stopping, deterministic single thread, seeds
`20260701/20260702/20260703`, equal-weight prediction mean. Model,
strategy, and combined optimization calls are all zero.

## 12. Walk-forward

Walk Spec `pwfs1_6a226e...0a7d9` is reused with 2021, 2022, 2023, and 2024
outer tests and expanding 2019-start training. Purge is
`max(10,label_horizon)`, therefore ten sessions for all three labels.
Outer Test is not used for training, preprocessing fit, Feature selection, or
early stopping.

## 13. L1 Fold Results

Annual RankIC by Bundle:

| Bundle | 2021 | 2022 | 2023 | 2024 | Pooled |
|---|---:|---:|---:|---:|---:|
| A | 0.019266 | -0.005312 | 0.000286 | 0.008887 | 0.005795 |
| B | 0.018996 | 0.011442 | 0.010431 | 0.031466 | 0.018085 |
| C | 0.023261 | 0.014540 | 0.013483 | 0.030489 | 0.020446 |

## 14. L5 Fold Results

| Bundle | 2021 | 2022 | 2023 | 2024 | Pooled |
|---|---:|---:|---:|---:|---:|
| A | 0.004662 | -0.003444 | 0.009135 | 0.028419 | 0.009688 |
| B | -0.010821 | -0.015451 | -0.030209 | 0.020814 | -0.008919 |
| C | -0.013975 | -0.022138 | -0.026665 | 0.030255 | -0.008137 |

## 15. L10 Fold Results

| Bundle | 2021 | 2022 | 2023 | 2024 | Pooled |
|---|---:|---:|---:|---:|---:|
| A | -0.009665 | 0.000054 | 0.017397 | 0.036590 | 0.011073 |
| B | -0.030282 | -0.031937 | -0.045970 | 0.022675 | -0.021388 |
| C | -0.027444 | -0.023528 | -0.038555 | 0.037105 | -0.013120 |

Every Fold Artifact also preserves mean IC, RankICIR, positive rate, coverage,
Q10-Q1, Top20 spread, net/benchmark/excess return, Sharpe, drawdown, turnover,
cost, best-ten-day contribution, model files, predictions, signals, and Qlib
evidence.

## 16. RankIC Comparison

Only Bundle A has monotonically increasing pooled RankIC across L1/L5/L10.
That improvement is not cross-year consistent and L10 fails its worst-year
gate. B and C deteriorate from positive L1 to negative L5/L10; both apparent
long-horizon improvements are 2024-driven.

## 17. Strategy Comparison

Median annual net return / CSI300 excess / turnover:

| Bundle | L1 | L5 | L10 |
|---|---|---|---|
| A | -4.53% / 8.92% / 18.03 | -2.20% / 11.03% / 17.95 | -1.03% / 12.20% / 17.97 |
| B | -9.83% / 4.89% / 18.11 | -9.95% / 3.79% / 18.08 | -14.42% / -0.07% / 17.66 |
| C | -2.89% / 9.23% / 17.92 | -10.30% / 0.96% / 17.95 | -7.84% / 5.90% / 17.82 |

Positive portfolio excess does not override the Label-specific RankIC and
global FDR gates.

## 18. Horizon Alignment

A shows pooled RankIC and strategy-excess agreement but not cross-year
monotonicity. B/C show neither alignment nor cross-year persistence.
Consequently the hypothesis that longer Label horizons generally rescue the
expanded technical signal is rejected by this retrospective matrix.

## 19. Model Stability

All nine concentration assessments pass the frozen single-feature, top-five,
and adjacent Top10-overlap limits. All Folds retain the three-seed ensemble;
no single seed is selected. Prediction correlations and Top20 overlaps are
stored per seed pair and Fold.

## 20. Multiple-testing Control

Artifact `mhmt1_9ba1acf8...c7ddc` applies one BH family across exactly nine
hypotheses at q=10%. Survivors:

- L1-B: raw p `0.0004401`, adjusted q `0.0019803`.
- L1-C: raw p `0.00003756`, adjusted q `0.0003381`.

L1-A passes its retrospective gate but adjusted q is `0.280544`. No L5 or
L10 combination passes both Gate and FDR.

## 21. Retrospective Gate

L1 A/B/C pass the frozen absolute gates; B/C also pass incremental value, but
only B/C survive FDR. L5-A passes its gate but fails FDR; L5-B/C fail RankIC,
fold consistency, and incremental checks. L10-A fails worst annual RankIC;
L10-B/C fail RankIC and incremental checks. No threshold was relaxed.

## 22. Label Support Classification

`one_day_label_supported`. This is a research classification, not a production
Label selection or replacement.

## 23. Model Candidates

Two immutable `retrospective_model_candidate` objects exist:
`mhrmc1_6b1a97e5...527c3` and `mhrmc1_83272b1d...56c23`. Both bind L1,
the exact Bundle, Model Spec, Walk Spec, 12 seed models, four predictions,
four Fold results, annual metrics, HAC/BH evidence, stability, and project
contamination. Neither is validated, approved, active, or production.

## 24. Fresh Locks

Two locks exist: `mhmfl1_59790b02...5db17` and
`mhmfl1_1b78c7a9...0cdfc`. Both freeze the model/bundle/label/seed/monthly
retraining/strategy/statistic contract and set `no_backfill=true`.

## 25. Fresh Cohorts

No post-exposure official date exists, so no Fresh observation or evaluated
Fresh Cohort exists. The two same-horizon candidates remain waiting under the
project-level Fresh governance; no historical backfill is performed.

## 26. Supervisor Cycle 004

Explicit Supervisor dispatch reports
`autonomous_research_cycle_004`, type `multi_horizon_model_alpha`, status
`completed_with_label_aligned_candidate`. It reuses the existing Supervisor
identity and creates no second Supervisor. `automatic_cycle_005_created=false`.

## 27. Global Stop Status

Because two candidates survive, the terminal state is
`fresh_candidate_waiting_for_unexposed_data`; technical feature,
fixed-model aggregation, and multi-horizon spaces are not marked globally
exhausted. This does not authorize another automatic research cycle.

## 28. Registry

Registry writes: 0. The canonical Registry and all production model/Label
state remain unchanged.

## 29. Artifact Store

Terminal Report `mhlrr1_53bae8de...b8550f`. Integrity:
`healthy`, Missing 0, Unreferenced 0. Formal execution created immutable Label,
quality, model, prediction, Fold, stability, alignment, testing, Candidate,
Fresh Lock, and terminal artifacts.

## 30. Cold Recovery

Validation and replay from new work roots reconstruct the required authority
and identities from the persistent Store. Status is valid with no evidence
gaps.

## 31. Resume Test

Terminal resume returns exact-existing with Label writes 0, model trainings
0, prediction writes 0, Qlib calls 0, Candidate/Fresh writes 0, and new
Artifacts/Blobs 0.

## 32. Exact Replay

Exact replay returns all required counters at zero: Label, training,
prediction, Qlib, Tushare, network, Candidate, Fresh Lock, Registry,
Promotion, Artifact, and Blob.

## 33. Files Added

- `backend/services/engine/multi_horizon_label_research/`
- `backend/services/tests/test_multi_horizon_label_research.py`
- `tools/quantmind2/run_multi_horizon_label_research.py`
- `docs/quantmind2/architecture/MULTI_HORIZON_LABEL_ALIGNMENT_RESEARCH_V1.md`
- `docs/quantmind2/architecture/schemas/multi_horizon_label_alignment_research_v1.schema.json`
- This Implementation Run Report and Manifest

## 34. Files Modified

Artifact-kind validation/mapping, the reusable fixed-model Fold executor,
Supervisor Cycle dispatch/CLI, Project Memory, Current State schema/context
checks, and directly related tests were modified. No data authority, Feature
Catalog, Bundle, model parameter, strategy parameter, Registry, dependency,
lockfile, database, API, UI, or Factor Lab source changed.

## 35. Tests Executed

- New and fixed-model unit tests: 19 passed.
- Full related suite: 80 passed.
- Context Bootstrap: 42 checks passed.
- Formal execution: 108 training, 36 prediction, 36 Qlib calls.
- Validate/resume/replay/Supervisor replay: passed; zero-call replay.
- JSON parsing, `py_compile`, `git diff --check`, Store integrity: passed.

## 36. Expected vs Actual

Expected and actual formal matrix counts match exactly. Expected conditional
Candidate creation produced two L1 candidates. Expected Store, recovery,
zero-call replay, no Promotion, and no Cycle 005 all match. The research
hypothesis that longer horizons rescue expanded technical Alpha is not
supported.

## 37. Implementation Run

- Run: `QM2-R2-008-20260724T155317Z-86b2496`
- Task status before commit: `completed_uncommitted`
- Verification: full relevant tests plus formal LightGBM/Qlib execution,
  persistent Store validation, recovery, resume, replay, and context checks.

## 38. Project Memory Updates

Current State, Handoff, Component Catalog, Known Issues, Roadmap, and their
machine-readable peers record Cycle 004, L1-only support, two Fresh Locks,
zero Registry/Promotion, no Fresh observation, and no Cycle 005.

## 39. Known Limitations

- Evidence through 2026-07-23 is retrospective and contaminated for future
  selection; no Fresh result exists.
- Existing Qlib wrappers emit optional PostgreSQL/COS lookup warnings and do
  not persist order-level holdings/trades through this consumer boundary.
- Label metadata remains descriptive and mismatched with executable code; this
  task audits but does not alter that legacy contract.
- Fold-level terminal checkpoints prevent completed Fold repetition; a process
  interruption inside a Fold may repeat compute while immutable publication
  still remains exact-existing.

## 40. Final Research Conclusion

Label-horizon mismatch does not explain the failure of the expanded technical
space in the tested way. Expanded and de-correlated technical Bundles are
positive and globally significant only for L1; their L5/L10 RankIC is
negative in 2021-2023 and turns positive only in 2024. The existing core shows
some longer-horizon improvement, but it is not cross-year monotonic and does
not survive the global FDR. The supported state is two L1 retrospective
candidates awaiting genuinely unexposed data—not a production Label change.

## 41. Git State After

Pre-commit result commit is null. The task will create one independent commit
with no amend and no push. Post-commit Planner and clean-worktree evidence are
recorded after commit; no dependency or lockfile change is present.
