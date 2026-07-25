# Current Implementation State

## Fresh runtime cleanup and diagnostic hardening (QM2-R2-012)

- The deployed heartbeat entrypoint no longer replaces its trap-owning shell.
  It propagates the heartbeat exit code and cleans its exact per-run temporary
  directory on success, failure, HUP, INT and TERM.
- Runtime temporary directories use validated run IDs, owner metadata and
  user-only permissions. Bounded stale cleanup requires a dead owner, age
  greater than 24 hours and no live Scheduler-lock reference.
- LaunchAgent diagnostics now cross a fixed field whitelist. Raw launchctl
  output is parsed only in memory; credential diagnostics expose only a
  boolean. A fail-closed redaction guard covers runtime stdout, stderr,
  status/history and notification inputs without storing secret hashes.
- Five operational Artifact kinds record the cleanup defect, whitelist,
  redaction guard, historical session exposure and hardening status. The
  historical event remains acknowledged; no claim is made that platform
  session history was deleted and credential rotation remains user-governed.
- Immutable post-commit App cutover is a deployment-locked operation with
  old-pointer/config/plist recovery. It reuses the existing environment and
  canonical Store; dynamic activation truth remains authoritative only in the
  external Deployment and Hardening Status records.
- Current task: `QM2-R2-012`.
- Latest Implementation Run:
  `QM2-R2-012-20260725T063951Z-4a12e40`.

## Immutable Fresh runtime deployment (QM2-R2-011)

- `quantmind2.fresh_runtime_deployment` versions committed Git source and the
  validated Python/Native environment below
  `~/Library/Application Support/QuantMind`; both current pointers switch
  atomically and immutable snapshots are retained.
- Runtime configuration, entrypoint, logs, locks, checkpoints, per-run
  temporary paths, deployment history and the LaunchAgent require no path
  below Documents, Desktop, Downloads, Mobile Documents or iCloud.
- The existing Store at `~/.quantmind2/artifact-store/v1` is already external
  and remains the only canonical writable Store; state relocation is false.
- Five immutable runtime Artifact kinds capture path audit, Git app snapshot,
  environment snapshot, state decision and deployment status. The existing
  Scheduler and Supervisor remain the only executors.
- Formal host activation occurs only after the containing commit. Dynamic host
  truth is authoritative in
  `~/Library/Application Support/QuantMind/deployments/current-deployment.json`
  and the latest `fresh_runtime_deployment_status`, never loaded state alone.

## Multi-Horizon Label Alignment Cycle (QM2-R2-008)

- Current task: `QM2-R2-008`.
- Label Family `trlf1_7370ec7d...04561c` freezes L1/L5/L10 together
  before training. All use adjusted prices, official sessions, Fixed-100
  lifecycle, no replacement/fill, and same-date 5-MAD plus population
  z-score. Quality coverage is 99.93%, 99.65%, and 99.34%; all quality/PIT
  gates pass.
- The executable audit confirms configured metadata does not drive the
  training code, which executes
  `adjusted_close[T+H]/adjusted_open[T+1]-1`. The old Label Artifact and
  production Label remain unchanged.
- The frozen 3 Label x 3 Bundle x 4 Fold x 3 Seed matrix completed 108
  LightGBM fits, 36 ensemble predictions, and 36 formal Qlib runs. Feature,
  hyperparameter, strategy, combined-optimization, network, Tushare,
  Registry, and Promotion writes are zero.
- Global nine-hypothesis BH at q=10% admits two L1 candidates: expanded
  technical space and combined de-correlated technical. L5 and L10 produce
  no survivor. Classification is `one_day_label_supported`; this does not
  replace or promote the production Label.
- Cycle 004 is `completed_with_label_aligned_candidate`. Two no-backfill
  Fresh Locks exist, but no post-2026-07-23 official data is available, so
  no Fresh result, Registry write, or Promotion exists. Cycle 005 was not
  created.
- Terminal Report: `mhlrr1_53bae8de...b8550f`; global test:
  `mhmt1_9ba1acf8...c7ddc`. Store integrity is healthy with Missing 0 and
  Unreferenced 0; cold validation, resume, Supervisor replay, and exact
  replay are zero-call.
- Latest Implementation Run:
  `QM2-R2-008-20260724T155317Z-86b2496`.

## Fixed-configuration Weak-Alpha Model Cycle (QM2-R2-007)

- The existing QuantMind LightGBM and formal Tushare `model_label` chain now
  have a separate retrospective model-research boundary. No model score is
  represented as a DSL Factor or Terminal Feature.
- Model Spec `fcms1_27c710...7ad94` freezes one configuration, three seeds,
  disabled early stopping, equal-weight seed aggregation and the unchanged
  TopK20/drop5/ten-session/equal-weight/CSI300 strategy before Fold 1.
- Bundle A freezes 36 pre-R2-006 technical Features. Bundle B freezes 20
  R2-006 Features plus six primitives. Bundle C applies the same train-only,
  label-free quality and `|Spearman| < 0.95` rule in every Fold and retained
  49--50 Features.
- All three Bundles completed four purged expanding outer Folds for 2021--2024
  and contaminated report-only runs for 2025 and 2026H1: 54 fixed-seed model
  fits, 18 prediction materializations and 18 real Qlib calls. Agent,
  hyperparameter/strategy/combined optimization, Tushare/network, Registry
  and Promotion calls were zero.
- None passed both the frozen retrospective gate and global BH FDR. Combined
  RankIC means were A `0.000643`, B `-0.004613`, C `-0.001247`; all adjusted
  q-values were `0.917134`. Model Candidates, Fresh Locks and Fresh Cohorts
  are zero.
- Cycle 003 is `completed_no_model_candidate`. Both single-Factor and bounded
  model-aggregation spaces are exhausted, so Supervisor status is
  `global_authorized_technical_research_space_exhausted`; Cycle 004 was not
  created.
- Store integrity is healthy with Missing 0 and Unreferenced 0. Cold
  validation, terminal resume, Supervisor replay and exact replay return zero
  external/computation/mutation counters.
- Current task: `QM2-R2-007`.

## Technical Research Space Cycle v2 (QM2-R2-006)

- Factor DSL now has six accepted PIT rolling operators: sum, correlation,
  median, fixed quantile, deterministic skew and most-recent-tie argmax age.
  Seven wider operators remain explicitly rejected.
- Primitive Catalog `tpc2_b9f611...7208` materializes six research-only
  primitives from the existing Tushare authority with no new market request.
- Factory `technical_feature_factory_002` used 10 Agent calls, emitted 26
  proposals and admitted/materialized 20 unlabeled novel research features.
  Frozen Catalog v3 is `tfc3_b903c8...23aea`.
- Supervisor Cycle 002 `arc2_78b9b6...3266` then ran 18 Alpha Agent rounds
  and 68 real Qlib calls under unchanged archetype, default-first, locked
  validation and global FDR rules.
- No object survived as a Retrospective Candidate, so no Fresh Lock, Cohort,
  incremental market request, Registry write or Promotion occurred. Status is
  `waiting_for_fresh_data_or_novel_space`; global stop is not yet active
  because the Feature dimension was non-empty.
- Store integrity, cold recovery, terminal resume and exact replay pass; replay
  has zero Agent, Qlib, Tushare, network, artifact and domain writes.
- Current task: `QM2-R2-006`.
- Latest Implementation Run:
  `QM2-R2-006-20260724T130920Z-e57696b`.

## Autonomous Research Supervisor v1 (QM2-R2-005)

- All project-visible market evidence through 2026-07-23 is now classified
  `retrospective_research_only`. Exposure Ledger
  `peel1_f96c3595...a7c7eb` backfills 16 formal R1/R2 Runs.
- Supervisor Spec `arsv1_1d07cf5c...abd14e` freezes Cycle, Agent, Proposal,
  Admission, Qlib, Candidate, Cohort and active-Fresh budgets. Research Queue
  is `arq1_1982ce71...29e71f`.
- The first automatic Cycle `arc1_58325bd9...cb2c8b` reused the existing
  Feature Factory and Alpha Program implementation. It made zero new
  Agent/Qlib calls and produced zero Retrospective Candidates.
- With no Candidate there is no Supervisor Fresh Lock, Cohort, observation or
  incremental request. Status is `waiting_for_fresh_data_or_novel_space`;
  R1-010 remains statistically isolated.
- Report `arsr1_3cc6becd...91666a` records autonomous execution operational,
  historical robust Alpha Survivor none, Registry/Promotion writes zero and
  healthy Store integrity. Cold recovery, resume and replay are zero-call.
- Current task: `QM2-R2-005`.

## Autonomous Multi-Campaign Research Program v1 (QM2-R2-003)

- `quantmind2.autonomous_factor_program` orchestrates three pre-registered,
  performance-isolated research Lanes over a shared structural/signal novelty
  boundary and global budget. Adaptive research is physically limited to
  2019–2020; 2021–2024 opens only after all Lane planners/memories and the
  immutable Union Shortlist are frozen.
- Formal Program `afrp1_5ac295d3...a150b0` completed 15 automatic Rounds:
  15 Agent calls, 26 Proposals, 23 Admissions, 20 local-rescue Trials and 61
  adaptive Qlib calls. All three Lanes completed five Rounds. Improvement stop
  occurred only after 12-Round/12-call, six-Family, three-Lane and
  16-Admission minimums were exceeded.
- Recovery and trend Lanes produced no eligible shortlist. Trading
  confirmation produced one object, locked globally by
  `apusl1_ede68a49...2901c` before any validation read.
- The single object completed unchanged 2021–2024 validation. It failed
  median annual RankIC (0.002148 < 0.003) and BH FDR
  (adjusted q-value 0.136976 > 0.10). Final state is
  `completed_no_validation_survivor`; Registry, 2025/2026H1 report, Candidate
  and Fresh-Lock writes are zero.
- Report `afpr1_d7368ad6...e4f508`, cold validation and exact replay have zero
  evidence gaps. Store integrity is healthy with Missing 0 and Unreferenced
  0; replay has zero Agent/Qlib/optimization/network/mutation/new-object
  counts.
- Current task: `QM2-R2-003`. No successor task is authorized by this
  implementation contract.

## Locked-Holdout Autonomous Campaign v2 (QM2-R2-002)

- Campaign v2 physically restricts Agent, Planner, Failure Memory, parameter
  selection and shortlist ranking to 2019--2022. The 2023--2024 matrix is
  opened once only after rounds stop, Memory freezes and immutable Shortlist
  Lock `acsl1_3746253e...f0a4` is published with zero prior holdout reads.
- Canonical Spec `afc2_f3ba310a...f17cb2` ran four autonomous rounds: four
  Agent calls, 12 proposals, eight admissions, six local-rescue Trials and 17
  Discovery Qlib calls. The stop reason was
  `development_improvement_exhausted`; manual intervention/planning remained
  zero.
