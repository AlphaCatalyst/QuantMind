# QM2-R2-007 Implementation Report

## 1. Task Result

`completed`. The fixed-configuration LightGBM research program, Cycle 003
Supervisor integration, four-fold retrospective execution, stability audit,
multiple-testing control, recovery, resume and exact replay are complete.
The formal outcome is `completed_no_model_candidate`.

## 2. Preflight State

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch: `master`
- Base commit: `dff10cd71c5d25bcbd1dea9b1092ff16427aeacf`
- Dirty before: no
- Unrelated dirty files: none
- Factor Lab: read-only and unchanged

## 3. Existing Training Audit

The existing algorithm and execution chain are reused. The training entry is
`docker/training/train.py`; orchestration is in
`backend/services/engine/training/local_docker_orchestrator.py`. Existing
production defaults include LightGBM regression, learning rate `0.05`, up to
`1000` rounds and early stopping at `100`; the program freezes a separate,
more conservative research configuration before observing any fold.

The existing training script constructs a return from `Close[T+H]` and
`Open[T+1]`; its `label_formula` metadata is not fully aligned with that code
and remains a pre-existing known issue. Model serialization and prediction
materialization stay on the existing LightGBM/prediction path. Formal portfolio
results use the existing Qlib consumer and are not replaced by a local
simulator.

## 4. Label Contract

- Label ID: `tld_7f765006c745d2a8d4f3ce885d1322dd96441fd547800ebe997c5452b0ddc969`
- Name: `model_label`
- Formula: `adjusted_close[T+1] / adjusted_open[T+1] - 1`
- Entry/exit: next-session adjusted open/close
- Horizon and signal lag: one session
- Corporate actions: adjusted prices
- Cross-section: same-date 5-MAD winsorization and population z-score
- Missing policy: omit the sample unless the next quote exists, volume is
  positive and the security is not conservatively locked
- Sample weighting: the existing valid sample-weight field is respected; no
  new weighting scheme is introduced

## 5. Leakage Audit

Audit ID:
`mtla1_cf3aec89dfa95464a7ea0390971ddb5ac60d558ddd989d91b198b6258f2c1f97`.
Feature row `T` is paired only with official label row `T`; purge is ten
sessions; early stopping is disabled; Outer Test is excluded from training,
preprocessing fitting and Bundle C membership. Same-date transforms are
stateless. Bundle C quality selection and redundancy removal are fitted on
training rows only. PIT violations are zero.

## 6. Model Program Architecture

The new bounded component is
`backend/services/engine/fixed_configuration_model_program/`. It reuses the
immutable Artifact Store, existing LightGBM package, formal Tushare snapshot,
fixed-universe lifecycle policy, Unified Signal/strategy semantics, Qlib
backtest service and existing Supervisor. It does not create a parallel model
service or a second Supervisor.

Canonical objects are `FixedConfigurationModelSpecV1`,
`ModelFeatureBundleSpecV1`, `PurgedWalkForwardSpecV1`, fold
training/prediction/result artifacts, `ModelStabilityAssessmentV1`, multiple
testing control, conditional model candidate/Fresh Lock objects and an empty
distillation queue.

## 7. Canonical LightGBM Configuration

- Model: LightGBM `gbdt`, regression objective, L2 metric
- Learning rate: `0.05`
- Leaves/depth/min leaf: `31`, `-1`, `50`
- Feature/bagging fraction and frequency: `0.8`, `0.8`, `5`
- L1/L2: `0.0`, `0.0`
- Rounds: fixed `200`
- Early stopping: disabled
- Threads: `1`
- Determinism: enabled, forced column-wise
- Model hyperparameter optimization calls: `0`

The configuration was frozen as model spec
`fcms1_27c7102a662731b28d5142166dacc398e82ca4c701870c6657bfd83cdcd7ad94`.

## 8. Seed Ensemble

The fixed seeds are `20260701`, `20260702` and `20260703`. Every Bundle/window
trains all three configurations and uses the equal-weight mean prediction.
No seed is selected after observing performance.

