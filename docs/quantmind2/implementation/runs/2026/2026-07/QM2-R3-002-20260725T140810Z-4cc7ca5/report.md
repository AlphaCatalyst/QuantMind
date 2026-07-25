# QM2-R3-002 Implementation Report

## 1. Task Result

`completed_uncommitted`

`QM2-R3-002 — Cross-Sectional Ranking and Style-Residual Alpha Discovery v1`
implements both frozen research lanes and completes formal Batch 002. Zero
Survivor is the valid unchanged-gate result.

## 2. Preflight State

- Repository:
  `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`.
- Branch: `master`.
- Base commit: `4cc7ca5afbece6bd23fec8eed27b943592830f74`.
- Workspace dirty before: false.
- Unrelated dirty files: none.
- Formal Supervisor:
  `arsv1_1d07cf5c773e0fef1c7855b874235405e8c1e0e247caa1f4af51876aecabd14e`.
- Existing Fresh objects and Store were read only for isolation and integrity
  assertions, not as research evidence.

## 3. Mainline Status

`mainline_blocked = false`

The Batch reached a legal terminal state. No data, Label, Qlib, persistence or
replay defect remains. No non-blocking runtime detail was promoted into a
mainline engineering task.

## 4. Existing Engine Reuse

The implementation extends the existing Autonomous Research Supervisor and
reuses the R3-001 window set and evaluation semantics, canonical Factor DSL,
Tushare Feature Catalog v3, existing LightGBM training utilities, formal Qlib
runner and filesystem Artifact Store. It does not create a parallel research,
model, backtest or persistence system.

## 5. Batch 002 Spec

- Batch:
  `rbdb1_6689b8ef15abd717047bf3914ac1f9e619f2dc26b9939d1dd986a3638c01b1aa`.
- Name: `rolling_blind_discovery_batch_002`.
- Discovery: `2019-01-02..2021-12-31`.
- Historical rolling evaluation: the exact 18 R3-001 windows,
  `2022-01-04..2026-06-23`.
- Maximum Agent calls/proposals/admissions: `18/54/30`.
- Maximum local rescue/ranking hypotheses/rolling submissions:
  `40/2/12`.
- Maximum Qlib calls/Survivors: `260/5`.
- Strategy: TopK 20, n_drop 5, rebalance 10, equal weight, lag 1, open
  execution, CSI300.
- Manual intervention/planning: `0/0`.
- Automatic Batch 003: false.

## 6. Style Controls Audit

The exact formal Feature definitions are:

- size: `log_circ_mv`;
- beta: `style_beta_20`;
- idiosyncratic volatility: `style_idio_vol_20`;
- liquidity/activity: `amount_ratio_20`.

All four are defined in the existing Tushare Feature Catalog v2 feature
implementation. Beta and idiosyncratic volatility are also explicit Feature
authority-matrix members. Size and amount activity derive from the immutable
normalized market/PIT inputs under formal formulas. No substitute names or
searched control subset were used. The model matrix does not itself make this
fixed control mapping authoritative; the Feature definitions and
residualization contract do.

## 7. Residualization Contract

- Contract:
  `cssr1_57af8aff79197acdd23c0a8c2e7e9b6996ea72dbe6f31135402dd89d31a29db1`.
- Per date: finite joint sample, control population z-scores, intercept,
  deterministic least-squares residual, residual population z-score.
- Minimum finite members: 80.
- Zero-variance controls: removed and recorded.
- Direction: unchanged.
- PIT violations: zero required.
- Cross-time fit, label/return input, return-selected controls and industry
  neutralization: absent.

## 8. Residual DSL Lane

Eighteen automatic Agent calls emitted 54 simple proposals. Fifteen structures
were admitted after canonical DSL validation; each had at most three Terminal
Features, at most one optimizable parameter and AST depth at most six. One
bounded default-first local rescue was used. Every admitted score passed
through the same fixed residualization contract. Raw scores were retained only
as diagnostics and never counted as separate hypotheses.

## 9. Ranking Label Contract

- Label:
  `rrl1_7e43d5d302e21f8c5c854a00c8dd53972bbf7ae3d8df29e1d345afc2d35b6ce5`.