- One Discovery object reached Holdout. It passed all frozen gates except
  positive RankIC in both years (2023 0.009854; 2024 -0.002376), so terminal
  status is `completed_no_holdout_survivor`. Registry writes, candidate locks,
  contaminated reports and Fresh Locks are all zero.
- Report `afcr2_bbeee1e...cb4b0`, cold validation and exact replay have zero
  evidence gaps. Store is healthy with Missing 0 and Unreferenced 0; replay
  makes all external, computation and mutation counts zero.
- The earlier v1 Campaign remains historically valid as autonomous execution
  but not as generalization evidence. Its three Candidates remain immutable.

## Autonomous Factor Research Campaign Orchestrator v1 (QM2-R2-001)

- `quantmind2.autonomous_factor_campaign` now composes the existing Agent,
  canonical Factor DSL, default-first/local-rescue governance, formal Qlib
  evaluator and filesystem Artifact Store into one bounded multi-round state
  machine. It does not replace those components.
- Formal Campaign Spec
  `afc1_5bae780e...a8034` completed all 12 planned rounds with
  `budget_exhausted`: 12 external Agent calls produced 26 Proposals, 20
  admitted Templates, 20 default evaluations, eight local-rescue Trials, 40
  annual evaluations and 74 formal Qlib calls.
- Three independent Candidate Locks are `research_registered`:
  `path_efficiency_acceleration`, `drawdown_distance_recovery_delta` and
  `normalized_acceleration_quality`. Five rejected objects are retained only
  in the Near-miss queue. Registry Promotion writes remain zero.
- Selection ends at 2024-12-31. The 2025 and 2026H1 results are contaminated
  report-only evidence and were not exposed to Agent Memory, Planner,
  Candidate ranking, parameter selection or early stopping. R1-010 Fresh
  Forward evidence remains completely isolated.
- Campaign Report `afcr1_e5eea677...460f4` and all Store lineage validate with
  zero evidence gaps; Store integrity is healthy, Missing 0, Unreferenced 0.
  Cold replay and terminal re-execute have a 100% cache-hit rate and make
  every external, computation, Registry, Promotion and new-object count zero.
- Current task: `QM2-R2-001`. No successor task is authorized by this
  implementation contract.

## Breadth-Gated Momentum Overlay and Fresh Forward Protocol v1 (QM2-R1-010)

- Signal D, the R1-009 `regime_specific_factor` classification, the formal
  PIT breadth builder and L1 TopK20/n_drop5/10-session protocol remain
  immutable. Gate Spec `bmgs1_4cb24dc3...aec343` consumes the formal state at
  session `t` directly because that state already represents raw breadth at
  `t-1`; a second shift is forbidden.
- Historical U/G/R mechanism paths are retrospective and contaminated. The
  final revision is `bgmhd1_48b6d03...030fec`. Conditional selection alpha is
  positive in 2021, 2022 and 2024, but negative in 2023, 2025 and 2026H1;
  history alone does not support the overlay.
- Fresh Lock `bgmfl1_80313cd9...436b60` was published before 68 bounded
  Tushare calls. Snapshot `tims1_a59e3127...9168c` has 22 exchange sessions,
  zero duplicates and zero missing adjustment factors.
- The current Fresh revision contains 20 completed return sessions, two
  10-session windows, 12 gate-on days and two gate-on rebalances. Interim
  metrics are positive, but the frozen sample gate is not met; status is
  `fresh_evidence_accumulating`, never supported or promoted.
- Observation `bgmfo1_6cdb7685...0abaf` and assessment
  `bgmfa1_22d8424e...349cd` recover with the other four new artifacts and
  immutable Signal D: seven recovered artifacts in total.
  Store integrity is healthy, Missing 0, Unreferenced 0; exact replay makes
  every prohibited call/write and new-object count zero.
- Current task: `QM2-R1-010`. No successor task is authorized here.

## Momentum Tail-Alpha and Selection-Overlay Diagnostic v1 (QM2-R1-009)

- The immutable R1-008 Signal D was decomposed into daily deciles, formal
  label RankIC, adjusted-close forward-return RankIC, tail spreads, fixed
  Top-N baskets, 2023 monthly/stock contributions, beta/style/breadth,
  stability, rank transition and T+1--T+40 decay.
- Signal D is not a stable broad monotonic or tail-only factor. Q10 beats its
  observable universe only in 2024 across the four research years; fixed
  Top20 beats CSI300 in 2021, 2023 and 2024, but not 2022, 2025 or 2026H1.
- The only jointly positive PIT breadth regime is narrow/weak: RankIC
  0.02628, Q10-Q1 0.001323 and Top20 CSI300 excess 39.05%. The formal class is
  `regime_specific_factor`; the non-executed decision is
  `retain_for_regime_specific_research`.
- Revision 2 explicitly separates immutable-label RankIC from adjusted-close
  forward-return RankIC. Diagnostic
  `mtad1_308b2628...951951` and its four child artifacts recover from Store;
  integrity is healthy, Missing 0, Unreferenced 0 and exact replay creates no
  object or external/research call.
- Agent, all Optimization classes, Qlib strategy, network/Tushare, Candidate
  Lock, Registry and Promotion counts are zero. Current task is
  `QM2-R1-009`; no successor task is authorized here.

## Low-Frequency Momentum and Turnover-Control Study v1 (QM2-R1-008)

- Four immutable, pre-registered Momentum signals were evaluated under B0
  five-session and L1 ten-session protocols using 40 formal Qlib calls.
- L1 reduced median annual turnover by 34.54% and transaction cost by 33.21%.
  Median L1 annual net return improved for all four signals, but no signal
  passed all frozen Candidate Eligibility gates.
- Candidate Locks and 2025/2026H1 reports are both zero by chronology. The
  terminal classification is `stock_selection_signal_only`: some annual
  RankIC/group or net-excess evidence remains, but standalone Alpha is not
  stable enough for registration.
- Store inventory `sai_06ee449c...28be` is healthy with 715 Artifacts and
  3,549 Blobs. Cold recovery restores 39 study objects and exact replay has
  zero Agent, Optimization, Qlib, network, new Artifact/Blob and Promotion
  calls.
- Current task: `QM2-R1-008`; no successor task is authorized here.

## Default-first Momentum Structure Search v2 (QM2-R1-007)

- R1-006 governance is now exercised by a real momentum research runtime:
  explicit Agent defaults run first, only near-gate failures enter a one-hop
  factor neighborhood, and Strategy/Combined optimization remains zero.
- Six real Agent calls produced eight evaluated DSL Proposals. Eight defaults
  plus thirteen local Trials consumed 21 formal Qlib calls. Network and
  Promotion writes are zero.
- All defaults failed the frozen development gate because turnover exceeded
  45 and neither CSI300 excess nor cross-sectional group evidence was
  positive. No local Trial rescued a structure. Thresholds, rounds and search
  scope were not expanded.
- There are no Development Locks, annual locked evaluations, Candidate Locks,
  2025 reports or 2026H1 reports. This is the frozen zero-candidate terminal
  outcome, not missing execution evidence.
- Canonical Experiment is `dfme1_e15ea299...98b6b0`; Assessment is
  `dfma1_b259450...271af4`. Cold recovery restores 40 objects; exact replay
  performs every external/computational call and new-object count at zero.
  Store integrity is healthy, Missing 0 and Unreferenced 0.
- Current task: `QM2-R1-007`; no successor task is authorized here.

## Default-first Optimization Governance v2 (QM2-R1-006)

- The corrected R1-005 business decision is now runtime policy: new research
  evaluates explicit Agent defaults first, stops when they pass, and permits
  at most a one-hop, one-parameter-at-a-time local rescue after failure.
- Factor and Strategy full searches are explicit diagnostic-only modes. They
  cannot select Candidate parameters or authorize Promotion. Combined Factor
  and Strategy parameter search is suspended and hard-fails during planning.
- New Candidate Locks require twelve optimization-governance metadata fields;
  local rescue remains `research_registered` only and needs new-time evidence
  before any later lifecycle admission.
- Four immutable policy/decision artifacts are Store-backed under decision
  `ogd1_7de0ba81...911f7f5`. Cold recovery and exact replay restore all four
  with Agent, Factor/Strategy Optimization, Qlib, network, Promotion and new
  object counts equal to zero. Store integrity is healthy.
- R1-003 Candidate Locks, R1-005 artifacts and their statuses were not changed.
- Current task: `QM2-R1-006`; no successor task is authorized here.

## Parameter Optimization Ablation Git evidence correction (QM2-R1-005F)

- The original `QM2-R1-005-20260722T052636Z-82f13f9` Run remains immutable,
  `validated=false`, `indexable=false`, with mandatory failures
  `changed_file_hashes` and `source_bundle_hash`.
- Commit `3e04743f...` proves 25 changed paths, 10 added paths and 24 business
  ChangedFiles. Exactly one committed blob differs from the pre-commit
  Manifest evidence: the parameter-ablation contract after removal of one
  trailing whitespace sequence.
- `QM2-R1-005F` records the commit-derived hashes and source-bundle identity
  as independent `GitEvidenceCorrectionV1` evidence and relates the new Run
  to the original with `corrects`. The supported Ledger interpretation is
  `completed_corrected`; the original Run is not rewritten.
- No Agent, Factor Optimization, Strategy Optimization, Qlib, network,
  Promotion, Candidate-state, research Artifact or research Blob action is
  performed. All ablation results and Framework Decision remain unchanged.
- Current task: `QM2-R1-005F`. No successor task is authorized here.

## Parameter Optimization Overfit Ablation v1 (QM2-R1-005)

- The immutable R1-003 defaults, full search spaces, two Candidate Locks and
  equal-weight ensemble were recovered from the Store. Candidate A defaults
  to `baseline_window=20`; Candidate B defaults to
  `high_distance_weight=0.5`. Both one-parameter local spaces equal their
  three-point full spaces, so F1 and F2 are intentionally identical.
- F0/F1/F2, S0/S1/S2 and O0/O1/O2 completed across four isolated walk-forward
  Folds and retrospective 2025/2026H1 reports. The study produced 1,470 unique
  formal Qlib results with no rejected result, 162 Trial-rank records and 108
  Winner's-Curse records.
- Candidate B is `likely_overfit` under both factor and strategy optimization.
  Candidate A and B are both `likely_overfit` under light and full combined
  optimization; ensemble classifications are inconclusive. Combined search
  raises research excess while lowering average later excess for A and B.
- The advisory decisions are `default_first_optimize_only_on_failure` for
  Factor and Strategy parameters and `suspend_parameter_optimization` for
  combined optimization. `apply_automatically=false`; both locks remain
  `research_registered` and no Factor, Agent, network or Promotion action was
  produced.