## 9. Feature Bundle A

`existing_technical_core`,
`mfbs1_ba2b9f7967c028230ddc0026a4e76d13891ab104c32adddf8af14d5e9358a24b`:
36 formal pre-R2-006 research technical features, no new features and no raw
primitives.

## 10. Feature Bundle B

`expanded_technical_space`,
`mfbs1_e55d3d6c9a810cf3f3098de90ee948b6c150a45d178760d8e83f7e098a55e415`:
the 20 R2-006 Terminal Features plus six frozen R2-006 primitives.

## 11. Feature Bundle C

`combined_decorrelated_technical`,
`mfbs1_19cc24e0ff0eeaa45d5cb10a1e1280bf6da0eabace1e1c380b8bc7bfc68504d6`:
62 preregistered candidates. The unchanged train-only, label-free quality rule
and greedy `|Spearman| < 0.95` retention selected `50/50/49/50` features for
Folds 1-4 and `50/50` for the two contaminated reporting windows.

## 12. Bundle-freeze Evidence

All three Bundle specs have `frozen_before_training=true`,
`label_used_for_membership=false` and
`performance_used_for_membership=false`. Bundle C additionally has
`training_only_selection=true`. Feature Catalog
`tfc3_b903...23aea` and Primitive Catalog `tpc2_b9f...7208` are read-only
inputs. Feature Agent calls, Alpha Agent calls and new Feature/DSL/Primitive
writes are zero.

## 13. Purged Walk-forward Spec

Spec:
`pwfs1_6a226e117f7eca56f380f1e7445bcb462dc7b7ffeedfe5d0e076b6d4a9c0a7d9`.
It contains four expanding annual Outer Tests, ten-session purge and zero
embargo. The resulting purged train ends are 2020-12-17, 2021-12-17,
2022-12-16 and 2023-12-15. Test windows are the frozen 2021, 2022, 2023 and
2024 windows.

## 14. Fold 1

Train 2019-01-02..2020-12-17; Test 2021-01-04..2021-12-31.
Train rows `47,570` after `56` lifecycle/label validity exclusions; test rows
`24,242`; 100 symbols.

## 15. Fold 2

Train 2019-01-02..2021-12-17; Test 2022-01-04..2022-12-30.
Train rows `71,792` after `76` exclusions; test rows `24,191`; 100 symbols.

## 16. Fold 3

Train 2019-01-02..2022-12-16; Test 2023-01-03..2023-12-29.
Train rows `95,959` after `100` exclusions; test rows `24,200`; 100 symbols.

## 17. Fold 4

Train 2019-01-02..2023-12-15; Test 2024-01-02..2024-12-31.
Train rows `120,138` after `121` exclusions; test rows `24,146`; 100 symbols.

## 18. Annual RankIC

| Bundle | 2021 | 2022 | 2023 | 2024 | Combined |
|---|---:|---:|---:|---:|---:|
| A existing core | -0.002111 | -0.002401 | 0.006008 | 0.001089 | 0.000643 |
| B expanded | -0.010635 | 0.007702 | -0.005625 | -0.009872 | -0.004613 |
| C combined decorrelated | -0.011184 | -0.001190 | 0.004273 | 0.003152 | -0.001247 |

The combined values in this table are the multiple-testing artifact's pooled
daily RankIC means; annual medians used by the gate are A `-0.000511`, B
`-0.007748`, C `0.000981`.

## 19. Annual Strategy Results

Formal Qlib results use TopK 20, n_drop 5, ten-session rebalance, equal weights,
one-session lag and open execution.