- Source: `technical_return_1d`.
- Grouping: each training date independently.
- Relevance: deterministic cross-sectional quintiles `0..4`.
- Bin count and thresholds were frozen before training and never selected
  from Discovery or rolling results.

## 10. LambdaRank Configuration

- Spec:
  `rms1_d448918c61b4e59aec64cf03c6e87a95e59e530cdd70ed7910cf245ca26aeb6c`.
- Objective/metric: `lambdarank` / `ndcg`, evaluation at 20.
- Learning rate/leaves/min leaf: `0.05/31/50`.
- Feature/bagging fraction/frequency: `0.8/0.8/5`.
- Boosting rounds: 200; early stopping: off.
- Threads: 1; deterministic: true.
- Seeds: `20260701`, `20260702`, `20260703`.
- Final score: equal-weight three-seed mean.
- Hyperparameter optimization and best-seed selection: zero.

## 11. Ranking Model Lane

Only the frozen `expanded_technical_space` and
`combined_decorrelated_technical` bundles were admitted. Bundle construction
reuses R2-008/R2-009 rules. Both passed the 2019--2021 Discovery Gate and
entered Lock V2; no third objective, label, model or bundle was introduced.

## 12. Discovery Results

- Agent calls/proposals/admissions/rejections: `18/54/15/39`.
- Rejection codes: 30 semantic mismatch, five Dataset-kind mismatch, two
  unused parameters and two duplicate structure.
- Residual candidates passing Discovery: 0/15.
- Residual failures: turnover 15, concentration 13, independence 4.
- Fixed ranking hypotheses passing Discovery: 2/2.
- Local rescue trials: 1.

The Discovery gate was not changed after observing any result.

## 13. Candidate Batch Lock

- Lock:
  `rbcbl2_d324121a5e2d5803d230175af18f8e435f03f34da43765971f229d6383256935`.
- Members/order: Ranking-C
  `combined_decorrelated_technical` first; Ranking-B
  `expanded_technical_space` second.
- Candidate count: 2.
- Agent/planner closed: true/true.
- Rolling reads before publication: 0.
- New rounds after Lock: 0.
- Formula/model, bundle, relevance Label, seeds, orientation, primary
  statistic and strategy are immutable.

## 14. Rolling Window Results

Both locked ranking candidates completed all 18/18 windows; 36 child result
Artifacts exist and no object stopped early.

Ranking-C:

- positive-primary rate `0.611111`;
- primary median `0.003200872`;
- worst-20% primary mean `-0.028646863`;
- CSI300-excess positive rate `0.444444`;
- excess median `-0.000887322`;
- turnover median `3.820553`;
- concentration median `0.155796`.

Ranking-B:

- positive-primary rate `0.555556`;
- primary median `0.001486062`;
- worst-20% primary mean `-0.025458457`;
- CSI300-excess positive rate `0.333333`;
- excess median `-0.009382601`;
- turnover median `3.844562`;
- concentration median `0.159167`.

## 15. Raw-vs-Residual Comparison

No residual DSL object passed Discovery, so no residual object was permitted
into Lock V2 and no raw-versus-residual rolling comparison was produced. This
is a valid absence, not a missing Artifact: raw scores were diagnostic-only
and Discovery failures were not bypassed.

## 16. Ranking Diagnostics

Ranking-C median NDCG@20 was `0.404513906` versus random
`0.346666667`; median Top20-universe spread was `0.000527141`.
Ranking-B median NDCG@20 was `0.400524693` versus random
`0.346666667`; median Top20-universe spread was `0.000524282`.

Both satisfy the NDCG-above-random gate, but NDCG did not translate into the
required cross-window RankIC tail or CSI300 excess consistency.

## 17. Window Consistency

- Window count per locked object: 18/18.
- Candidate/window evaluations: 36/36.
- Configuration mutations: 0.
- Early stops: 0.
- Pre-window training used only dates before each window.
- Agent, Planner and Failure Memory visibility for window results: false.

## 18. Search Exposure

- Search Exposure:
  `rbse1_e9627d04521584ab36579ffddef9b1abfef90d4a76f41e6ba95c889b5fdb8027`.