- Contract revision 2 corrects a revision 1 list-order-only F1/F2 equality
  summary without rewriting the immutable revision 1 artifacts. The final six
  revision 2 artifacts cold-recover; exact replay performs zero Qlib,
  Optimization, Agent, network, Store-object or Promotion calls. Store
  integrity is healthy with Missing 0 and Unreferenced 0.
- Current task: `QM2-R1-005`. No successor task is authorized here.

## Momentum Signal Semantic Audit and Alpha Decomposition v1 (QM2-R1-004)

- Candidate A is a 60--10 momentum deviation/surprise signal, not a
  risk-adjusted signal. Candidate B's negative distance-to-high term rewards
  stocks farther below their 60-session high, so it is momentum plus
  mean-reversion/anti-crowding rather than breakout confirmation.
- 2025 mean RankIC remains positive at 0.00747/0.00482 for A/B, while 2026H1
  turns negative at -0.00438/-0.00866. The ensemble is 0.00781 in 2025 and
  -0.01110 in 2026H1. Later periods remain retrospective reports only.
- Formal Qlib diagnostics show costs are not the primary failure. 2025 retains
  positive absolute returns but trails CSI300; 2026H1 loss is dominated by
  negative stock-selection residual. The candidates have low signal overlap
  but strongly correlated long-only returns through shared market/style
  exposure.
- Five immutable diagnostic artifacts are Store-backed and cold-recoverable.
  Exact replay restores all five with every external/computational call count
  and every new-object count equal to zero; Store integrity is healthy.
- The research decision is `continue_as_stock_selection_overlay_only`. Both
  Candidate Locks remain `research_registered`; no new Factor, parameter
  search or Promotion was produced.
- Current task: `QM2-R1-004`. This task authorizes no automatic successor.

## Replayable Skip-Recent Momentum Deep Dive v1 (QM2-R1-003)

- Canonical Experiment `srme1_072b0d1a...d1ab3c` implements the Research
  Artifact Completeness v1 chain from exact Agent response bytes through
  Proposal, DSL/AST Template, fold-specific Trial values, pre-evaluation Fold
  locks, Eligibility, Candidate locks, reports and assessment.
- Six skip-recent subfamilies were explored with nine completed real Agent
  calls, 15 candidates, 50 unique Trials and 178 formal Qlib calls. Two
  independently eligible structures are `research_registered`; the two-family
  ensemble gate also passed. No Promotion or production state was written.
- Both locked candidates and their ensemble underperformed CSI300 in the
  contaminated 2025 and 2026H1 retrospective reports. These are not Fresh
  Validation, frozen evidence or predictive claims.
- Exact replay recovered 368 artifacts from an empty cache with Agent,
  Optimization, Qlib, network, new-artifact and Promotion counts all zero.
  Store integrity is healthy, Missing 0 and Unreferenced 0.
- Current task: `QM2-R1-003`. No next research task is authorized by this
  implementation task.

## Momentum Factor Family Iteration v1 (QM2-R1-002)

- Current task: `QM2-R1-002`; the earlier PIT Fundamental task with this ID is
  cancelled and produced no implementation evidence.
- Canonical experiment revision 2 is
  `mfi1_87177b7c06420e65159d3f5bdafee8149cdb3290c32f08712cd73e59a4e19dee`.
  It supersedes immutable revision 1
  `mfi1_cb0953420f15e3bf162e84be1cac7cd0c0794064197e65c11d430d24a985cf32`.
- The final run computed 36 quality-passed features in nine families and
  explored eight families through five real Agent rounds, 13 admitted
  Templates, 37 Factor Trials and 92 formal Qlib calls.
- One candidate passed standalone eligibility, but the final lock requires at
  least two eligible families. No Candidate Lock, later-period candidate
  report, ensemble, Registry write or Promotion was produced.
- Store integrity is healthy with Missing 0 and Unreferenced 0. Cold recovery
  validates nine artifacts and exact replay performs zero Agent, Optimization,
  Qlib, network, new-artifact or new-blob calls.
- Formal conclusion: the current Fixed-100 daily momentum space has not found
  sufficiently stable Alpha. No next research task is authorized here.

## Expanded-factor Git evidence correction (QM2-R1-001F)

- `QM2-R1-001` completed its business research loop, but its immutable
  Implementation Manifest omitted its own path from both Git path inventories.
  The original Run therefore remains historically `partial_committed`.
- `QM2-R1-001F` records the exact 26 changed paths and 13 added paths from
  commit `4de8b1e8...` as independent `GitEvidenceCorrectionV1` evidence and
  links the new Run to the original with `corrects`. The Ledger-supported
  resolved state is corrected completion; the original Run is not rewritten.
- Research evidence is unchanged: assessment `mixed`, one
  `research_registered` factor, negative 2025 and 2026H1 continuation, and
  zero Promotion candidates. Agent, Factor Optimization, Qlib, Tushare,
  network and Promotion calls in this correction task are all zero.
- Current task: `QM2-R1-001F`. The only next task is
  `QM2-R1-002 — PIT Fundamental and Regime-aware Factor Iteration v1`.

## Expanded-feature Agent factor iteration v2 (QM2-R1-001)

- Complete definitions of the three existing Factors were recovered before
  any new Agent call. Feature Catalog v2 selected 24 of 26 PIT-safe daily
  price/volume features and materialized 180,241 Fixed-100 rows from the
  immutable Tushare normalized-bars authority without a network or legacy-data
  read. All selected features pass the frozen quality gates.
- Six external `openai_codex_cli` / `gpt-5.6-terra` rounds completed with 12
  admitted Templates, 38 factor-only parameter Trials and 50 formal Qlib
  calls. Every Template retained four independently parameter-locked
  2021--2024 evaluation Folds under fixed TopK20/n_drop5/five-session strategy.
- One Candidate passed: `fi_e2dd6057...d8576f`, combining smoothed
  `amount_ratio_5` with absolute change in `price_vs_ma_60`. It has 3/4
  positive RankIC Folds, 4/4 positive CSI300-excess Folds, median/worst RankIC
  0.001440/-0.004723, median/worst excess 16.88%/9.91%, turnover 35.317 and
  maximum old-factor correlation 0.276.
- Candidate Lock `afcl_27fb695b...ba51e` and Experiment
  `afi2_78fe3138...7fcf` are contract revision 2 and research-only. They
  supersede immutable preliminary records solely to add readable canonical
  DSL; no Agent, Optimization or Qlib call was repeated.
- Retrospective 2025 and 2026H1 CSI300 excess is -10.91 and -20.84 percentage
  points. The assessment is `mixed`, not Fresh Validation, Promotion or
  production evidence.
- Store is healthy with Missing 0 and Unreferenced 0. All 15 original and
  superseding v2 Artifacts cold-recover; exact replay performs no external
  calls and creates no objects.
- Current task: `QM2-R1-001`. No successor is authorized by this task.

## Strategy Parameter Optimization v1 (QM2-P0-017)

- A strict Strategy Optimization domain searches only TopK `[10,20,30]`,
  n_drop `[0,5,10]` and Qlib trade-date rebalance intervals `[1,5,10]`.
  Invalid `topk=10,n_drop=10` combinations are rejected before Trial creation;
  four locked Unified Signals produced exactly 96 deterministic Trials.
- All 96 Trials completed through `QlibBacktestService →
  RedisRecordingStrategy → SimulatorExecutor → CnExchange`. Selection used
  only six annual 2019--2024 CSI300-relative results. Four immutable research
  Candidate Locks were created before 2025 and 2026H1 reporting.
- Candidate parameters are respectively `20/0/5`, `20/5/5`, `30/5/10` and
  `20/5/10` in Study signal order. All four beat CSI300 cumulatively during
  contaminated 2019--2024 research, but all four underperformed CSI300 in
  both retrospective 2025 and 2026H1. Every candidate is parameter-unstable.
- Study `sos_e504d537...10687`, Result `sor_2c7803f0...b8628` and Registry
  `srr_58f3e455...023d13` remain research-only. Approved/active counts are
  zero; no Agent, Factor Optimization or Promotion call occurred.
- Store Inventory `sai_a0dbf127...cf5f5` is healthy at 270 artifacts / 2,468
  blobs, Missing 0 and Unreferenced 0. Cold recovery and exact replay pass
  with Qlib calls 0 and no new Store objects.
- Current task: `QM2-P0-017`. The only next task is `QM2-P0-018 — Strategy
  Risk and Validation Gate v1`.

## Unified Signal and Strategy Layer v1 (QM2-P0-016)

- Unified Signal v1 now separates locked Factor inputs, transformation,
  combination, quality, materialization and immutable identity. Four signals
  were published from three research-diagnostic Tushare candidates. The
  equal-weight signal `usa_4c824a58...9fab0` is exactly equal to the historical
  reference across 180,241 interval keys, including the NaN mask and all
  180,231 finite cells.
- Strategy Layer v1 fixes TopK 20, n_drop 5, five-session weekly rebalance,
  equal target weights, CSI300 and the existing formal Qlib execution chain.
  Four Portfolio Targets and four Strategy Results were published. The final
  Strategy Registry is `srr_a2d226d4...ea503`, with four
  `backtest_completed`, zero approved and zero active entries.
- Equal weight returned 82.45%, Sharpe 0.474 and maximum drawdown -19.07%.
  It improves Sharpe and drawdown over every individual Factor but does not
  exceed the best single Factor's 91.90% total return. CSI300 excess is 16.79%.
- Absolute and CSI300-relative strategy evidence is canonical. Fixed-100
  2025/full-period comparison remains noncanonical and unusable for decisions.
  The historical Qlib result exposes actual positions but not formal pre-trade
  target weights, so target-to-actual-target equality is not verifiable and is
  not fabricated.
- Store Inventory is healthy with Missing 0 and Unreferenced 0. Final cold
  recovery verifies 13 current artifacts; exact replay creates zero artifacts,
  zero blobs and makes zero Qlib, Agent, Optimization or Promotion calls.
- Historical task: `QM2-P0-016`; its fixed baseline artifacts remain immutable.
  Its then-next task `QM2-P0-017` is now completed as recorded above.

## Tushare corporate-action evidence audit (QM2-P0-015H)

- The environment-only Tushare credential was used for 19 redacted requests.
  Thirteen requests were available: `stock_basic`, `daily`, `namechange`,
  `suspend_d`, `share_float`, `dividend` and `major_news` metadata. Issuer
  announcement endpoint `anns_d` and candidate structured `merge`/`merger`
  endpoints were unavailable for both target securities.
- Raw Snapshot `tsca_raw_c8c04e...91b13` preserves 409 event/status rows, 800
  news-metadata rows, request schemas, response hashes and safe capability
  outcomes. It contains no credential, account, physical path or request time.