| Bundle-Year | Net return | CSI300 excess | Sharpe | Max DD | Turnover | Cost |
|---|---:|---:|---:|---:|---:|---:|
| A-2021 | -2.01% | 4.20% | -0.273 | -11.57% | 17.47 | 14,075 |
| A-2022 | -12.59% | 8.69% | -0.733 | -25.23% | 17.67 | 12,514 |
| A-2023 | -13.51% | -1.77% | -1.171 | -22.51% | 17.78 | 14,768 |
| A-2024 | 27.24% | 11.04% | 1.437 | -11.36% | 18.17 | 16,748 |
| B-2021 | -3.31% | 2.91% | -0.327 | -15.18% | 17.13 | 12,901 |
| B-2022 | -10.17% | 11.10% | -0.680 | -19.83% | 18.21 | 13,832 |
| B-2023 | -4.62% | 7.13% | -0.502 | -15.30% | 17.95 | 15,977 |
| B-2024 | 27.21% | 11.01% | 1.366 | -13.78% | 18.25 | 16,849 |
| C-2021 | 10.30% | 16.51% | 0.594 | -8.87% | 18.30 | 15,426 |
| C-2022 | -11.71% | 9.56% | -0.824 | -21.18% | 17.59 | 12,872 |
| C-2023 | -6.12% | 5.63% | -0.599 | -17.99% | 18.04 | 15,686 |
| C-2024 | 27.43% | 11.23% | 1.476 | -9.82% | 18.00 | 16,880 |

## 20. Bundle Comparison

Bundle C met the incremental-value rule versus A (median RankIC improvement
`0.001492`, median excess improvement `3.95` percentage points and acceptable
drawdown change) but failed the absolute RankIC gate. Bundle B failed its
incremental rule and absolute RankIC gate. A had the best pooled RankIC but
still failed positive-fold and median annual RankIC requirements.

Contaminated reports did not participate in selection:

| Bundle-Period | RankIC | Net return | CSI300 excess | Sharpe | Max DD |
|---|---:|---:|---:|---:|---:|
| A-2025 | 0.010208 | 13.49% | -8.26% | 0.892 | -9.24% |
| A-2026H1 | -0.006273 | -8.90% | -13.18% | -1.424 | -12.14% |
| B-2025 | -0.006607 | 4.34% | -17.41% | 0.222 | -9.66% |
| B-2026H1 | 0.005470 | -9.78% | -14.05% | -1.712 | -11.62% |
| C-2025 | 0.008444 | 10.53% | -11.22% | 0.814 | -6.40% |
| C-2026H1 | 0.001813 | -16.08% | -20.36% | -2.327 | -19.36% |

## 21. Legacy Model Comparator

Status: `legally_incomparable_not_run`. No stored Alpha158 result matches the
exact Tushare Fixed-100 universe, official label, four folds, cost and fixed
strategy protocol. It is excluded from primary hypotheses, BH control and
Candidate creation.

## 22. Feature Importance Stability

Median adjacent-fold importance-rank Spearman / Top10 overlap / Top20 overlap:
A `0.964/0.90/0.95`; B `0.696/0.70/0.90`; C `0.889/0.60/0.80`.
Only native LightGBM gain/split importance is used; SHAP is not added.

## 23. Seed Stability

Worst pairwise prediction Pearson / Spearman / Top20 Jaccard:
A `0.533/0.470/0.300`; B `0.461/0.436/0.261`; C
`0.458/0.433/0.255`. Every fold records `single_seed_selected=false`.

## 24. Model Concentration

All Bundles passed the frozen concentration gate. Median maximum single-feature
gain share / top-five share / adjacent Top10 overlap were A
`4.48%/20.54%/90%`, B `4.40%/21.38%/70%`, C
`2.87%/13.72%/60%`, all within `35%/75%/40%` limits.

## 25. Multiple-testing Control

Artifact:
`mmtc1_659e9d7f7793ae90664c4372907794892acadf9ee95662fbbcb44a8d162aef6f`.
HAC lag is 10 and BH FDR is 10% across exactly three primary hypotheses.
A/B/C raw p-values are `0.421892/0.917134/0.661864`; all adjusted q-values
are `0.917134`; all survivor flags are false.

## 26. Retrospective Model Gate

- A failed positive RankIC folds (`2`) and median annual RankIC.
- B failed positive RankIC folds (`1`), median/worst/combined RankIC and
  incremental value.