- Submission Ledger:
  `rbsl1_ce65070f1277c1a574f4bc3ba83176af6e79b5f1de9d89c366600e7b8fe05ae9`.
- Historical/current/project cumulative Agent calls: `18/18/36`.
- Current proposals/admissions/local rescue/model hypotheses:
  `54/15/1/2`.
- R3-001/current/project rolling submissions: `2/2/4`.
- R3-001 metrics included in Agent-visible exposure: false.

## 19. Multiple-testing Control

- Artifact:
  `remt1_404083e21e3b4955a87f9d133dc7f6ea8130f135fd15d9d1253e98e229c763e6`.
- Method: one global Benjamini-Hochberg family.
- FDR: q=10%; hypothesis count: 2.
- Ranking-C mean/t/p: `-0.001899550/-0.449715/0.670701`.
- Ranking-B mean/t/p: `-0.000865224/-0.210143/0.581973`.
- Both adjusted q-values: `0.670701349`.
- Passed hypotheses: 0.

## 20. Failures

Both ranking objects failed primary positive-window rate, primary worst-20%
mean, CSI300-excess positive-window rate and excess median. Residual candidates
failed before Lock as reported in section 12. Failures were written only to
terminal evidence and were not returned to the same-Batch Agent, Planner or
Failure Memory.

## 21. Survivors

Survivor count/writes: `0/0`. No gate was lowered, no budget was increased,
and no locked object was retuned after rolling evaluation.

## 22. Registry

Registry writes: 0. No failed residual or ranking object was registered,
approved, activated, promoted or represented as production-eligible.

## 23. New Fresh Locks

Fresh Lock writes: 0 because no object survived both the cross-window gate and
global BH. The no-backfill contract remains conservative and uninvoked.

## 24. Existing Fresh Isolation

Candidate B/C, their Fresh Locks, Cohort
`mfcc1_faab1ee6f07fe1ce46bb13ab8403e104433c5781058d3e8c6720e6ffd7bde6dc`,
Fresh Heartbeat, LaunchAgent and Runtime Deployment were unchanged. Their
metrics were not read by Agent, Discovery, Lock, rolling evaluation or report
comparison.

## 25. Research Efficiency

- Agent calls: 18.
- Model training calls: 114 (six Discovery fits and 108 rolling fits).
- Qlib calls: 54 (18 residual Discovery, two ranking Discovery and 36 rolling,
  less reused cached formal executions as counted by the runtime).
- Rolling submissions per Survivor: undefined because Survivor count is zero.
- New Artifacts/Blobs in the terminal Report runtime counters: `60/135`.

The fixed ranking lane consumed the full all-window evidence cost; the
residual lane avoided rolling cost by enforcing Discovery admission.

## 26. Batch Final Status

`completed_no_survivor`

Evidence semantics: `historical_rolling_evaluation`. Real Fresh validation:
false. Automatic Batch 003: false.

## 27. Mainline Blocked

`false`

Zero Survivor is a legal research result and does not imply an engine or data
failure.

## 28. Artifact Store

- Terminal Report:
  `rbrr1_c83019c48ad1edcfcd3fc68bb4eb829db3e78ca4144291ff43bd4ac8a5f3abdb`.
- Integrity: healthy.
- Missing: 0.
- Unreferenced: 0.
- Eight new/extended Artifact kinds are registered and validated.

## 29. Cold Recovery

`validate_batch` recovers 47 Batch artifacts: contracts, Window Set, Lock, two
aggregate results, all 36 child window results, Multiple Testing, Search
Exposure, Submission Ledger and terminal Report. Evidence gaps are zero and
Store integrity remains healthy.

## 30. Resume Test

A terminal `run-next-cross-sectional-alpha-batch` returned
`exact_existing=true`, recovered 47 artifacts and reported zero Agent, model,
Qlib, Tushare, network, candidate, Fresh, Registry, Promotion, Artifact and
Blob writes.

## 31. Exact Replay

Supervisor exact replay returned zero calls and writes across every required
counter, with zero evidence gaps and healthy Store integrity. No research
object or runtime state changed.

## 32. Files Added