- Event Set `scae_a90b3726...abd1f` confirms last tradable/effective dates
  2025-02-05/2025-03-04 for `SH600837` and 2025-08-12/2025-09-05 for
  `SH601989`. Both remain `delisting` events with null settlement date, cash,
  replacement symbol, conversion ratio and residual cash; completeness is
  `evidence_missing`.
- `FixedUniverseBenchmarkContractV2` is frozen as investable, self-financing,
  equal-weight semantics under `fubc_e1885a79...513e4`. Locked membership
  remains 100, replacement is forbidden, settlement cash stays in cash and a
  conversion asset does not become a new locked member.
- The canonical-revision gate hard-failed with
  `SECURITY_TERMINATION_SETTLEMENT_UNRESOLVED`. No benchmark revision,
  corrected return, relative metric, Qlib call, Agent call, Optimization or
  Promotion was produced. All Fixed-100 2025/full-period metrics remain
  noncanonical; strategy NAV, CSI300, 2019--2024 and 2026H1 remain unchanged.
- Store Inventory `sai_ff1a263a...faee2` is healthy at 49 artifacts / 1,607
  blobs, Missing 0 and Unreferenced 0. Cold recovery and exact replay pass with
  zero Tushare, Qlib and Agent calls and zero new objects.
- Current task: `QM2-P0-015H`; status is `blocked` with reason
  `TUSHARE_CORPORATE_ACTION_EVIDENCE_INSUFFICIENT`. No successor is authorized.

## Security termination audit (QM2-P0-015G)

- `SecurityTerminationPolicyV1` now defines delisting, cash settlement, stock
  conversion, merger exchange, write-off and unknown-termination evidence. It
  forbids implicit last-price sale, stale valuation, zero return, cash or
  conversion assumptions. A position crossing the last tradable date without
  governed settlement evidence is `SECURITY_TERMINATION_SETTLEMENT_UNRESOLVED`.
- Formal 2025 Qlib reruns reconstructed positions and executed orders for the
  three locked candidates and equal-weight combination. Neither strategy path
  ever held `600837.SH`. The combination and Candidate 1 held `601989.SH` but
  fully exited on 2025-07-11 and 2025-04-21, before its 2025-08-12 last market
  date. Candidates 2 and 3 had no exposure. All strategy absolute and CSI300-
  relative 2025 metrics preserve exact parity and remain canonical.
- The daily observable-member Fixed-100 benchmark had unit-notional weights
  1/100 on `600837.SH` at 2025-02-05 and 1/98 on `601989.SH` at 2025-08-12,
  then removed each missing member without a governed cash, conversion or
  write-off event. Its 2025 return, all Fixed-100-relative 2025 metrics and the
  corresponding full-period metrics are noncanonical. No corrected return or
  maximum impact was fabricated.
- Audit `htf_4a0762a5...ba6c3f` is immutable in the Store. It contains policy,
  symbol events, strategy and benchmark exposure, a position timeline, impact
  and canonicality. Store is healthy at 46 artifacts / 1,597 blobs; cold
  recovery and exact replay pass with zero Qlib calls and zero new objects.
- 2019--2024 and 2026H1 remain unchanged and canonical. No Agent,
  Optimization, candidate, parameter, universe or Promotion state changed.
- Current task: `QM2-P0-015G`; result is `partial` because a governed Corporate
  Action Provider is still required to resolve the historical Fixed-100
  benchmark settlement. No successor is authorized by this task.

## Fixed-100 lifecycle follow-up (QM2-P0-015F)

- Fixed membership remains exactly 100. `600837.SH` (海通证券(退), status D,
  delisted 2025-03-04) and `601989.SH` (中国重工(退), status D, delisted
  2025-09-05) were proven from the immutable Tushare stock-basic artifact to
  be `DELISTED_BEFORE_PERIOD` for 2026H1. Their last market rows are
  2025-02-05 and 2025-08-12; this is not source loss, symbol mapping failure,
  or Qlib-view omission.
- `FixedUniverseLifecyclePolicyV1` separates locked, active, observable,
  tradable and signal-eligible sets. Capacity is frozen before evaluation as
  TopK 20 + n_drop 5 = 25; the observed daily range is 96--98, while active
  membership is 98 and all observable signal cells are finite. No member,
  market value, or signal value was replaced or filled.
- All four signal paths preserve 2019--2025 signal, position and key-metric
  parity. Formal 2026H1 Qlib runs now complete under the unchanged TopK,
  rebalance and CnExchange cost contract. The equal-weight combination net
  return is -5.84%, CSI300 excess -10.11 points, fixed-100 excess +6.22
  points, Sharpe -1.143 and maximum drawdown -6.98%.
- Original experiment `tha_2b367621...76383b` remains immutable and partial.
  Follow-up revision 2 `thf_9f389863...7307b2` and lifecycle policy
  `fulp_60672b83...a632a` are historical retrospective evidence, not Fresh
  Validation or Promotion evidence. Store is healthy at 45 artifacts / 1,589
  blobs; cold recovery and exact replay pass with zero Qlib calls and zero new
  artifacts/blobs.
- Preliminary follow-up `thf_39155cdb...d498d6` remains immutable; revision 2
  explicitly supersedes it because the preliminary output omitted per-strategy
  Calmar and lifecycle summaries.
- Current task: `QM2-P0-015F`. No successor is authorized by this task.

## Tushare fixed-100 Agent experiment (QM2-P0-015)

- Four historical-as-of rounds completed on only the immutable Tushare
  fixed-100 authority. The formal protocol admitted 2 candidates per round,
  executed 18 bounded factor-parameter Trials, and used one successful
  `openai_codex_cli` / `gpt-5.6-terra` call per round. A prior immutable
  diagnostic attempt consumed four additional calls before exposing a wrong
  public `CompiledFactor` field assumption; the task-wide total is therefore
  exactly the eight-call ceiling.
- Every round locked its candidates before the next-year evaluation. Mean
  next-year RankIC for rounds 1..4 was -0.00213, 0.00358, 0.00191 and 0.00331;
  fixed-100 net excess was -4.41%, 3.41%, 0.93% and 15.99%. The iteration
  assessment is `mixed`, not continuously improving.
- Selection used only evidence through 2024 and locked three Factors. The
  equal-weight combination returned 82.45% over the available 2019--2026H1
  main range, with 2.22% excess over fixed-100, 16.79% excess over CSI300,
  Sharpe 0.474 and maximum drawdown -19.07%. This full-range result must not be
  treated as an isolated 2026H1 result.
- 2025 completed for all locked Factors and the combination. The combination
  returned 4.23%, underperforming CSI300 by 17.52 percentage points and
  fixed-100 by 2.85 points. The three individual Factors returned -4.32%,
  1.62% and -7.41%.
- Every 2026H1 signal has 0% NaN. This original task remains immutable and
  `partial`; its rejected result is superseded only by the separate lifecycle
  follow-up evidence above, not rewritten.
- Experiment `tha_2b367621...76383b` is immutable. Store state is 43 artifacts
  / 1,580 blobs, healthy, Missing 0 and Unreferenced 0. Thirteen artifacts cold
  restored, and exact replay used zero Agent, Optimization, Qlib, Registry,
  network and legacy-data calls.
- Historical task: `QM2-P0-015`; its artifacts remain unchanged.

## Tushare-only authority cutover (QM2-P0-014)

- `tushare-pro-v1` is the only active market-data authority under ADR-0011.
  Fixed locks are `tu500_fb547c...24e8c` and `tu100_078e6609...2c526`.
- Real history covers 500 locked stocks from 2018-09-03 through 2026-06-23:
  daily 926,653 rows, adj-factor 931,312 rows, daily-basic 926,653 rows,
  trade calendar 2,854 rows and CSI300 1,889 rows. No full-market history was
  downloaded.
- Normalized bars `tnb_311f8c6f...c73ec`, Features
  `tfd_2cdcf056...6b97e`, Labels `tld_7f765006...dc969`, and fixed-100 Qlib
  view `tqv_c489efe4...941ff` are immutable Store artifacts. Continuous
  cross-year computation removes the old 2026 annual-boundary cold start;
  2026H1 idio-vol and locked-signal missingness are both 0%.
- Existing `QlibBacktestService` initialized directly against the new view;
  `RedisRecordingStrategy`, `SimulatorExecutor` and `CnExchange` contracts
  loaded successfully. Existing LightGBM is unchanged and is not yet bound to
  this new Feature Dataset.
- New Registry genesis `trg_0e23d0c7...1d309` has entry/promotion/approved/
  active counts 0/0/0/0. Sanitized Memory `tsm_d17b00a7...9fc8` retains only
  structural and engineering lessons; old metrics are explicitly invalidated.
- Purge result `ldr_cc9b249d...1fea0` deleted 59,168 files, all 97 legacy
  research descriptors and 372 exclusively legacy blobs, reclaiming
  11,366,423,425 bytes. Old annual features, old Qlib data and old research
  caches are absent. Final Store Inventory is `sai_2e7ce672...02040`, healthy,
  with Missing 0, Unreferenced 0 and legacy Artifact count 0.
- Current task: `QM2-P0-014`. Next task is only
  `QM2-P0-015 — Re-run Fixed-100 Agent Factor Experiment on Tushare Authority`.

Generated: 2026-07-18
Verified source commit before this task: `32dc6af0be24468da997e9e32e9627e23d360987`

## 2026H1 locked-signal missingness follow-up

- `QM2-P0-011BF` reconstructed the original Qlib numerator and denominator:
  3,822 NaN scores / 10,867 observed signal rows = 35.1707%. Against the
  locked 100 symbols and 111 dates, 233 rows are absent, so total expected-grid
  missingness is 4,055 / 11,100 = 36.5315%.
- The two locked Factors and their equal-weight combination have the identical
  missing mask. Both Factor Values artifacts have 180,241 exact Dataset keys,
  zero duplicates/missing keys and exact recomputation parity. DSL rolling,
  delta, rank, z-score, orientation and combination add zero 2026H1 NaNs.
- Root cause is upstream data quality: 222 cells belong to two completely
  absent locked symbols, 11 are local source-row absences, and 3,822 observed
  rows lack `style_idio_vol_20`. The source shows `style_beta_20` first valid on
  2026-02-02 and `style_idio_vol_20` first valid on 2026-03-09, consistent with
  a two-stage annual-boundary warmup. Provenance is insufficient to recreate
  the authoritative Feature without changing research semantics.
- Qlib view `qcv_211a189...d9d2` covers through its 2026-06-24 boundary
  sentinel; symbol/date alignment, score handoff and quote cells add no loss.
  The unchanged 20% gate still fails, so no 2026H1 Qlib rerun occurred.
- Audit `sma_33979ef...a9b64` and blocked follow-up
  `hbf_fc927bc...6e1f1` are immutable Store artifacts. Inventory
  `sai_39e8526...42f2` contains 97 artifacts / 372 blobs and is healthy.
  Cold recovery and exact-existing replay passed with zero new blobs.