- C failed positive RankIC folds (`2`), median/worst/combined RankIC.

Data quality, PIT, turnover and concentration checks passed. Failures are
research outcomes, not incomplete execution.

## 27. Model Candidates

Retrospective Model Candidates: `0`. No object was relabeled as registered,
validated, approved, active or production.

## 28. Distillation Queue

Queue:
`mfdq1_72908f268b8fee7823d5aaaca60eb579b74d0eb3dfe2130e96e7ee6403c34306`.
It is formally published and empty because no Bundle passed the retrospective
gate. It triggers no DSL/Agent research.

## 29. Supervisor Cycle 003

The existing Supervisor
`arsv1_1d07cf5c773e0fef1c7855b874235405e8c1e0e247caa1f4af51876aecabd14e`
executed `autonomous_research_cycle_003` with research type
`fixed_configuration_model_alpha`. Status is
`completed_no_model_candidate`; no second Supervisor and no automatic Cycle
004 were created.

## 30. Fresh Locks

Fresh Locks: `0`, correctly conditional on zero retrospective candidates.

## 31. Fresh Cohorts

Fresh Cohorts: not required. No Fresh data were backfilled or interpreted.

## 32. Incremental Data Decision

No incremental market-data fetch is authorized or required. Tushare and
network calls are zero; historical data maximum remains 2026-06-23.

## 33. Global Stop Status

`global_authorized_technical_research_space_exhausted`. Both
`single_factor_space_exhausted` and
`model_aggregation_space_exhausted` are true. The Supervisor must not burn
additional Agent/Qlib budget or create Cycle 004 automatically.

## 34. Registry

Registry writes: `0`; Promotion writes: `0`. No model or Factor lifecycle state
was changed.

## 35. Artifact Store

Persistent Store validation reports `healthy`, `missing=0`,
`unreferenced=0`. Fourteen new formal Artifact kinds are registered and
validated. The formal run performed 54 model training calls, 18 prediction
writes and 18 real Qlib calls; Feature/Alpha Agents, all three optimization
layers, Tushare/network, Registry and Promotion remain zero.

## 36. Cold Recovery

The terminal multiple-testing artifact and its reachable graph were
materialized into a clean recovery directory and validated with zero evidence
gaps. Recovery is based on immutable descriptors/blobs rather than the
execution cache.

## 37. Resume Test

Resume of the terminal Model Spec returns `exact_replay`,
`exact_existing=true`, with zero training, prediction, Qlib, Agent,
optimization, candidate, Fresh, Registry, Promotion, Artifact and Blob writes.

## 38. Exact Replay

Program replay and Supervisor `run-next-model-cycle` replay both return
`exact_replay`, zero evidence gaps and all side-effect counters zero. The
Supervisor replay preserves Cycle 003 and reports
`automatic_cycle_004_created=false`.

## 39. Files Added

- `backend/services/engine/fixed_configuration_model_program/__init__.py`
- `backend/services/engine/fixed_configuration_model_program/models.py`
- `backend/services/engine/fixed_configuration_model_program/engine.py`
- `backend/services/tests/test_fixed_configuration_model_program.py`
- `tools/quantmind2/run_fixed_configuration_model_program.py`
- `docs/quantmind2/architecture/FIXED_CONFIGURATION_MODEL_ALPHA_PROGRAM_V1.md`
- `docs/quantmind2/architecture/schemas/fixed_configuration_model_alpha_program_v1.schema.json`
- this Report and its Manifest v2

## 40. Files Modified

- Artifact Store kind/validator and external-reference contracts
- Supervisor exports, orchestration and CLI
- Project Memory Component Catalog, Current State, Handoff, Known Issues and
  Roadmap in Markdown and JSON
- Current State JSON Schema for the explicit Cycle 003 state
- Context bootstrap validator and its focused regression assertion

No dependency, lockfile, database migration, API, UI, historical Artifact,
market-data or Factor Lab file changed.

## 41. Tests Executed