- `backend/services/engine/cross_sectional_alpha_discovery/`: package,
  contracts, residualization, ranking and engine.
- `backend/services/tests/test_cross_sectional_alpha_discovery.py`.
- `docs/quantmind2/architecture/CROSS_SECTIONAL_RANKING_AND_STYLE_RESIDUAL_ALPHA_V1.md`.
- This Implementation Report and Manifest.

## 33. Files Modified

- Artifact kind, ID-prefix and schema-validator registries.
- Autonomous Research Supervisor export/orchestrator and CLI.
- Context Bootstrap current-task assertion.
- Project Memory Current State, Handoff, Component Catalog and Roadmap in
  human- and machine-readable forms.

No dependency, lockfile, runtime deployment, LaunchAgent, Fresh Cohort, market
authority, production configuration or existing research Artifact changed.

## 34. Tests Executed

- New targeted suite: 17 passed with `--no-cov`.
- Supervisor, R3-001, Feature Factory, multi-horizon and Artifact Store
  regression: 106 passed; two pre-existing real-research import tests failed
  only because their `/private/tmp/qm2-p0-006-validation/.../manifest.json`
  fixture no longer exists.
- Formal Batch, cold validation, terminal resume and exact replay: passed.
- Context Bootstrap, JSON parse, `py_compile`, Git inventory,
  `git diff --check` and secret scan: final results are recorded in the
  Manifest.

The first narrow run had 17 passing tests but exited nonzero only because its
4.41% repository-wide coverage was below the global 5% threshold. The
functional rerun used the supported `--no-cov`; no behavioral test was hidden.

## 35. Expected vs Actual

- Maximum Agent calls/proposals were 18/54; actual 18/54.
- Maximum admissions were 30; actual 15.
- Expected two fixed ranking hypotheses; actual two.
- Expected every locked object to complete 18 windows; actual 36/36.
- Maximum Qlib was 260; actual 54.
- Zero Survivor was explicitly legal; actual zero.
- Expected no Batch 003, Promotion or existing Fresh mutation; all remained
  zero/unchanged.

## 36. Implementation Run

- Run ID: `QM2-R3-002-20260725T140810Z-4cc7ca5`.
- Base commit: `4cc7ca5afbece6bd23fec8eed27b943592830f74`.
- Manifest: v2.
- Pre-commit status: `completed_uncommitted`.
- Suggested commit: `feat(qm2): research ranking and residualized alpha`.
- Commit policy: one commit, no amend/reset/rebase/push.

## 37. Project Memory Updates

Current State, Handoff, Component Catalog and Roadmap identify the new
component, immutable Batch IDs, fixed controls/ranking boundaries, 15
Discovery failures, two complete rolling submissions, zero-Survivor result,
historical evidence semantics, 47-artifact recovery and exact replay.

## 38. Known Limitations

- No residual DSL object passed Discovery, so there is no locked
  raw-versus-residual rolling comparison.
- Both ranking models improved NDCG@20 over random but failed RankIC tail and
  CSI300-excess consistency; neither is a supported Alpha Survivor.
- The reused formal Qlib path may emit non-blocking optional PostgreSQL/COS
  resolution warnings before successful local execution.
- The two legacy `test_artifact_store_real_research.py` cases depend on a
  deleted `/private/tmp` QM2-P0-006 fixture and cannot currently run green.
- The formal runtime needs its already-versioned OpenMP path for LightGBM; no
  dependency installation is needed.
- Historical rolling evidence is not real Fresh evidence.

## 39. Final Research Conclusion

Fixed daily style residualization did not rescue any Agent-generated technical
DSL structure through the unchanged Discovery Gate. Fixed LambdaRank produced
NDCG@20 above random for both authorized bundles, but neither converted that
ranking fit into stable cross-window RankIC tails or CSI300 excess, and both
failed global FDR. The evidence supports zero Survivor, not retuning, control
search, gate relaxation or automatic Batch 003.

## 40. Git State After

Before commit the workspace contains only task-scoped source, tests,
architecture, Project Memory and this Implementation Run. No dependency or
lockfile changed. Post-commit Planner evidence and the clean worktree are
verified after the single containing commit.