- The unchanged pre-existing Artifact Store concurrent-import test is
  timing-sensitive: the final broad run exposed an immutable Receipt ID
  conflict and two focused reruns failed, while the same test on an archived
  base tree passed once. This task did not modify that unrelated production
  concurrency path; the failure is recorded rather than hidden.
- Current task: `QM2-P0-011BF`; status is `blocked`. The original
  `hae_5e4b11...3fedd` and `qbr_b8be069...f9dc0` remain unchanged. No successor
  task is authorized.

## Fixed-100 historical Agent diagnostic

- `QM2-P0-011B` locked 100 symbols from the first 20 observed 2019 sessions by
  mean `style_ln_mv_float` with at least 15 observations. No annual reselection,
  replacement or missing-data fill occurred. Dataset
  `fuhd_734dae...f95fb` covers 2019-01-02..2026-06-23 and binds the production
  Label Contract and annual source hashes.
- Four formal external `openai_codex_cli` / `gpt-5.6-terra` rounds made four
  calls and 14 bounded factor-only Trials. Round admitted counts were 2/0/1/2;
  mean next-year RankIC was 0.02346 / unavailable / 0.03963 / -0.01127.
  Assessment is `mixed`; later rounds did not consistently improve on Round 1.
- Selection through 2024 locked two candidates. Existing
  `QlibBacktestService` and `CnExchange` completed 2025 and the 2019–2026H1
  main-range attempt. The equal-weight combination returned 63.22% over the
  available full run, below the fixed-universe benchmark by 19.43 percentage
  points, with Sharpe 0.344 and maximum drawdown -20.03%.
- The task is truthfully `partial`: every locked signal has 35.17% NaN in
  2026H1 because its required style input is missing, exceeding the existing
  Qlib 20% signal-quality gate. No fill, reselection, gate relaxation, Fresh
  claim or promotion was performed.
- Historical Experiment `hae_5e4b11ba...3fedd` and Inventory
  `sai_8ee9085f...c4ee` contain 93 artifacts / 357 blobs. Cold recovery passed;
  exact replay made zero Agent, Optimization, Qlib, Registry and Store writes.
  Canonical Registry remains `frs_9f61af9b...92052`, 20 entries, with
  promotion / approved / active = 0 / 0 / 0. Fresh controls remain unchanged.
- Current task: `QM2-P0-011B`. No successor is authorized by this task; the
  2026H1 missing-signal boundary requires an explicit follow-up decision.

## Parameter-aligned external Agent success path

- `QM2-P0-012F` generated the Proposal parameter contract summary from the
  live DSL parameter fields, parameter/role enums, AST-role contexts and
  Optimization Search Space schema. Prompt and the one permitted repair now
  consume this summary; Control still requires declared = used = searched =
  role-assigned parameters and enforces type, bounds, step, AST role and the
  Cartesian Trial budget.
- New Goal `rg_decb8ade...bf3109` completed external Campaign
  `rc_4432a5d3...c04b56` with `openai_codex_cli`, Codex CLI
  `0.145.0-alpha.18`, explicit `gpt-5.6-terra`, one Provider call and no
  repair. Decision `rd_142a0fa4...ab9838` admitted Template
  `ft_115afad9...70aef1` with a lookback and factor-internal weight correctly
  bound in the AST.
- Study `fos_22c2f3b6...e8a84` executed all six bounded Trials successfully.
  The selected Trial is `fot_cd22d4e1...990db`, selected Factor Values is
  `fv_937e5df1...571a`, and contaminated Development result is
  `der_b8669e6...9a92e`. The result is adaptive research only, not predictive,
  not Validation/Frozen evidence and ineligible for promotion.
- Registry successor `frs_9f61af9b...92052` linearly follows
  `frs_c2ef675c...0237b5`, has 20 entries, and adds exactly one
  `research_registered` Entry. Promotion / approved / active remain 0 / 0 / 0.
  Fresh controls and the 0/60 maturity state did not change.
- Inventory advanced from `sai_b0c03807...70320` (66 artifacts / 287 blobs)
  to `sai_820983db...e5e68` (79 / 339). The delta includes three immutable
  Provider-Schema diagnostic Campaigns plus the successful Campaign graph.
  Integrity is healthy with zero missing and zero unreferenced blobs.
- A new empty cache recovered and Domain-validated the full successful graph.
  Exact replay returned Campaign/Result/Descriptor unchanged with Agent calls,
  Optimization calls, Development calls, Registry writes, new artifacts and
  new blobs all zero.
- P0-012 remains immutable `partial`: two Agent calls, no admitted Proposal and
  no Registry change. Its Call 1 used undeclared search names against empty
  placeholder Templates (`search_space_parameter_unknown`); the historical
  repair response was not persisted, so only the old validator branch proves
  the same error class, not an exact Proposal index or AST location.
- Current task: `QM2-P0-012F`. The only next task is
  `QM2-P0-011B — Fixed-100-Universe 2019—2026 Agent Iteration and Historical
  Backtest`; `QM2-FV-001` remains conditional on at least 60 mature post-lock
  trading dates.

## Artifact-backed external Agent production dry run

- `QM2-P0-012` executed Campaign `rc_16bf5717...b7ea` through the
  `store_required` CLI with Codex CLI `0.145.0-alpha.18`, explicit
  `gpt-5.6-terra`, one iteration, two Agent-call limit, one admitted-template
  limit and six-Trial limit.
- Both Provider calls exited 0 and recorded request/response hashes and usage.
  The initial response violated the strict Proposal parameter contract; the
  sole permitted repair did the same. The Campaign is therefore `partial`
  with zero Decision, admitted Proposal, Study, Trial, Factor Values,
  Development result or Registry write. No gate or budget was relaxed.
- The immutable partial Campaign is stored as descriptor
  `sad_2e42bc...7b18b`. Inventory advanced from
  `sai_a0b9e618...55d312` to `sai_b0c03807...70320`: 66 artifacts and 287
  blobs, healthy, zero missing and zero unreferenced. Canonical Registry stays
  `frs_c2ef675c...0237b5` with 19 entries and promotion / approved / active
  remain 0 / 0 / 0.
- Empty-cache Campaign and canonical Registry recovery passed. Exact replay
  returned the same Campaign/Result/Descriptor with Agent calls, Optimization
  calls, Registry writes, new artifacts and new blobs all zero. Legacy fallback
  was false. Fresh remains `awaiting_first_fresh_date` at 0/60.
- This P0-012 partial Campaign remains historical evidence and was not
  overwritten, retried or reclassified by P0-012F.

## Artifact-backed Research Runtime v1

- `QM2-P0-011` implements Store-backed references, runtime policy, verified
  resolver, immutable publisher, descriptor-keyed ephemeral cache, exact replay,
  source-aware legacy guards, Domain adapters and Store-only research-state
  recovery. Formal QM2 CLI mode now defaults to `store_required`.
- Factor Values, Optimization, Validation/Frozen, Registry, Campaign, Fresh
  Admission and Fresh Validation top-level entry points are Store-backed. Their
  low-level deterministic readers, validators and compute functions retain
  explicit paths supplied by the runtime.
- An empty-cache drill restored and Domain-validated eight artifact roles from
  the Store without reading original temporary source roots. Canonical Registry
  remains `frs_c2ef675c...0237b5` with 19 entries and promotion / approved /
  active counts remain 0 / 0 / 0.
- External Campaign `rc_0b13d7f...d9401c` exact-replayed with Agent calls,
  Optimization calls and Registry writes all zero. Exact-existing publication
  of Registry, Campaign and Optimization created no descriptor or blob.
- The QM2-P0-011 baseline Inventory was `sai_a0b9e618...55d312`: 65 artifacts, 280 blobs,
  healthy, zero missing and zero unreferenced. `/private/tmp` is not a formal
  runtime authority. Explicit `legacy_local` exists only for emergency
  compatibility and cannot establish formal publication without Store import.
- Fresh Validation remained `awaiting_first_fresh_date` at 0/60; no Fresh
  Result was created. Its successor dry run is recorded above.

## Persistent Research Artifact Store v1

- `QM2-P0-010` implements a local immutable content-addressed Store with
  formal Domain validation, exact-existing/conflict semantics, verified
  materialization, inventories, integrity scans and reachability planning.
- The root resolves by CLI, environment, then
  `~/.quantmind2/artifact-store/v1`; Git remains control/implementation
  authority and the Store is large immutable research-artifact authority.
- Current Plan `rap_f3aca751...ccc247` migrated all 65 reachable formal
  artifacts with zero missing/unresolved sources. Inventory
  `sai_a0b9e618...55d312` records 107,663,971 logical bytes, 107,518,972 unique
  Blob bytes, 144,999 deduplicated bytes and healthy integrity.
- Independent Factor Values, Optimization, Registry and Campaign recovery
  passed byte/hash parity and formal Domain revalidation; source artifacts were
  preserved. Fresh Validation remains awaiting its first date at 0/60.
- The immutable `QM2-P0-010` Run remains Git-inconsistent and non-indexable:
  its integrity inventories omit only its own Manifest (41 recorded versus 42
  verified changed paths; 27 recorded versus 28 verified added paths). Its 41
  business ChangedFiles are correct because that list excludes the Manifest
  and retains the Report.
- `QM2-P0-010F` records the exact commit-derived inventory in a separate
  immutable correction Artifact and links it to the original Run with
  `corrects`; it does not edit the original Run, Store code, Store bytes,
  migration result, inventory or recovery result.
- `QM2-P0-010F` latest correction Run is
  `QM2-P0-010F-20260717T161330Z-77f5b1f`. Its successor `QM2-P0-011` performs
  the runtime cutover; `QM2-FV-001` remains forbidden
  until at least 60 locked post-lock mature trading dates exist.

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

- Generic Research Skill packages beyond Agent Research Campaign v1
- Cross-domain Decision Validator beyond the Campaign-specific runtime
- Persistent multi-service QuantMind 2.0 Code Orchestrator
- Registry → Feature Snapshot → LightGBM lineage
- Unified Signal Service
- Project Knowledge API
- Project Knowledge Web UI
- Project Knowledge API and Web UI

## Factor Validation v1

- `QM2-P0-006` implements the audited production Label Contract, immutable
  Label Snapshot and Validation Dataset, strict Train/Validation/2025
  quarantine/Frozen splits, one-date embargo, 14-Trial full-period Factor
  Values, Train-only orientation, daily IC/RankIC, Validation-only immutable
  selection and independent one-time Frozen evaluation.
- Dataset `vd_1ac71a8b...c3ed62` binds current source-byte hashes and output
  Parquet hashes. The effective split dates are Train 2022-01-04..2023-12-28,
  Validation 2024-01-02..2024-12-30, quarantined development
  2025-01-02..2025-12-30 and Frozen 2026-01-05..2026-06-23.