- New fixed-model unit suite: `10 passed`.
- Fixed-model, Supervisor and isolated Artifact Store suites:
  `43 passed`; the combined command additionally selected two pre-existing
  real-research tests that failed because their legacy `/private/tmp`
  QM2-P0-005 source no longer exists. Those two are environment-bound and not
  caused by this change.
- Full relevant model/Supervisor/Store/Context/Feature Factory/Alpha/Signal/
  Strategy/lifecycle regression: `127 passed`.
- The separately sampled legacy Qlib-backend unit file has three pre-existing
  failures because it patches a removed `backtest_service.importlib` symbol;
  production Qlib was not changed, and all 18 formal Qlib calls completed.
- `validate-program`: valid, zero evidence gaps, Store healthy.
- `resume`: exact replay, all counters zero.
- Program replay: exact replay, all counters zero.
- Supervisor model-cycle replay: exact replay, Cycle 003, no Cycle 004.
- Context bootstrap, JSON parsing, schema validation, `py_compile`,
  `git diff --check` and post-commit Planner are recorded after finalization in
  the Manifest test list.

## 42. Expected vs Actual

| Item | Expected | Actual |
|---|---:|---:|
| Bundles | 3 | 3 |
| Outer folds | 4 | 4 |
| Seeds | 3 | 3 |
| Formal training calls | 54 | 54 |
| Formal prediction writes | 18 | 18 |
| Formal Qlib calls | 18 | 18 |
| Hyperparameter/strategy/combined optimization | 0 | 0 |
| Feature/Alpha Agent calls | 0 | 0 |
| Tushare/network calls | 0 | 0 |
| Model candidates / Fresh Locks | conditional | 0 / 0 |
| Replay side effects | 0 | 0 |
| Cycle 004 | prohibited | not created |

## 43. Implementation Run

- Run ID: `QM2-R2-007-20260724T142049Z-dff10cd`
- Task status before commit: `completed_uncommitted`
- Manifest schema: v2
- Suggested/actual commit message:
  `feat(qm2): research fixed configuration alpha models`
- Result commit is intentionally resolved by the Git-authoritative
  post-commit Planner; no amend is used.

## 44. Project Memory Updates

Current State, Handoff, Component Catalog, Known Issues and Roadmap now record
the fixed-model component, Cycle 003 result, zero Candidate/Fresh outcome,
global stop and the two known output limitations. Historical Project Memory
and research Artifacts are not rewritten.

## 45. Known Limitations

1. The existing training script's `label_formula` metadata remains inconsistent
   with its executable label expression; this task binds the authoritative
   Tushare `model_label` artifact and does not rewrite legacy training.
2. Qlib completes formal strategy evaluation, but its current service does not
   expose durable holdings/trades tables. The fold Artifact therefore publishes
   explicit empty-schema tables; they are not evidence that no trades occurred.
3. LightGBM on this local macOS runtime requires the already-present
   `DYLD_FALLBACK_LIBRARY_PATH` for the environment's OpenMP library. No
   dependency was installed and no lockfile changed.
4. The first interrupted diagnostic attempt left immutable, unreferenced-to-
   this-report Store objects under an older runtime-contract revision. The
   authoritative terminal graph uses revision 2 and Store reachability remains
   healthy with zero unreferenced blobs.
5. The 2025 and 2026H1 metrics are contaminated report-only evidence and cannot
   select, validate or promote a model.

## 46. Final Research Conclusion

Within the preregistered Technical Catalog v3 space, fixed conservative
LightGBM aggregation did not convert the weak technical signals into a
statistically supported retrospective model. A showed a near-zero pooled
RankIC; B and C were negative; none passed both the absolute gate and BH FDR.
The valid conclusion is zero model candidates and a bounded global stop, not a
request to tune models, generate more Factors or reinterpret contaminated
report periods.

## 47. Git State After

The task requires one new commit, no amend and no push. Final post-commit state,
Planner evidence and worktree cleanliness are verified after Manifest
finalization and recorded in the final task response.