- Four of 14 Trials passed the published Validation gates; top three are locked
  in Selection `fvs_f679a630...819e9c`. Frozen result
  `fvt_734478fc...21c787` is confirmatory evidence only and did not alter the
  Selection or Optimization.
- No Registry promotion, LightGBM, Qlib, signal, portfolio, backtest, Sharpe or
  future-return conclusion was produced. Registry remains the next boundary.
- The Factor Validation implementation is committed at
  `8ad3e22575f9339955dd5fde4255269d87e9b138`. Its immutable Implementation
  Run `QM2-P0-006-20260716T181959Z-07a3df9` remains Git-inconsistent because
  one manually recorded `before_hash` differs from the base Git blob.
- `QM2-P0-006F` records the verified base-blob SHA-256 in a separate strict
  evidence-correction Artifact and links it with `corrects`; it does not edit
  or make the original Run consistent and does not alter Validation, Selection
  or Frozen Test artifacts.
- The three Frozen candidates remain confirmatory observations only. They do
  not constitute Registry promotion evidence and none is currently promoted.
- Latest Implementation Run: `QM2-P0-006F-20260717T044608Z-8ad3e22`.

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

## Persistence reality audit

- `QM2-P0-002A1a — Persistence Mechanism Reality Audit` completed a static,
  code-backed audit at base commit `8188a1e78f0ff74f7beb49d3522c417ed76194fa`.
- The audit records that SQLAlchemy/PostgreSQL persistence is fragmented across
  a shared async manager, sync compatibility pools, service-local engines,
  runtime DDL, bootstrap SQL, and manually documented upgrade SQL.
- The recommended future Ledger route is the shared async PostgreSQL manager,
  API-owned SQLAlchemy metadata, transaction-neutral repository methods, and a
  versioned SQL migration in an explicit `quantmind2` schema. This is an
  engineering selection only, not an implemented persistence layer.
- At the A1a audit point, Ledger domain and Repository code did not exist;
  later A1b tasks now supersede that implementation-state observation while
  preserving the audit's persistence findings.
- Latest Implementation Run:
  `QM2-P0-002A1a-20260714T145325Z-8188a1e`.

## Implementation Ledger domain model

- `QM2-P0-002A1b1 — Implementation Ledger Domain Model and Invariants`
  implements standard-library, frozen domain objects, stable enums, structured
  errors, value validators, Run state invariants, and direct relationship
  conflict checks.
- The domain package is independent of SQLAlchemy, FastAPI, environment,
  filesystem, network, Git commands, and databases.
- At the A1b1 point, Repository behavior was deferred; A1b2 now supplies its
  Protocol and test-double contract without changing the frozen domain model.
- Latest Implementation Run:
  `QM2-P0-002A1b1-20260714T152420Z-6ec76c0`.

## Implementation Ledger Repository contract

- `QM2-P0-002A1b2 — Ledger Repository Contract and In-memory Test Double`
  implements synchronous `typing.Protocol` contracts, immutable query/page
  values, stable Repository errors, full in-memory relationship cycle checks,
  expected-version checks, append-only details, stable queries, and an atomic
  batch test contract.
- `InMemoryLedgerRepository` is a process-local test double only. It is not a
  production Ledger or persistence authority.
- SQLAlchemy Repository, database transactions, Manifest Parser/Indexer, Git
  consistency service, API, and UI remain unimplemented. A2a1 now supplies
  static core ORM mappings only.
- Latest Implementation Run:
  `QM2-P0-002A1b2-20260714T155151Z-200665b`.

## Implementation Ledger core ORM mapping

- `QM2-P0-002A2a1 — Core Implementation Ledger ORM Mapping` maps only
  ImplementationTask, ImplementationRun, and RunRelationship on the selected
  API Declarative Base.
- The mappings explicitly target `quantmind2`, use JSONB/timestamptz,
  VARCHAR plus named enum checks, named PK/FK/UQ/check/index objects, positive
  version columns, and `ON DELETE RESTRICT`.
- PostgreSQL DDL was compiled statically from SQLAlchemy metadata without an
  Engine, Connection, Session, credentials, or DDL execution.
- This is a mapping contract only. Reference/annotation ORM tables, domain
  mappers, migration, real schema/table creation, PostgreSQL verification, production
  Repository, Session/UoW, and transaction code remain unimplemented.
- QM2-P0-002A2a2a adds static API-Base mappings for ChangedFile,
  ChangedSymbol, TestExecution, and ImplementationArtifact. Their named PK,
  Run FK, natural unique, checks, and indexes compile as PostgreSQL DDL.
- The four detail mappings are metadata only: no Mapper, migration, schema,
  table, database connection, Repository, Session/UoW, Indexer, API, or UI was
  created.
- Latest Implementation Run:
  `QM2-P0-002A2a2a-20260714T164637Z-53efb74`.

## Implementation Ledger ORM mapping

- `QM2-P0-002A2a2b1 — Ledger Component and ADR Reference ORM Mapping`
  maps ComponentReference and ArchitectureDecisionReference on the shared API
  Base using their A1b2 natural identities as composite primary keys.
- Both tables have only a restrictive Run FK. Component Catalog and ADR Index
  remain Git-derived facts and are not database foreign-key targets.
- `QM2-P0-002A2a2b2 — Ledger Limitation and Recommended Task ORM Mapping`
  maps the two remaining annotation objects. Both use globally unique domain
  IDs as primary keys, restrictive Run FKs, enum-derived checks, and explicit
  indexes; the A1b2 Run/object identities are also recorded as named unique
  constraints.
- All eleven currently targeted Ledger objects now have static ORM mappings.
  This is metadata only: Domain mappers, migration, `quantmind2` schema/table
  creation, PostgreSQL Repository, database access, Indexer, API, and UI remain
  unimplemented. No annotation row has been written.
- Latest Implementation Run:
  `QM2-P0-002A2a2b2-20260714T175052Z-646c4db`.

## Ledger Domain / ORM Mapper contract

- `QM2-P0-002A2a2c1 — Ledger Mapper Identity and Conversion Contract` fixes
  Mapper contract version 1.0.0, pure conversion boundaries, all eleven object
  round trips, enum/time/JSON/null/error rules, and deterministic ChangedFile
  and ChangedSymbol identity vectors.
- Frozen Domain/ORM `ImplementationRun.repository_root` is interpreted as a
  logical repository identity. Manifest v1's absolute path is execution context
  and requires an explicit future Indexer binding; it is not directly copied.
- This is a documentation and verification contract only. No Mapper Python,
  Core/Detail/Reference/Annotation mapper, migration, schema/table, database
  connection, Repository, Session/UoW, Indexer, API, or UI exists.
- Latest Implementation Run:
  `QM2-P0-002A2a2c1-20260714T181338Z-1d5affb`.

## Complete Ledger Mapper layer

- `QM2-P0-002A2a2c2a — Mapper Foundation and ImplementationTask Mapper`
  implements safe transport-neutral Mapper errors, contract version 1.0.0,
  reusable exact Enum/aware-UTC datetime/tuple-JSON conversions, and pure
  bidirectional ImplementationTask conversion.
- New Domain Tasks produce new ORM records with `version=1`; stored positive
  versions are validated but excluded from Domain. Existing-record updates,
  replay, conflict, optimistic concurrency, and transactions remain Repository
  responsibilities.
- `QM2-P0-002A2a2c2b — ImplementationRun Domain-to-ORM Mapper` adds pure
  bidirectional Run conversion, exact five-Enum conversion, aware UTC times,
  nullable commit/hash fields, logical repository identity preservation, and
  ORM-only version handling. Domain construction remains state authority.
- `QM2-P0-002A2a2c2c — Complete Remaining Ledger Domain-to-ORM Mappers`
  completes explicit bidirectional mapping for all eleven Ledger Domain
  objects. It adds RunRelationship, four Detail, two Reference, and two
  Annotation mapper families while preserving the Task and Run contracts.
- ChangedFile and ChangedSymbol technical IDs now use the frozen NFC/UTF-8/LF
  SHA-256 algorithms. Reverse mapping recomputes and rejects mismatched stored
  IDs. Parent Run context is explicit and must match each Domain object.
- Full Domain and ORM business-field round trips, all nine identity vectors,
  Enum and invalid-record cases, field/inventory drift, safe-error behavior,
  and no-side-effect guards are verified.
- Manifest Parser/Indexer, repository identity binding, PostgreSQL Repository,
  and business Session/UoW remain unimplemented.
- Latest Implementation Run:
  `QM2-P0-002A2a2c2c-20260715T050423Z-30edead`.

## Ledger migration and isolated PostgreSQL verification

- `QM2-P0-002A2b` adds explicit migration `0001`, exact-byte SHA-256
  checksums, `_schema_migrations`, ordered plan/status/validate/up/down, one
  transaction per migration, a stable advisory transaction lock, and guarded
  rollback.
- Fresh install now calls the same migration runner after base bootstrap;
  Ledger DDL is not duplicated in `quantmind_init.sql`.
- A disposable PostgreSQL 15 container verified the eleven business tables,
  87 columns, 97 named constraints, 49 explicit indexes, exact ORM/catalog
  parity, valid data, 18 invalid writes, `RESTRICT`, idempotent up, checksum
  drift rejection, rollback atomicity, down, reapply, and cleanup.
- This evidence is isolated verification only. No production database was
  migrated. PostgreSQL Repository, business Session/UoW, Manifest
  Parser/Indexer, Git consistency service, API, and UI remain unimplemented.
- Latest Implementation Run:
  `QM2-P0-002A2b-20260715T060812Z-7c83e36`.

## PostgreSQL Ledger Repository and Unit of Work

- `QM2-P0-002A3` implements the complete asynchronous PostgreSQL Repository
  mirror of the frozen A1b2 contract and an explicit async Unit of Work over
  the shared DatabaseManager engine/sessionmaker.
- Task, Run, Relationship, all eight child families, typed lists/history,
  exact replay, immutable conflict, savepoint recovery, expected versions,
  state changes, finalization, and atomic batch behavior are implemented.
- Relationship admission uses one stable PostgreSQL transaction advisory lock
  and a recursive CTE. Independent Sessions verified same/different Task races,
  stale updates, opposing-edge cycle admission, and batch conflict rollback in
  disposable PostgreSQL 15.
- The implementation is persistence access only. No Manifest Parser/Indexer,
  Git consistency service, repository identity resolver, API, UI, production
  migration, or research business feature was added.
- Latest Implementation Run: the `QM2-P0-002A3` Run paired with this task.

## Git-authoritative Ledger indexing

- `QM2-P0-002B — Manifest Parser, Git Consistency and Ledger Indexer`
  implements strict Manifest v1 parsing, explicit logical Repository binding,
  committed Git-object discovery, hash/commit/immutability checks, Domain
  Bundle admission, deterministic multi-pass indexing, JSON CLI commands, and
  isolated tests.
- Historical compatibility at base `d33f2815`: 16 v1 Runs discovered, 15 pass
  mandatory Git evidence, and zero form a complete Domain Bundle. The 001F Run
  declares a result commit different from its containing commit. Every v1 Run
  lacks independent Task status/creation time; populated children also lack
  Ledger identities or required semantics.
- No missing value was inferred. No historical Run was written as a backfill.
  A complete synthetic bundle verified insert, replay, immutable conflict, and
  rollback through disposable PostgreSQL 15. Production deployment/backfill
  has not occurred.
- ADR-0010 fixes logical repository identity and explicit runtime path binding.
- Ledger infrastructure implementation is closed. API/UI, watcher, webhook,
  daemon, and production deployment remain outside this phase.
- Latest Implementation Run:
  `QM2-P0-002B-20260715T090630Z-d33f281`.

## Forward-indexable Manifest v2

- `QM2-P0-002B1 — Manifest v2 Producer and Forward Indexability` implements
  strict Manifest v2 Schema, example, protocol documentation, and the formal
  `new` / `finalize-payload` / `validate` producer used by future Runs.
- Manifest v2 separates logical Repository identity from execution path and
  records Mapper/technical identity versions, stable child identities, typed
  artifact locations, complete Task/Run facts, and canonical integrity.
- Parser, Git consistency, Domain Bundle, Bootstrap, and Indexer accept v2
  without changing the v1 route. A valid v2 Run constructs all eleven frozen
  Ledger Domain families without Report prose or evidence gaps.
- The B1 Run itself uses Manifest v2 and passed committed-Git planning plus
  isolated PostgreSQL indexing, exact replay, immutable-conflict, and
  no-partial-write verification. Production database deployment did not occur.
- All 17 historical v1 Runs remain immutable. At the B1 base, 16 pass mandatory
  Git evidence and zero are fully indexable; QM2-P0-001F retains its declared
  result-commit mismatch.
- Ledger infrastructure is now formally closed. Project Knowledge API/UI,
  production deployment/backfill, watcher, webhook, and daemon remain absent
  and are not the next implementation scope.
- Latest Implementation Run:
  `QM2-P0-002B1-20260716T135059Z-0353435`.

## Fresh Validation forward protocol v1

- QM2-P0-009 locks three exact admitted candidates in
  `fvcl_716d7465285f7a8f541924877aa3acde9e90a38efe7d10dea2e20d6874063c7b`.
- Exposure ledger `rdel_56d95b77f42f5b9784badaf3558e92e375d87be9cc1194143e334aba3e55f5ff`
  records 2024 Validation, adaptive 2025 Development and historical 2026 Frozen
  exposure. Protocol `fvp_93163e1b4f82b52154bf0472b1cd165916f8ecae722ab851dd7fc4210bb5a867`
  freezes the earliest common 60-date window and all pass gates.
- Lock time is 2026-07-17T14:12:16.318993Z, market date 2026-07-17. The
  previously available source cutoff is 2026-06-24. Watermark
  `fdw_3459fb5a20fb60707c6bf001dc194a931cfea7cddf250de2a099cba97efaa248`
  finds source maximum 2026-06-24 and zero eligible dates; state is
  `awaiting_first_fresh_date`.
- No old 2026 rows were backfilled, no real Fresh evaluation ran, and promotion,
  approved and active counts remain zero.
- Registry successor `frs_c2ef675c8ad3d17e1351e6193df706bff1820f16f1d6aaa35bd9aeb7050237b5`
  adds only bounded `awaiting_data` evidence to those three entries; every main
  status remains `research_registered`.
- The immutable QM2-P0-009 Implementation Run remains Git-inconsistent and
  non-indexable because its manually assembled `changed_files` recorded 12 of
  35 Git-proven business paths. QM2-P0-009F adds complete Git-derived correction
  evidence and a `corrects` relationship without changing that Run or any Fresh
  Validation identity.

## Next task

## Market data entry and Dataset Snapshot v1

- `QM2-P0-003 — TongDaXin Provider Reality Audit and Dataset Snapshot Entry`
  completed the repository/data-flow audit and implemented the Provider,
  Raw Capture, deterministic normalization, quality gate, immutable Parquet
  Snapshot, reader, validator and CLI boundaries.
- Current production reality is multi-source: official/remote PostgreSQL,
  local/CSMAR Parquet, feature snapshots and Qlib binary are not bound to one
  authoritative version. Training reads yearly feature Parquet; Qlib backtest
  reads a separate binary provider view.
- The evidenced TongDaXin path is the proprietary `tqcenter.tq` wrapper used by
  standalone legacy scripts, not pytdx/mootdx. The module, local client/data
  directory and canonical unit evidence are unavailable in this environment.
- No real TongDaXin Snapshot was generated. Deterministic Fake Provider tests
  validate the full storage contract and are explicitly marked `provider_id=fake`.
- Calendar, PIT Universe, listing/delisting, corporate actions, ST, limits,
  suspension, industry, finance and index-membership authorities remain open.
- Existing LightGBM training and Qlib backtest have not switched to Dataset
  Snapshot.
- Latest Implementation Run:
  `QM2-P0-003-20260716T142422Z-0114f35` (partial: real TDX environment absent).

## Legacy production feature route

- `QM2-P0-003L — Legacy Feature Parquet Provider and Real Dataset Snapshot`
  binds the actual annual Parquet consumed by existing LightGBM training through
  an explicit read-only Provider and the shared immutable Snapshot authority.
- The latest complete source is 2025: 1,248,108 rows, 5,212 symbols, 243 dates,
  155 columns and exact source SHA-256
  `7fd0316e6f8d936688ef332357fb7589f64c0e127c5f64e3158c584baf28b00f`.
- The real bounded Snapshot is
  `ds_bc82e7bb2c63d2c47677b11cf0f4fc1e5aa11a0ed18ee0bb27e3c8ab667d2ee7`:
  5,931 rows, 100 deterministic symbols, 60 dates, all 152 allowed features,
  zero labels, zero quality errors. Labels remain inaccessible by default.
- Existing production-loader/Provider/Snapshot parity passed. The only allowed
  production conversion is the existing numeric source dtype to `float32` cast.
- Real TDX remains unavailable, but it no longer blocks the Factor DSL route.
  A future TDX Provider adds Daily Bars Snapshots under the same authority model.
- Existing LightGBM training and Qlib backtest have not switched consumers.
- Latest Implementation Run:
  `QM2-P0-003L-20260716T151140Z-7d29df7`.

## Manifest v2 forward-indexability repair

- `QM2-P0-003LF — Manifest Self-reference Fix and 003L Forward-indexability`
  makes the current Run Manifest a protocol carrier rather than a ChangedFile.
- New Manifest v2 production rejects self-reference with
  `MANIFEST_SELF_REFERENCE`; Report remains a valid ChangedFile and Artifact.
- Committed v2 self-reference uses a general, path-based compatibility rule.
  003L now validates and builds a complete Domain Bundle with one structured
  `LEGACY_V2_MANIFEST_SELF_REFERENCE_IGNORED` warning and zero evidence gaps.
- The real 003L Dataset Snapshot, hashes, values, quality and loader-parity
  evidence are unchanged.
- Latest Implementation Run:
  `QM2-P0-003LF-20260716T153535Z-22461e0`.

## Manifest PostgreSQL assertion closure

- `QM2-P0-003LF1 — Fix Manifest Self-reference PostgreSQL Test Assertion`
  corrects the test-only use of nonexistent `AnalyzedRun.git_consistency` to
  the public `AnalyzedRun.evidence` contract.
- The production Planner, Git evidence, Manifest, Indexer, Repository,
  migration, Dataset Snapshot and Legacy Provider behavior are unchanged.
- The opt-in disposable PostgreSQL suite now passes all four tests, including
  real 003L and 003LF planning, first index, exact replay and absence of a
  self-Manifest ChangedFile.
- Latest Implementation Run:
  `QM2-P0-003LF1-20260716T160222Z-da271ac`.

## Factor DSL v1 and real-Snapshot compute

- `QM2-P0-004` adds the closed JSON/typed AST contract, strict parser,
  canonical Template/Instance identities, dataset-aware static compiler and
  bounded pandas execution under `backend/services/engine/factor_dsl/`.
- Only Snapshot columns with exact role `feature` are admitted. Execution reads
  through `load_feature_matrix`, never `load_labels`, and preserves Snapshot
  `symbol,trade_date` keys.
- Factor Values v1 is an immutable atomic Parquet artifact with manifest,
  quality evidence, hashes and exact replay behavior. Runtime proof artifacts
  remain outside Git under `/tmp`.
- Five parameter instances on the real 003L Snapshot each produced and
  revalidated 5,931 rows; exact replay reused the same content identity.
- Real terminals were `mom_ret_1d`, `liq_volume_ratio_5`, `style_beta_20` and
  `style_idio_vol_20`; the Snapshot role contract reported 152 legal features
  and zero labels.
- Template IDs: rolling rank
  `ft_8174c2c375fe504dfada1d0cdb953ac94469ec8c017276382f365bfebccad8b5`,
  weighted delta
  `ft_c75dc9f65292b6711a939bb178c2b48455df07653708508b315395fc3b2e2453`,
  normalized spread
  `ft_bf8f68bfb0a54459cb3d1708990819f5ad194d7894c693acb9c178574c085d4d`.
- Bound Instance IDs are
  `fi_d666f5b0409763e8a2ce35c3135ac32adb82c83dd20c370f106414acf0793964`,
  `fi_94b3fc524e46b37f97c9a7e87aca83099da507b4c7822775d28e932d48f01943`,
  `fi_f808ee5f0c9c87035f6ef6d634ee8bece6373b622489042d527a89cf1df546f5`,
  `fi_ba5479118b518decabc2b165abca43d64fc4b70fc44d49e19b55ecad0552824a`
  and `fi_a462e50f80e7fc0fb134c123d556bb701ceed29acfb52850c14471cef69f1a76`.
- Factor Values IDs are
  `fv_385ed568d5b68b7ec24dc2302081f867469206d591e51002d32998085b504264`,
  `fv_5b83b004cd6c985f51af22c3d417656c7f24657bb2d1647607ca5a12f8fafdff`,
  `fv_346461783ca9956c2e90d66e04c028ffb90eb2ee08724ec58e64d01423f54bc9`,
  `fv_bb8d92e8ecc4d13f8c4d2e0d91c56b133186cb97ebeb32ec83b9c2f6b4b162a3`
  and `fv_c200a1c6d2f9d86527650073bf7184cfba1d43929832ecbeb9ff98b620a753c9`.
- This is a partial research component, not a Registry, factor validation,
  optimization, LightGBM feature, Qlib signal or production promotion.
- Latest Implementation Run:
  `QM2-P0-004-20260716T163004Z-4efc06b`.

## Factor Optimization v1

- `QM2-P0-005` adds strict Optimization Spec parsing, typed parameter-role
  admission, deterministic Search Space enumeration, trial/failure budgets,
  Study/Trial/Result identities, failure isolation, mechanical metrics,
  validation eligibility, stable candidate ordering, immutable atomic Study
  artifacts, exact-existing validation, replay, and CLI under
  `backend/services/engine/factor_optimization/` and `tools/quantmind2/`.
- v1 searches only Template-declared `lookback_window` and
  `factor_internal_weight` parameters. `signal_threshold` is reserved but
  rejected until a formal Signal node exists. Structure, model, portfolio,
  random, Bayesian, and distributed search are absent.
- Rolling Rank Study
  `fos_969d431e553ad29d1d7bcdd4d912a6ab92471b5c4faf833a18abe2607baa1cb2`
  produced five eligible real-Snapshot trials for windows 2, 3, 5, 10 and 20.
- Weighted Delta Study
  `fos_ac8ea3539ba0db8faa4dc223750d649584da270244ec022638faef8bdfeb5a19`
  produced nine eligible real-Snapshot trials for the deterministic
  `periods=[1,3,5]` by `weight=[0.2,0.5,0.8]` product.
- All 14 trials bind the same authoritative 003L Snapshot, reference immutable
  Factor Values artifacts, and passed mechanical eligibility. Re-execution
  returned exact-existing; existing Factor Values were replayed where present.
- `validation_candidate_order` is mechanical data/execution readiness only.
  No label, IC, RankIC, future return, LightGBM, Qlib, signal, or backtest was
  accessed or produced.
- Latest Implementation Run:
  `QM2-P0-005-20260716T171457Z-70982ed`.

## Canonical Registry reconciliation and Fresh Validation admission

- QM2-P0-008 and QM2-P0-008F produced sibling Registry snapshots from the
  same original Snapshot; neither branch contained the other.
- Reconciliation `frr_9112702e368326365d6f4adb144633c7d0cf3ae59baa61ed76270ae86e93cb32`
  preserves all Entries and establishes the unique current canonical Registry
  `frs_f0a08cc472270cf80f2ae8c1141de17871dacbe2edccba8eb4ffe05ca45d3ba4`.
- The canonical Registry has 19 Entries: 14 historical and 5 Agent-generated.
  Promotion candidates, approved, and active Entries remain zero.
- Admission Policy `fvap_e8af2fd66f311a35160e073258c3f910fe13fe767d0cd4389b90f536c6394efa`
  produced Result `fvar_89e61fe674bff1d10d46c9bea3913a456f236bbc191578291529736480a831ab`:
  three candidates advanced to the future Fresh Validation pool and two did
  not. The external factor was rejected for negative oriented Development
  mean RankIC. No Fresh Validation or Frozen evaluation was executed.

## Next task

`QM2-P0-010 — Persistent Research Artifact Store v1` is the only recommended
next task. A real one-time evaluation is separately permitted only after 60
post-lock label-complete dates exist.

## Autonomous Technical Feature Factory and Archetype-aware Alpha

- `QM2-R2-004` implements the bounded unlabeled Technical Terminal Feature
  Factory under `backend/services/engine/autonomous_technical_feature_factory`
  and the Archetype-aware Alpha Program under
  `backend/services/engine/archetype_alpha_program`.
- Formal Factory `technical_feature_factory_001` used eight external Agent
  calls, proposed ten Features, admitted/materialized two and froze Catalog v2
  `tfc2_229f19...cf5e6`. Label reads, Qlib, Tushare/network, manual planning
  and Promotion were zero.
- Formal `technical_alpha_program_002` revision 1.0.1 used 18 Agent calls, 36
  Proposals, 19 Admissions, 11 local rescue Trials and 58 Adaptive Qlib calls.
  Three Lanes, at least seven Families and both pre-registered Archetypes were
  attempted.
- Union Lock `aausl1_47e182...27d239` froze nine objects before Validation:
  four monotonic and five top-tail. Locked Validation ran both test forms;
  global BH FDR is `amtc1_fae10b...dd7d1`.
- All nine objects failed the unchanged Archetype gate and/or FDR. Final
  Report `aapr1_e344e1...f4f6e3` is
  `completed_no_validation_survivor`. Registry, Fresh Locks, 2025/2026H1
  reports and Promotion writes are zero.
- Store integrity is healthy with Missing 0 and Unreferenced 0. Cold
  inspection, resume and exact replay succeed with every external call/write
  counter equal to zero.

## Factor Registry v1

- `QM2-P0-007` implements strict Registry Entry, Promotion Policy and Decision,
  evidence-derived status, immutable content-addressed Registry Snapshot,
  exact-existing publication, read-only queries, and CLI under
  `backend/services/engine/factor_registry/` and `tools/quantmind2/`.
- Real Snapshot
  `frs_436f4a966ea0c00ee2182c665813cd74cc13bb900a7022604ad9efc26849f2d9`
  uses policy
  `fpp_6ca41655ea0ec5692ef2799674ef743a8bf91a6cf58718e124163bf033e255a3`
  and registers all 14 existing Factor Instances in two Template families.
- Statuses are exactly 10 `validation_rejected`, one
  `validation_passed_not_selected`, and three `frozen_rejected`. There are zero
  `promotion_candidate`, `approved`, or `active` Entries. No currently
  validated-effective or production Factor exists.
- Registry verifies Optimization, Validation, Selection, Frozen, and QM2-P0-006F
  correction evidence without rerunning or modifying research. Agent receives
  read-only, visibility-filtered Registry history and has no decision authority.
- Registry database persistence, API/UI, durable artifact storage, actor
  authorization, redundancy analysis, LightGBM/Qlib consumption, and active
  Factors remain unimplemented.
- Latest Implementation Run:
  `QM2-P0-007-20260717T052606Z-ff4a61b`.

## Agent Research Campaign v1

- `QM2-P0-008` implements closed Research Goal/Decision contracts, sanitized
  Campaign Memory, deterministic and Codex Agent adapters, structural novelty,
  bounded orchestration, adaptive Development evaluation, immutable Campaign
  artifacts, CLI, and research-only Registry evidence under
  `backend/services/engine/research_campaign/`.
- Real Baseline Campaign `rc_4970d141...19cd5f` ran three iterations against
  Dataset Snapshot `ds_dd1defb...e338f`, admitted four novel Templates, ran 12
  successful Optimization Trials, and published four `research_registered`
  entries in Registry Snapshot `frs_d40bfd74...584718`.
- Direction was fixed on 2022–2024. Development feedback used only
  2025-01-02..2025-12-30 and is explicitly contaminated, adaptive-only, not
  Validation, not Frozen evidence, and ineligible for promotion. No Frozen
  evaluator was called and candidate/approved/active additions are all zero.
- Codex CLI and the real adapter were invoked. Two bounded calls per Campaign
  returned provider exit code 1 before a structured Proposal was available;
  Campaign `rc_c9c7a98...3bca43` is therefore immutable `partial` evidence with
  zero admitted Templates, Trials, or Registry changes. QM2-P0-008 as a whole
  is partial, not completed.
- Latest Implementation Run:
  `QM2-P0-008-20260717T072210Z-0374aac`.

## Automated Fresh Model Cohort observation

- Current task: `QM2-R2-009`.
- Cohort `mfcc1_faab1ee6...7bde6dc` contains exactly the two immutable
  `QM2-R2-008` L1 Model Candidates and Fresh Locks.
- Formal Tushare calendar evidence derives `2026-07-24` as the first open date
  strictly after the project exposure cutoff `2026-07-23`.
- First-seen Snapshot `fms1_e0aaaf86...9f83e3` contains one Fresh trading day.
  Both Candidates have one prediction, zero mature L1 observations, zero
  monthly retraining events, and remain `fresh_evidence_accumulating`.
- Cohort HAC/BH testing is waiting for both members to satisfy the unchanged
  minimum evidence gate. Registry writes and Promotion writes are zero.
- Heartbeat `fmhr1_224de05e...f9fe42` is Store-backed. Cold recovery and exact
  replay return all external-call and write counters as zero. Store integrity
  is healthy with Missing 0 and Unreferenced 0.
- System-level scheduling remains uninstalled. No successor task is authorized.

## Fresh Heartbeat LaunchAgent operations

- Current task: `QM2-R2-010`.
- The repository now contains the frozen 15-trigger LaunchAgent template,
  management CLI, installed-wrapper contract, atomic lock, 10 MB / ten-file
  log rotation, local status/history, failure classification, edge-triggered
  notifications, and immutable scheduler/operational Artifact kinds.
- Manual formal execution reuses Heartbeat
  `fmhr1_224de05e...f9fe42`; the repeat is `exact_replay` with zero Tushare,
  model, prediction, Label, strategy, Artifact, or Blob work. Both Candidates
  and the Cohort remain `fresh_evidence_accumulating`.
- Scheduler status `fhss1_9bbdf90c...22f53d2` and operational run
  `fhor1_ebc67320...d8f5d4` are immutable Store evidence. Store integrity is
  healthy with Missing 0 and Unreferenced 0.
- Real current-user install/bootstrap and RunAtLoad were attempted. macOS
  blocked background access to the repository and Python runtime below
  `~/Documents`. The nonfunctional Agent was booted out and uninstalled;
  operational logs and Artifacts were preserved.
- Automatic scheduling is therefore not active. No Candidate, Lock, Cohort,
  model, Label, strategy, Registry, Promotion, dependency, lockfile, shell
  profile, power setting, or Factor Lab source was changed.

## External Agent Provider completion

- `QM2-P0-008F` diagnosed the historical exit code 1 as Provider
  `invalid_json_schema`: Codex CLI structured output requires explicit JSON
  types alongside `const` and `enum`. The adapter now performs a semantic-only
  transport normalization, parses JSONL events, classifies Provider failures,
  redacts safe error summaries, and records bounded call evidence.
- Codex CLI `0.145.0-alpha.18` successfully used explicitly configured
  `gpt-5.6-terra`. Historical QM2-P0-008 failed Campaign evidence remains
  immutable and unchanged.
- External Campaign `rc_0b13d7f...d9401c`, Decision
  `rd_0efd9c55...f08e96`, admitted one novel Template, completed Study
  `fos_eb355bff...ba56be` with four successful Trials, produced contaminated
  Development result `der_d8e4951e...53bbb`, and published one
  `research_registered` entry in Registry `frs_7ab0a844...01054`.
- Replay returned exact-existing with zero new Agent calls. Promotion candidate,
  approved, active, Validation evidence, and Frozen evidence additions remain
  zero. The 2025 Development period remains contaminated adaptive research.
- Latest Implementation Run:
  `QM2-P0-008F-20260717T113419Z-5988dff`.
