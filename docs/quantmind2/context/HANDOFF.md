# Codex Handoff

## QM2-R2-012 runtime-hardening handoff

- Read the R2-012 Implementation Run and
  `FRESH_HEARTBEAT_OPERATIONS_V1.md` before changing the deployed heartbeat.
- The only supported runtime diagnostics are `safe-status`,
  `safe-launchctl-status`, `safe-credential-check` and
  `safe-runtime-diagnostics`. Never persist or return raw launchctl output,
  environment dictionaries, process environments or credential material.
- Per-run temporary ownership and stale cleanup live in
  `fresh_runtime_deployment/temporary_directory.py`. Never replace the exact
  owner/PID/age/lock checks with wildcard deletion.
- `hardened-cutover` is the deployment-locked post-commit transition. It
  preserves the old App Snapshot, reuses the active environment and canonical
  Store, performs two LaunchAgent runs and rolls back pointer/config/plist on
  failure.
- The R2-011 session diagnostic exposure is acknowledged, not erased.
  Repository/config/Artifact persistence is false; credential rotation is
  user-governed.
- Dynamic runtime truth is in the external current Deployment Status and
  `fresh_runtime_hardening_status` bound to
  `QM2-R2-012-20260725T063951Z-4a12e40`.

## QM2-R2-003 multi-Campaign Program handoff

- Read `AUTONOMOUS_MULTI_CAMPAIGN_RESEARCH_PROGRAM_V1.md` before changing the
  Program runtime. Formal Program is `afrp1_5ac295d3...a150b0`; Report is
  `afpr1_d7368ad6...e4f508`.
- The adaptive partition ends at 2020-12-31. Never expose 2021+ metrics,
  validation state, historical ranks, contaminated reports or Fresh evidence
  to an Agent, Lane/Program Planner, Failure Memory, parameter selection,
  early stop or shortlist order.
- Three Lanes completed 15 total Rounds and the minimum early-stop coverage.
  Only trading confirmation produced a Lane shortlist. The single Union
  object failed locked validation on median RankIC and BH FDR, so the legal
  outcome is `completed_no_validation_survivor`.
- Candidate Locks, Registry writes, 2025/2026H1 reports and Fresh Locks are
  zero. Do not lower gates, retune after validation, rank using validation,
  or turn the failed object into a Registry entry.
- Store integrity is healthy; cold validation has zero gaps and exact replay
  makes zero Agent/Qlib/optimization/network/Registry/Fresh/Promotion calls
  and creates no objects. No successor is authorized.

## QM2-R2-002 locked-holdout Campaign handoff

- Read `AUTONOMOUS_FACTOR_RESEARCH_CAMPAIGN_V2.md` before changing the
  Campaign runtime. Canonical Spec is `afc2_f3ba310a...f17cb2`; Report is
  `afcr2_bbeee1e...cb4b0`.
- Discovery ends physically and logically at 2022-12-30. Never expose 2023+
  metrics, statuses or reports to Agent, Planner, Failure Memory, parameter
  selection, early stopping, shortlist ranking, or budget changes.
- The immutable shortlist had one object. It failed the two-positive-RankIC
  Holdout gate, so the legal result is `completed_no_holdout_survivor`, zero
  Registry candidates and zero Fresh Locks. Do not lower the gate, retune,
  rank on Holdout, or rescue from 2025/2026.
- v1's three candidates remain immutable retrospective v1 candidates.
  Generalization assessment is isolated from v2 clean-room memory.
- Store integrity is healthy; cold validation has zero gaps and exact replay
  uses zero Agent/Qlib/network/optimization/Registry/Fresh/Promotion calls or
  new objects.

## QM2-R2-001 autonomous factor campaign handoff

- Read `AUTONOMOUS_FACTOR_RESEARCH_CAMPAIGN_V1.md` and the QM2-R2-001
  Implementation Run before changing research orchestration.
- Canonical Spec is `afc1_5bae780e...a8034`; Report is
  `afcr1_e5eea677...460f4`. Twelve automatic rounds used 12 Agent calls, 26
  Proposals, 20 admissions, eight local-rescue Trials, 40 annual evaluations
  and 74 formal Qlib calls without manual round planning.
- Three locks are research-only:
  `afcl1_6fddf98b...90f880`, `afcl1_da61b451...59ba3e` and
  `afcl1_d54ef8d8...ac1c6`. Their 2025 and 2026H1 results are contaminated
  reports, not selection, Fresh Validation, Frozen Test, Promotion or
  production evidence.
- Fresh Forward evidence, report-period feedback, Strategy/Combined
  optimization, market-data network calls and Promotion writes are all
  excluded. Do not weaken these boundaries or turn a Candidate Lock into
  production state.
- Store integrity is healthy with no missing or unreferenced object. Cold
  recovery has no evidence gaps; exact replay and terminal execute use zero
  Agent/Qlib/network/optimization/Registry/Promotion calls and create no
  Artifact or Blob. No successor is authorized.

## QM2-R1-010 breadth-gated momentum forward handoff

- Read `BREADTH_GATED_MOMENTUM_FORWARD_V1.md`, R1-009 and R1-008 before
  interpreting the overlay. Signal D and all U/G/R parameters are frozen.
- Formal `build_regimes` output at `t` already uses raw `t-1` breadth. Test
  that returned state directly; never add a second lag, include neutral, or
  tune thresholds.
- Gate Spec `bmgs1_4cb24dc3...aec343` and Fresh Lock
  `bgmfl1_80313cd9...436b60` predate all new network evidence. Snapshot
  `tims1_a59e3127...9168c` covers 22 open sessions after 2026-06-24.
- Fresh evidence is accumulating: 20 return sessions, two 10-session windows,
  12 gate-on sessions and two gate-on rebalances do not meet the fixed
  60/5/20/3 minimums. Positive interim metrics are not support.
- Exact replay recovers the six canonical task artifacts plus Signal D with Store integrity healthy,
  Missing 0 and Unreferenced 0, and all external, optimization, Qlib,
  Registry, Promotion and new-object counts zero. No successor is authorized.

## QM2-R1-009 momentum tail-alpha handoff

- Read `MOMENTUM_TAIL_ALPHA_DIAGNOSTIC_V1.md`, the R1-009 Implementation Run
  and the immutable R1-008 study before interpreting Signal D.
- Signal D remains the exact 0.5/0.5 absolute/residual momentum consensus.
  Revision 2 separates formal `model_label` RankIC from adjusted-close
  forward-return RankIC; never merge these meanings or replace the formal
  gate with a tail metric.
- The final class is `regime_specific_factor`; only narrow/weak breadth has
  jointly positive RankIC, Q10-Q1 and Top20 CSI300 excess. The advisory
  decision `retain_for_regime_specific_research` was not executed.
- 2025 and 2026H1 are retrospective reports only. Both fail Top20 relative
  performance; 2025 underperformance is not explained by low beta, and
  2026H1 adjusted-close tail returns reverse despite positive formal label
  RankIC.
- Diagnostic `mtad1_308b2628...951951` plus four child artifacts cold-recover
  and exact-replay from a healthy Store with every prohibited call/write and
  new-object count at zero. No Candidate, Registry or Promotion state changed.
- No successor task is authorized by this implementation.

## QM2-R1-008 low-frequency momentum handoff

QM2-R1-008 completed the pre-registered comparison with 40 formal Qlib calls:
four signals times B0/L1 times four years, plus eight full-period runs. No
Agent or Factor/Strategy/Combined Optimization was called. L1's ten-session
protocol reduced median annual turnover by 34.54% and costs by 33.21%; it
improved median net return for every signal but did not make any signal pass
all frozen RankIC and stability gates.

The assessment is `stock_selection_signal_only`. There are zero Candidate Locks,
so chronology correctly produces zero 2025/2026H1 reports and no
Registry or Promotion write. Study `lfmsta1_18f3a4ad...65ff80`, assessment
`lfma1_de242a62...319f3` and inventory `sai_06ee449c...28be` are immutable and
healthy. Cold recovery restored 39 objects; exact replay used zero calls and
created zero artifacts or blobs. The new Codex should read
`LOW_FREQUENCY_MOMENTUM_STUDY_V1.md` and the QM2-R1-008 Implementation Run.
No successor task is authorized.

## QM2-R1-007 default-first momentum handoff

- Read `DEFAULT_FIRST_MOMENTUM_STRUCTURE_SEARCH_V2.md`, the R1-006 policy
  contracts and R1-004 semantic audit before changing momentum research.
- Canonical Experiment is `dfme1_e15ea299...98b6b0`; Assessment is
  `dfma1_b259450...271af4`. Six Agent calls, eight defaults, thirteen local
  Trials and 21 Qlib calls produced zero eligible structures.
- The result is deliberate: every default exceeded turnover 45 and lacked
  positive excess/group evidence; none of the legal one-hop Trials rescued
  it. Do not lower the gates, reopen full search, tune Strategy parameters or
  use 2025/2026H1 to select a structure.
- There are no Candidate Locks or report-period results. All Registry states
  remain unchanged and no Promotion exists. Exact replay is zero-call and
  Store integrity is healthy.
- No successor task is authorized by this implementation task.

## QM2-R1-006 default-first optimization-governance handoff

- Read the three optimization policy contracts and the R1-005/R1-005F Runs
  before changing parameter-research behavior. R1-005 is supported as
  `completed_corrected`; never rewrite its historical Report or Manifest.
- New Factor/Strategy research must evaluate explicit Agent defaults first.
  A pass freezes immediately; a failure permits only the bounded one-hop local
  neighborhood. Full spaces are diagnostic-only and opt-in.
- Combined optimization is suspended. `F0S0`, failure-gated `F1S0`, and
  failure-gated `F0S1` are the only allowed combinations; if both defaults
  fail, search Factor locally with default Strategy and then stop.
- Canonical governance decision is `ogd1_7de0ba81...911f7f5`; its three policy
  parents and the decision cold-recover and exact-replay with all execution
  and new-object counts zero.
- R1-003 locks remain `research_registered`. No Candidate, Registry lifecycle,
  Qlib result, Dataset, signal or historical optimization artifact changed.
- No successor task is authorized by this governance implementation.

## QM2-R1-005F Git evidence correction handoff

- The original `QM2-R1-005-20260722T052636Z-82f13f9` Report and Manifest are
  immutable and remain Git-inconsistent: `validated=false`,
  `indexable=false`, with `changed_file_hashes` and `source_bundle_hash`
  evidence gaps.
- Correction evidence is rebuilt exclusively from commit `3e04743f...`: 25
  changed paths, 10 added paths and 24 business ChangedFiles. The only hash
  mismatch is the contract file after a trailing-whitespace cleanup performed
  after Manifest hash finalization.
- `QM2-R1-005F` links to the original through `corrects`. Together they are
  the supported `completed_corrected` Ledger representation; never modify the
  historical Run to make it appear valid.
- Research behavior and results are unchanged. Correction execution has zero
  Agent, Factor/Strategy Optimization, Qlib, network, Promotion, Candidate
  mutation, new research Artifact and new research Blob counts.
- No successor task is authorized by this evidence-only correction.

## QM2-R1-005 handoff

- Read `PARAMETER_OPTIMIZATION_OVERFIT_ABLATION_V1.md`, the R1-005
  Implementation Run and the preceding R1-004 semantic audit before changing
  parameter-research behavior.
- Final Assessment is `poa1_15e9398...c69f1a`, contract revision 2. Its six
  artifacts recover from the Store and exact-replay with all computational,
  external and new-object counts equal to zero; Store integrity is healthy.
- Candidate A default is window 20 and Candidate B default is weight 0.5.
  Their frozen F1 and F2 factor spaces are the same three points; do not claim
  this study observed a larger F2 factor search.
- Candidate B is likely overfit in factor and strategy layers. Both Candidates
  are likely overfit under O1 and O2; ensemble evidence is inconclusive. The
  formal advisory decisions are default-first for separate Factor/Strategy
  optimization and suspend for combined optimization.
- Do not apply these recommendations automatically. Both locks remain
  `research_registered`; no new Factor, Candidate state, Registry state,
  Agent/network call or Promotion exists. No successor is authorized.

## QM2-R1-004 handoff

- Read `MOMENTUM_SIGNAL_SEMANTIC_AUDIT_AND_ALPHA_DECOMPOSITION_V1.md` and the
  `QM2-R1-004` Implementation Run before interpreting the two R1-003 locks.
- Candidate A is momentum deviation/surprise without risk adjustment.
  Candidate B rewards distance below the 60-session high; it is not breakout
  confirmation. Historical IDs and names remain unchanged.
- 2025 has positive RankIC but negative CSI300-relative performance. 2026H1
  has negative RankIC and negative residual return. Costs and stock
  concentration are not the primary explanation.
- The formal decision is `continue_as_stock_selection_overlay_only`; it does
  not execute a next task. Both locks remain `research_registered` and no
  Promotion state exists.
- Five diagnostic artifacts cold-recover from the Store. Exact replay is
  zero-call and creates no Store objects. No successor is authorized here.

## QM2-R1-003 handoff

- Read `RESEARCH_ARTIFACT_COMPLETENESS_V1.md` and
  `SKIP_RECENT_MOMENTUM_ITERATION_V1.md` before further factor research.
- Canonical Experiment is `srme1_072b0d1a...d1ab3c`; its 368-artifact lineage
  cold-recovers with zero replay calls and healthy Store integrity.
- Two independent locks are `srmcl1_56201db3...9f95b` and
  `srmcl1_4e0abd49...c80b4`; both are `research_registered` only. The
  two-family ensemble is permitted.
- Both locks and the ensemble underperform CSI300 in contaminated 2025 and
  2026H1 reports. They are not Fresh Validation, Promotion or production.
- The original `QM2-R1-002` ghost candidate remains unrecoverable and was not
  reconstructed. No successor task is authorized here.

## QM2-R1-002 handoff

- Read `docs/quantmind2/contracts/MOMENTUM_FACTOR_ITERATION_V1.md` and the
  `QM2-R1-002-20260721T144440Z-5d6442c` Implementation Run first.
- Canonical Store experiment:
  `mfi1_87177b7c06420e65159d3f5bdafee8149cdb3290c32f08712cd73e59a4e19dee`,
  revision 2, superseding immutable revision 1.
- The research stopped after round 5 under the frozen early-stop rule. Eight
  families were explored; one standalone eligible candidate did not satisfy
  the two-family final-lock gate, so there are no locks or ensembles.
- Do not lower eligibility, open an extra round, reuse 2025/2026H1 for
  selection, search Strategy parameters or promote any result.
- Store replay is runtime evidence; local `/private/tmp` work directories are
  disposable and are not evidence sources. No successor task is authorized.

## Expanded-factor Git evidence correction

- `QM2-R1-001F` is an evidence-only correction. It reconstructs commit
  `4de8b1e8...` as 26 changed paths and 13 added paths, including the original
  Manifest path, and relates the new Run to
  `QM2-R1-001-20260720T182257Z-a574580` with `corrects`.
- The original Run remains immutable and historically `partial_committed`.
  The completed correction Run plus its relationship is the current Ledger
  equivalent of `completed_corrected`; do not rewrite the old Manifest or
  Report.
- The business result remains `mixed`: the sole new factor remains
  `research_registered`, did not continue in 2025 or 2026H1, and produces no
  Promotion candidate. No research Artifact was added, deleted or rerun.
- Agent, Factor Optimization, Qlib, Tushare, network and Promotion calls for
  the correction are all zero.
- The only recommended next task is `QM2-R1-002 — PIT Fundamental and
  Regime-aware Factor Iteration v1`.

## Expanded-feature Agent factor research

- `QM2-R1-001` is complete. Read
  `docs/quantmind2/contracts/EXPANDED_FEATURE_AGENT_FACTOR_ITERATION_V2.md`
  before continuing Factor research.
- Feature Catalog v2 is `tfc2_7d996ee8...21c21e`, Fixed-100 Dataset v2 is
  `tfd2_ee90879c...2e407`, and no Tushare network or retired data was used.
- Six external Agent rounds admitted 12 Templates and completed 38 parameter
  Trials plus 50 formal Qlib calls. Only `fi_e2dd6057...d8576f` passed all
  gates. Its Lock is `afcl_27fb695b...ba51e`; final Experiment is
  `afi2_78fe3138...7fcf`.
- The Candidate is `research_registered` only. Its 2025 and 2026H1 CSI300
  excess is negative, so the assessment is `mixed`; do not describe it as
  Fresh Validation, Frozen evidence, Promotion or production Alpha.
- Contract revision 2 immutably supersedes preliminary records only to add
  readable canonical DSL. Exact replay selects the unique highest revision
  and performs zero Agent, Optimization, Qlib, network or Store writes.
- No successor task is authorized. Wait for an explicit task contract.

## Strategy optimization completion and next task

- `QM2-P0-017` completed 96/96 formal Qlib parameter Trials over four locked
  Unified Signals. Read `docs/quantmind2/contracts/STRATEGY_OPTIMIZATION_V1.md`
  before further strategy work.
- Current Study is `sos_e504d537...10687`, Result is
  `sor_2c7803f0...b8628`, Strategy Registry is `srr_58f3e455...023d13`, and
  the four Candidate Locks are `spcl_1512373e...37531`,
  `spcl_099b055b...10fbc`, `spcl_d4760d57...7abe0` and
  `spcl_9228c11b...85c4e`.
- The Locks select TopK/n_drop/rebalance values `20/0/5`, `20/5/5`,
  `30/5/10` and `20/5/10`. They are retrospective contaminated research
  candidates, not validated, approved, active or production-ready.
- 2025 and 2026H1 were evaluated only after locking and were never used for
  selection. Every candidate underperformed CSI300 in both periods and every
  candidate is parameter-unstable. Do not use these results for Promotion.
- Store Inventory `sai_a0dbf127...cf5f5` is healthy at 270 artifacts / 2,468
  blobs with zero missing/unreferenced. Exact replay makes zero Qlib, Agent or
  Factor Optimization calls.
- The only next task is `QM2-P0-018 — Strategy Risk and Validation Gate v1`.
  It may introduce risk constraints and a Strategy Validation boundary only
  under a new explicit task; it must not auto-approve or activate a strategy.

## Current authority and next task

- `QM2-P0-016` implements Unified Signal and Strategy Layer v1. Read
  `docs/quantmind2/contracts/UNIFIED_SIGNAL_V1.md` and
  `docs/quantmind2/contracts/STRATEGY_LAYER_V1.md` before strategy work.
- Final equal-weight signal is `usa_4c824a58...9fab0`; final Strategy Registry
  is `srr_a2d226d4...ea503`. The Registry has four research-only completed
  backtests and no approved or active strategy.
- Absolute and CSI300-relative results are canonical. Fixed-100 affected
  metrics remain noncanonical. Do not use them for ranking, optimization or
  Promotion.
- Historical successor `QM2-P0-017` is now completed as recorded above. Its
  immutable P0-016 baseline remains the TopK20/n_drop5/five-session comparison
  point and was not rewritten.

- Current task is `QM2-P0-015H`; it is blocked because the live Tushare account
  cannot supply issuer announcements or structured cash/conversion/merger
  settlement fields for both 2025 terminations. Do not supplement this gap
  with web, remembered news, manual ratios or another Provider.
- Active provider is `tushare-pro-v1`; legacy provider
  `quantmind-production-feature-snapshots-v1` is `retired_and_purged` and may
  not be used by formal runtime. Read ADR-0011 and
  `docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json` before data work.
- Fixed universe IDs are `tu500_fb547c...24e8c` and
  `tu100_078e6609...2c526`; formal Qlib view is `tqv_c489efe4...941ff`.
- Canonical research start is empty Genesis Registry
  `trg_0e23d0c7...1d309`. Do not restore old Factor Registry metrics or old
  Research Memory effectiveness labels.
- Artifact Store Inventory `sai_ff1a263a...faee2` is healthy at 49 artifacts /
  1,607 blobs with Missing 0, Unreferenced 0 and legacy Artifact count 0. The purge is irreversible for
  the deleted local data; rollback means re-fetching/rebuilding Tushare data or
  restoring old data from an independent backup, not changing the authority
  record silently.
- No successor is authorized by this task. A future explicitly authorized
  Corporate Action Provider is required before Fixed-100 2025 or full-period
  benchmark-relative metrics can become canonical.

## Repository state

- QuantMind root: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`
- Base before QM2-P0-012F: `32dc6af0be24468da997e9e32e9627e23d360987`
- Current latest commit: the commit containing this handoff; resolve it with
  `git log -1 --format=%H -- docs/quantmind2/context/HANDOFF.md`.
- Dirty before QM2-P0-012F: no
- Unrelated dirty files: none
- Uncommitted work after the QM2-P0-006 commit: no

## Official Factor Lab source

- Root: `/tmp/quantmind_factor_lab_real_bounded_v7_orchestrator_v1/`
- Source: `/tmp/quantmind_factor_lab_real_bounded_v7_orchestrator_v1/backend/services/engine/factor_lab/`
- Branch: `factor-lab/real-bounded-v7-orchestrator-v1`
- Commit: `c83192c2278767e03f008bc39197b1ba33bfb6a9`
- Its source bytes remained read-only during QM2-P0-002B1. The supplied `/tmp`
  root had no `.git` directory, so the expected branch/commit and Git-clean
  claims could not be reverified locally; a before/after content digest was
  used for the task boundary instead.

## Current position

- Corporate-action Raw Snapshot `tsca_raw_c8c04e...91b13`, normalized Event
  Set `scae_a90b3726...abd1f` and Benchmark Contract
  `fubc_e1885a79...513e4` are immutable. Exact replay performs no network,
  Qlib, Agent or Store writes.
- Live capability evidence shows `stock_basic`, `daily`, `namechange`,
  `suspend_d`, `share_float`, `dividend` and `major_news` metadata available;
  `anns_d`, `merge` and `merger` are unavailable for both symbols. News
  metadata is not an issuer announcement or structured settlement source.
- Both events have `evidence_missing`; all settlement fields are null. The
  Fixed-100 2025/full-period benchmark and related excess metrics remain
  noncanonical. Block reason is
  `TUSHARE_CORPORATE_ACTION_EVIDENCE_INSUFFICIENT`. No benchmark revision
  exists. Strategy NAV, trades, CSI300,
  2019--2024, 2026H1 and Promotion state are unchanged.

- Termination audit `htf_4a0762a5...ba6c3f` proves all four strategy paths are
  flat before both security terminations. `600837.SH` was never held;
  `601989.SH` was exited by the combination on 2025-07-11 and Candidate 1 on
  2025-04-21, before its 2025-08-12 last market day. Strategy absolute and
  CSI300-relative results therefore remain canonical.
- The Fixed-100 benchmark had 1/100 and 1/98 unit-notional exposure at the two
  last market dates and then silently re-normalized observable members. Since
  no governed settlement exists, its 2025/full-period return and all affected
  strategy excess metrics are noncanonical and forbidden for Agent feedback,
  factor ranking, parameter choice or Promotion.
- `SecurityTerminationPolicyV1` is generic and contains no stock-specific
  rule. It forbids inferred last-price sale, zero return, stale valuation,
  cash or conversion. The immutable audit exact-replays with zero Qlib calls.

- `QM2-P0-015F` proves that `600837.SH` and `601989.SH` are status-D members
  delisted before 2026H1. The fixed 100-member identity and Qlib instrument
  lines remain intact; daily active membership is 98 and observable/tradable
  membership ranges from 96 to 98.
- Lifecycle policy `fulp_60672b83...a632a` uses an observable-cell signal
  denominator and a pre-frozen capacity minimum of 25 (`topk + n_drop`). All
  2019--2025 signals, positions and formal metrics retain parity. No universe,
  candidate, parameter, strategy, market data, or signal changed.
- 2026H1 formal Qlib completed for all three candidates and their equal-weight
  combination. Combination net return is -5.84%; it trails CSI300 by 10.11
  points and beats the lifecycle-aware fixed-100 benchmark by 6.22 points.
  These are retrospective historical results, not Fresh Validation or
  Promotion evidence.
- Follow-up revision 2 `thf_9f389863...7307b2` exact-replays with zero Qlib
  calls and zero new Store objects. It explicitly supersedes immutable
  preliminary follow-up `thf_39155cdb...d498d6`, which omitted per-strategy
  Calmar and lifecycle summaries. Store inventory `sai_ee866a1b...78e6` is
  healthy at 45 artifacts / 1,589 blobs. Original P0-015 remains immutable and
  partial.

- `QM2-P0-015` completed all four Tushare historical-as-of Agent rounds. The
  formal run used four calls and 18 Trials; an earlier immutable failed
  diagnostic used four calls, so the task consumed exactly its eight-call
  maximum. Eight candidates were round-locked before evaluation.
- Round mean next-year RankIC is -0.00213 / 0.00358 / 0.00191 / 0.00331 and
  fixed-100 net excess is -4.41% / 3.41% / 0.93% / 15.99%. Assessment is
  `mixed`; rounds 2--4 did not continuously improve over round 1.
- Three candidates were selected using only 2021--2024 evidence. The 2025
  equal-weight result is +4.23%, but trails CSI300 by 17.52 points and
  fixed-100 by 2.85 points. Individual 2025 returns are -4.32%, +1.62% and
  -7.41%.
- All isolated 2026H1 signal NaN ratios are 0%. Formal Qlib still rejects the
  interval at its unchanged 100-symbol quality gate because only 98 symbols
  have effective observations. This is retained as rejected evidence; no
  fill, replacement, deletion, fallback, threshold change or promotion was
  performed. Do not quote the successful full-range result as isolated
  2026H1 performance.
- Final Experiment `tha_2b367621...76383b` exact-replays with zero Agent,
  Optimization, Qlib, Registry, Tushare-network or legacy reads. Store is
  healthy at 43 artifacts / 1,580 blobs with zero missing/unreferenced.

- `QM2-P0-011BF` is a completed diagnostic with a blocked backtest outcome.
  The original 35.17% is exactly 3,822 NaNs / 10,867 observed rows. A full
  100-symbol x 111-date grid has 4,055 missing cells / 11,100 (36.53%): 222
  from two wholly absent symbols (`SH600837`, `SH601989`), 11 local row
  absences, and 3,822 missing `style_idio_vol_20` values across all 98 observed
  symbols and 39 dates.
- Both locked Factor Values artifacts reproduce exactly and all Factor DSL,
  orientation, normalization and combination steps add zero NaNs. The derived
  Qlib view reaches 2026-06-24, has 100 instruments and adds no join, date,
  symbol or score loss. This is an upstream Feature-data-quality boundary, not
  a Qlib or combination defect.
- No safe repair was made: recreating the missing authoritative Feature would
  change research data semantics without sufficient provenance. The 20% gate
  remains unchanged, Qlib rerun calls are zero, and original 011B artifacts
  remain immutable.
- An unchanged, out-of-scope Artifact Store concurrent-import test exposed a
  timing-sensitive Receipt ID conflict in the final broad regression and two
  focused reruns; the archived base tree passed one isolated run. Do not call
  it fixed or attribute it to the signal audit. No production Store concurrency
  code was changed in 011BF.
- Store Audit `sma_33979ef...a9b64`, blocked follow-up
  `hbf_fc927bc...6e1f1`, and Inventory `sai_39e8526...42f2` are current.
  Store state is 97 artifacts / 372 blobs, healthy, zero missing/unreferenced;
  cold recovery and exact-existing replay passed.
- Current task is `QM2-P0-011BF`; status is `blocked`. No successor task is
  authorized by this contract.

- `QM2-P0-011B` is a truthful partial historical diagnostic. Fixed Universe
  `ful_e899c9ce...df2651`, Dataset `fuhd_734dae...f95fb`, final Historical
  Experiment `hae_5e4b11ba...3fedd` and Qlib result
  `qbr_b8be0692...f9dc0` are immutable Store artifacts.
- Four formal external rounds used four Agent calls and 14 factor-only Trials;
  a discarded preflight dataset run used four more calls, keeping the task at
  its eight-call ceiling. Round 2 admitted no Proposal and Round 4 next-year
  RankIC was negative. The Agent assessment is `mixed`.
- Two candidates were locked using evidence only through 2024. 2025 completed
  with about 2.6% net return for each candidate but about -4.4/-4.5 percentage
  points fixed-universe excess. 2026H1 Qlib execution was rejected by the
  unchanged signal-quality gate (35.17% NaN versus 20% maximum). Do not fill,
  reselect, relax the gate or call this Fresh evidence.
- Inventory `sai_8ee9085f...c4ee` has 93 artifacts / 357 blobs. Cold recovery
  and exact replay passed with zero Agent/Optimization/Qlib/Registry calls and
  zero new artifacts/blobs. Production Registry and Fresh control identities
  did not change. No successor task is authorized; ask for an explicit task
  that addresses or accepts the 2026H1 coverage boundary.
- Final read-only verification found no Factor Lab source file at its official
  `/tmp` path (only a `__pycache__` entry). The earlier normalized digest cannot
  be reverified; this task did not write or consume that tree.

- `QM2-P0-012F` aligned the external Agent with the unchanged Proposal
  parameter contract. Campaign `rc_4432a5d3...c04b56` completed after one real
  `openai_codex_cli` / `gpt-5.6-terra` call and no repair. It produced Decision
  `rd_142a0fa4...ab9838`, Template `ft_115afad9...70aef1`, Study
  `fos_22c2f3b6...e8a84`, six successful Trials, selected Factor Values
  `fv_937e5df1...571a`, Development result `der_b8669e6...9a92e`, and Registry
  successor `frs_9f61af9b...92052`.
- The new Registry has 20 entries and adds one `research_registered` factor;
  promotion / approved / active remain 0 / 0 / 0. The 2025 Development result
  is contaminated adaptive research only and creates no Validation, Frozen,
  Fresh or promotion evidence.
- Current Inventory is `sai_820983db...e5e68`, 79 artifacts / 339 blobs,
  healthy with zero missing and zero unreferenced. Empty-cache graph recovery
  passed. Exact replay returned the identical Campaign/Result/Descriptor with
  zero Agent, Optimization and Registry-write calls and no Store delta.
- Three earlier P0-012F Goal/Campaign identities are preserved as immutable
  diagnostics: `rc_29c2c3c9...c3655` (Provider rejected nested `oneOf`),
  `rc_01e211af...fcc47` (nested `anyOf`) and `rc_0cd43051...4cfe7`
  (`uniqueItems`). Each stopped after the fixed two-call ceiling and created no
  Decision, Trial or Registry entry. They explain why Provider transport uses
  the supported explicit-values profile while Control retains the full formal
  Search Space validation.
- P0-012 Campaign `rc_16bf5717...b7ea` remains immutable partial with two
  calls and no admission. Do not describe P0-012F as changing that result.
- Latest Run after this task is the `QM2-P0-012F` Run under
  `docs/quantmind2/implementation/runs/2026/2026-07/`. The only next task is
  `QM2-P0-011B — Fixed-100-Universe 2019—2026 Agent Iteration and Historical
  Backtest`. Conditional `QM2-FV-001` remains forbidden until 60 mature
  post-lock trading dates exist.

- `QM2-P0-012` is a truthful partial production dry run. Campaign
  `rc_16bf5717...b7ea` made exactly two real Codex CLI calls (the second was
  the sole repair); both exited 0 but failed the unchanged Proposal parameter
  contract. It produced no Decision, admitted Proposal, Trial, Development
  result or Registry successor. Do not retry it, widen its budget, or describe
  it as an AI factor discovery.
- The partial Campaign is immutable in Store descriptor
  `sad_2e42bc...7b18b`. Current Inventory is `sai_b0c03807...70320` with 66
  artifacts / 287 blobs, healthy and zero unreferenced. Cold recovery and exact
  replay passed; replay called Agent/Optimization zero times and wrote no
  Registry or Store artifact. Canonical Registry remains
  `frs_c2ef675c...0237b5`, 19 entries, with promotion / approved / active =
  0 / 0 / 0. Fresh remains 0/60.
- Latest Run is `QM2-P0-012-20260717T180925Z-ded5c10`. The only next task is
  `QM2-P0-011B — 2019—2026 Historical Diagnostic Backtest`. Conditional
  `QM2-FV-001` stays forbidden until 60 mature post-lock dates exist.

- `QM2-P0-011` cuts the formal research runtime to `store_required`. Read
  `ARTIFACT_BACKED_RUNTIME_V1.md`, `ARTIFACT_RUNTIME_RECOVERY_V1.md` and
  `ARTIFACT_RUNTIME_ROLLBACK_V1.md` before changing runtime behavior.
- In QM2-P0-011, Store-only empty-cache recovery passed for Factor Values, Optimization,
  Validation, Frozen, canonical Registry, both Campaigns and Fresh Admission.
  External Campaign replay called neither Agent nor Optimization and wrote no
  Registry state. Its Store baseline was healthy at 65 artifacts / 280 blobs on
  Inventory `sai_a0b9e618...55d312`.
- Canonical Registry remains 19 entries with promotion / approved / active =
  0 / 0 / 0. Fresh remains `awaiting_first_fresh_date` at 0/60; no Fresh Result
  exists. Legacy local mode is emergency-only and cannot publish formal results.
- This predecessor state is preserved for historical context.

- `QM2-P0-010` adds persistent Research Artifact Store v1. Current inventory
  is `sai_a0b9e6183a7bed95d9dbcce918a19c9e2f63a67ffbc7617a2091b7a37955d312`;
  reachability plan is `rap_f3aca751ad751c976888fd9b464f9f56dd4913339b226786c0c3a7ef65ccc247`.
- All 65 current reachable artifacts migrated with zero missing sources and
  healthy integrity. Read `RESEARCH_ARTIFACT_STORE_V1.md`, migration and
  recovery contracts before runtime cutover work.
- The original immutable `QM2-P0-010` Implementation Run remains
  Git-inconsistent and non-indexable because only its own Manifest is absent
  from `integrity.git_changed_paths` and `git_added_paths`. The independently
  verified Git inventories contain 42 changed and 28 added paths. Its 41
  business ChangedFiles remain correct: the Manifest is excluded and the
  Report is included.
- `QM2-P0-010F` publishes correction evidence only, with one `corrects`
  relationship. It changes no Store behavior or research artifact identity.
  Latest run: `QM2-P0-010F-20260717T161330Z-77f5b1f`.
- Runtime cutover successor `QM2-P0-012` is the partial dry run recorded above;
  Fresh evaluation is still 0/60 and must not run.

- Architecture: QuantMind 2.0 Architecture v1, frozen.
- ADR-0009 and Research Decision Contract v1 are accepted architecture facts.
- They do not represent implemented Skill, Decision Validator, permission
  guard, state machine, budget controller, or Code Orchestrator runtime.
- Official V7 Factor Lab remains Python-first and does not yet satisfy the
  formal Decision-Control-Execution separation.
- Previous task `QM2-P0-010F` recorded immutable Git inventory correction
  evidence for the Artifact Store implementation Run.
- Completed predecessor: `QM2-P0-008 — Agent Research Campaign v1` remains
  historically partial because its external attempts failed.
- Latest correction run: `QM2-P0-010F-20260717T161330Z-77f5b1f` under
  `docs/quantmind2/implementation/runs/2026/2026-07/`.
- Persistence conclusion: future Ledger access should use SQLAlchemy 2.0 async,
  the shared master engine/session manager, API-owned metadata, versioned
  transaction-wrapped PostgreSQL SQL, and an explicit `quantmind2` schema.
  Migration invocation and rollback are implemented. The async PostgreSQL
  Repository and explicit UoW now reuse the shared manager's engine/sessionmaker;
  Repository methods never own transaction completion.
  Production deployment and final schema privilege policy remain unconfirmed.
- Immutable Ledger domain objects, stable enums, structured errors,
  side-effect-free validators, Run state invariants, and direct relationship
  conflict checks now exist under `backend/services/engine/project_knowledge/domain/`.
- Synchronous Repository Protocols, query objects, stable errors, full
  in-memory graph-cycle checks, expected-version behavior, append-only details,
  stable history queries, and atomic-batch contract tests now exist.
- `InMemoryLedgerRepository` is a test double only; it is not production
  persistence or an implementation fact source.
- API-Base static ORM records now map Task, Run, RunRelationship, ChangedFile,
  ChangedSymbol, TestExecution, ImplementationArtifact, ComponentReference,
  ArchitectureDecisionReference, Limitation, and RecommendedTask to eleven explicit
  `quantmind2` table shapes. PostgreSQL DDL compiles without a database connection.
- All current target ORM mappings and explicit bidirectional Domain mappers
  exist. Migration `0001` and the async PostgreSQL Repository/UoW are complete.
  Exact replay/conflict, expected version, finalization, append-only children,
  recursive-CTE/advisory-lock DAG admission, typed history, and atomic batch
  behavior pass isolated PostgreSQL 15 tests, including independent Sessions.
  Manifest Parser/Indexer, Git consistency service, trusted binding, and CLI
  now exist. API and UI do not exist.
- Limitation does not foreign-key Component Catalog; RecommendedTask does not
  foreign-key, create, or execute a future Task. Neither historical annotation
  has an ORM update method, and no annotation data was written.
- Mapper Contract v1 covers all eleven objects. The complete explicit Mapper
  package implements pure conversion, safe errors, round trips, and frozen
  `changed-file-v1` / `changed-symbol-v1` identities. It has no database runtime.
- Manifest v2 is the default for future Runs. It separates logical repository
  identity from execution path, declares Mapper/identity versions, and carries
  every current Ledger Domain family. ADR-0010 and the Indexer still require an
  explicit trusted binding. Manifest v1 remains immutable compatibility only.
- All eleven objects now have explicit `to_record` and `from_record` functions.
  Stored ChangedFile/Symbol technical IDs are recomputed and verified; explicit
  parent Run IDs cannot disagree with Domain values. Task/Run version behavior
  remains unchanged. Parser, binding, Git consistency, and Indexer exist; API
  and UI do not.
- At the B1 base, 17 historical Manifest v1 Runs exist: 16 pass mandatory Git
  evidence and zero form complete Domain Bundles. It did not invent missing
  Task/child facts and did not claim a historical backfill. The 001F Run fails
  result-commit consistency. A complete synthetic bundle passed isolated
  PostgreSQL insert, replay, immutable-conflict, and rollback verification.
- ADR-0010 requires explicit caller binding from logical repository ID to local
  worktree; v1 absolute paths remain informational execution evidence.
- The B1 v2 Run passes committed Git consistency and complete Domain Bundle
  construction, and is fully indexable with all eleven families in isolated
  PostgreSQL. Exact replay and immutable-conflict rollback are verified.
- Ledger infrastructure is closed. Production deployment/backfill, API/UI,
  watcher, webhook, and daemon remain absent.
- Dataset Snapshot v1 now provides explicit Provider requests, immutable Raw
  Capture, deterministic normalization, blocking quality checks, atomic
  Parquet publication, identity/hash validation and a read-only consumer seam.
- Real TDX is not verified: legacy scripts depend on absent `tqcenter`; pytdx
  and mootdx are absent; source volume/amount units are not evidenced. No real
  Snapshot ID exists. Fake Snapshots are test-only and explicitly identified.
- Existing training remains on feature snapshots and Qlib remains on its
  separate binary view. No production consumer switch occurred.
- The production feature source is explicitly bound read-only as logical source
  `quantmind-production-feature-snapshots-v1`. The latest complete 2025 bytes
  hash to `7fd0316e6f8d936688ef332357fb7589f64c0e127c5f64e3158c584baf28b00f`.
- Real Legacy Snapshot
  `ds_bc82e7bb2c63d2c47677b11cf0f4fc1e5aa11a0ed18ee0bb27e3c8ab667d2ee7`
  contains 5,931 rows, 100 deterministic symbols, 60 observed dates, all 152
  legal research features and zero labels. Default readers cannot expose labels,
  forbidden or unknown columns.
- Production loader parity passed with only its existing numeric-to-float32 cast
  allowlisted. Source and Snapshot values/NaN masks otherwise match exactly.
- Factor DSL must consume validated Snapshot terminals through
  `load_feature_matrix`; it must not read the legacy root or labels directly.
- New v2 Runs must omit their own Manifest from `changed_files`; the Manifest
  remains in integrity Git inventories. Report remains a ChangedFile/Artifact.
- Historical 003L is immutable and uses the generic compatibility warning
  `LEGACY_V2_MANIFEST_SELF_REFERENCE_IGNORED`; its Manifest is not mapped to a
  ChangedFile, while every other Git/hash check remains strict.
- The 003LF test-only assertion now uses `AnalyzedRun.evidence.consistent` and
  `evidence.warnings`; all four opt-in PostgreSQL tests pass without a
  production-code change. Ledger remains closed.
- `QM2-P0-004 — Factor DSL v1 on Real Legacy Feature Dataset Snapshot` now
  provides a closed typed JSON AST, strict feature/parameter
  admission, canonical Template and Instance identities, deterministic
  Snapshot-only execution, and immutable Factor Values artifacts.
- Five parameter instances passed on the real 003L Snapshot with 5,931 rows
  each and exact replay. This is compute evidence, not factor validation,
  Registry status, model value, signal or backtest evidence.
- Factor Optimization v1 now admits only declared `lookback_window` and
  `factor_internal_weight` parameters, enumerates deterministic finite Study
  products under trial/failure budgets, executes or replays existing Factor
  Values, evaluates mechanical quality, and atomically publishes immutable
  Study/Trial artifacts.
- Real Studies
  `fos_969d431e553ad29d1d7bcdd4d912a6ab92471b5c4faf833a18abe2607baa1cb2`
  and `fos_ac8ea3539ba0db8faa4dc223750d649584da270244ec022638faef8bdfeb5a19`
  completed 5 plus 9 trials; all 14 were mechanically eligible and exact Study
  replay passed. Their ordering is not predictive evidence.
- No label, IC/RankIC, return, model, Qlib, signal, backtest, structure
  evolution, random/Bayesian, model, or portfolio optimization was introduced.
- Factor Validation v1 audited current production label behavior and created
  Dataset `vd_1ac71a8b...c3ed62`, full-period Factor Values for all 14 Trials,
  Result `fvr_b9f247e4...c51ab0`, Selection `fvs_f679a630...819e9c`, and Frozen
  Result `fvt_734478fc...21c787`. Four Trials passed Validation gates; only the
  top three were frozen. 2025 remains quarantined and was not used in formal
  metrics. Frozen results did not feed selection or Optimization.
- The original Run remains Git-inconsistent: its immutable Manifest records
  `11db9e00e1babe...` for the pre-change `handoff_v1.schema.json`, while raw
  bytes from base commit `07a3df9e...` hash to `11db9e00e1aabe...`.
  `QM2-P0-006F` preserves that history and adds the correct value as a strict
  evidence-correction Artifact with a `corrects` relationship. It does not
  rewrite the old Run or change Dataset, Validation Result, Selection or
  Frozen Result identities.
- Factor Registry v1 registers 14 real Instances in Snapshot
  `frs_436f4a966ea0c00ee2182c665813cd74cc13bb900a7022604ad9efc26849f2d9`
  under Policy `fpp_6ca41655ea0ec5692ef2799674ef743a8bf91a6cf58718e124163bf033e255a3`.
  Statuses are 10 Validation-rejected, one passed-not-selected, and three
  Frozen-rejected; candidates, approved and active are all zero.
- Registry is immutable offline artifact authority only. No Registry database,
  API/UI, durable backend, active Factor, LightGBM/Qlib consumption or backtest
  was introduced. Agent may read filtered failure history but cannot mutate,
  approve, activate, or access Frozen details.
- Baseline Campaign `rc_4970d141...19cd5f` produced four new research-only
  Registry entries after 12 real Trials and contaminated 2025 Development
  evaluation. Registry before/after: `frs_436f4a96...f2d9` →
  `frs_d40bfd74...584718`; no promotion candidate, approved, or active entry
  was added.
- External Codex Campaign `rc_c9c7a98...3bca43` is partial: two bounded real
  CLI attempts returned exit code 1 before structured output, so it spent no
  Trial budget and changed no Registry state. This must not be described as an
  external AI factor proposal.
- QM2-P0-008F identifies `invalid_json_schema` as the old root cause and keeps
  the ResearchDecision contract unchanged while adding Provider-schema type
  normalization and classified safe diagnostics in `CodexResearchAgent`.
- External Campaign `rc_0b13d7f...d9401c` used Codex CLI
  `0.145.0-alpha.18` with explicit `gpt-5.6-terra`, admitted one Proposal,
  completed four Trials and contaminated Development evaluation, and published
  one `research_registered` entry in Registry `frs_7ab0a844...01054`.
  Exact-existing replay made zero additional Agent calls; promotion candidate,
  approved, active, Validation evidence and Frozen evidence additions are zero.
- Baseline and External Campaign Registry snapshots are sibling branches. The
  unique current canonical Registry is
  `frs_f0a08cc472270cf80f2ae8c1141de17871dacbe2edccba8eb4ffe05ca45d3ba4`
  with 19 Entries and reconciliation
  `frr_9112702e368326365d6f4adb144633c7d0cf3ae59baa61ed76270ae86e93cb32`.
- Fixed Development-evidence admission result
  `fvar_89e61fe674bff1d10d46c9bea3913a456f236bbc191578291529736480a831ab`
  admits three of five Agent-generated candidates; the external factor is not
  admitted. This is not Fresh Validation or Frozen evidence.
- QM2-P0-009 locked three admitted candidates on market date 2026-07-17 under
  Candidate Lock `fvcl_716d7465...63c7b`, Protocol `fvp_93163e1b...5a867`,
  Exposure Ledger `rdel_56d95b7...5f5ff`, and Watermark `fdw_3459fb5...aa248`.
  The real source ends 2026-06-24; eligible count is zero and status is
  `awaiting_first_fresh_date`. Registry successor `frs_c2ef675...0237b5` adds
  awaiting-data evidence without changing main status. No historical backfill
  or real Fresh result exists.
- The original QM2-P0-009 Run remains Git-inconsistent/non-indexable because 23
  business ChangedFiles were omitted. QM2-P0-009F records the complete 35-entry
  Git-derived inventory as immutable correction evidence with `corrects`; it
  does not edit the original Run or research controls.
- Recommended next task: `QM2-P0-011B — 2019—2026 Historical Diagnostic Backtest`.

## Unconfirmed facts

- Authorized `tqcenter` runtime/client and daily-bar volume, amount, adjustment,
  timeout, rate-limit and license semantics remain unavailable, but no longer
  block the Legacy Snapshot to Factor DSL route.
- The active production database feature allowlist was not queried; the provider
  is bound to the checked-in 152-enabled-feature catalog.
- The adjacent 2025 source sidecar is stale relative to current Parquet bytes.
- Long-term durable location for the official Factor Lab source.
- Production execution-role permission policy for the explicit `quantmind2` schema.
- CI capability and scheduling for the opt-in disposable PostgreSQL test.
- Final artifact storage backend for large snapshot and ledger artifacts.
- Concrete actor identity and permission policy for ResearchDecision.
- Persistent idempotency-key and semantic-duplicate policy.
- SQLAlchemy 2.0.25 / asyncpg 0.29 pinned-runtime behavior;
  A2a1/A2a2a/A2a2b1/A2a2b2 static verification used an existing SQLAlchemy
  2.0.51 environment and A3 used SQLAlchemy 2.0.51 / asyncpg 0.31.0.
- Production schema privileges and CI execution remain unverified; local
  ordering, checksums, rollback, reapply, parity, and cleanup are verified.

## Constraints that must not be broken

- Do not replace LightGBM or Qlib.
- Do not put Python `factor_impl.py` in the v1 standard factor path.
- Keep Factor, Model, and Portfolio optimization separate.
- Keep Research Memory, Project Architecture Memory, and Implementation Ledger separate.
- Do not expose Frozen Test to Agent, Optimizer, or Campaign Memory.
- Do not treat plans, mocks, fixtures, fallbacks, or temporary evidence as implemented production facts.
- Do not modify accepted ADRs silently.
- Decision Layer may propose actions but cannot claim execution success.
- Code Orchestrator is the only controlled boundary to execution services.
- Execution services cannot autonomously choose the next research action.

## Next-session read order

Read `CONTEXT_INDEX.md`, Project Charter, Architecture v1, Current State, this
Handoff, task-related ADRs, Component Catalog, the latest relevant
Implementation Run, then current code, Git state, and tests. For research-loop
tasks, also read ADR-0009 and `RESEARCH_DECISION_CONTRACT_V1.md`.

## QM2-R2-004 handoff

Task `QM2-R2-004` is completed uncommitted at base
`38af464809d2bec14ea9284a4e2ba6e634f61d3b`. Read
`AUTONOMOUS_TECHNICAL_FEATURE_FACTORY_AND_ARCHETYPE_ALPHA_V1.md` after the
R2-003 Program contract.

The authoritative new research objects are Catalog
`tfc2_229f19...cf5e6`, Program Spec `aap1_30e59b...cd0100`, Union Lock
`aausl1_47e182...27d239`, FDR `amtc1_fae10b...dd7d1` and terminal Report
`aapr1_e344e1...f4f6e3`. The final result is zero Validation Survivor; do not
describe any object as approved, active, production or Fresh validated.

The first immutable Program attempt `aap1_dd9044...42f197` reached a zero
shortlist with no Qlib because an implementation date-type boundary blocked
admitted evaluations. It remains immutable diagnostic evidence. Revision
1.0.1 fixes the general boundary and is the final formal result; it does not
rewrite the earlier Store artifacts.

## QM2-R2-005 handoff

Read `AUTONOMOUS_RESEARCH_SUPERVISOR_AND_PROJECT_FRESH_VALIDATION_V1.md`.
Project evidence through 2026-07-23 is `retrospective_research_only`.
Supervisor Spec `arsv1_1d07cf5c...abd14e`, Ledger
`peel1_f96c3595...a7c7eb`, Queue `arq1_1982ce71...29e71f`, Cycle
`arc1_58325bd9...cb2c8b` and Report `arsr1_3cc6becd...91666a` are the
authoritative new objects.

The first Cycle produced zero Retrospective Candidates and therefore zero
Supervisor Fresh Locks, Cohorts, observations and Registry writes. Incremental
data was not requested because no active Supervisor Fresh Candidate exists.
R1-010 remains an independent Fresh protocol and is not pooled into Supervisor
Cohort statistics. Promotion requires a separate human-authorized task.

## QM2-R2-006 handoff

Read `TECHNICAL_DSL_OPERATOR_EXTENSION_V1.md` after the R2-004 and R2-005
contracts. Six rolling operators and six PIT primitives are now the accepted
bounded technical extension. Factory 002 produced Catalog v3
`tfc3_b903c85e...23aea` from 10 Agent calls, 26 proposals and 20 unlabeled
admissions/materializations.

Supervisor Cycle 002 `arc2_78b9b6c...3266` consumed Catalog v3 and completed
18 Alpha Agent rounds plus 68 formal Qlib calls. It produced no Retrospective
Candidate, Fresh Lock or Cohort. Historical evidence remains
`retrospective_research_only`; no Registry or Promotion write occurred.
Terminal status is `waiting_for_fresh_data_or_novel_space`, Store integrity is
healthy, and cold recovery/resume/exact replay return all call/write counters
as zero. No successor task is authorized.

## QM2-R2-007 handoff

Read `FIXED_CONFIGURATION_MODEL_ALPHA_PROGRAM_V1.md` after the R2-004 through
R2-006 contracts. Model Spec `fcms1_27c710...7ad94`, Walk-forward Spec
`pwfs1_6a226e...0a7d9`, Leakage Audit `mtla1_cf3aec...c1f97` and global
multiple-testing Artifact `mmtc1_659e9d...aef6f` are authoritative.

All three preregistered Bundles completed four purged 2021--2024 outer Folds,
three fixed seeds, 54 LightGBM training calls and 18 formal Qlib calls. The 2025/2026H1
objects are contaminated reports only. All Bundles failed the unchanged
RankIC gate and BH FDR; Candidates, Distillation entries, Fresh Locks, Fresh
Cohorts, Registry writes and Promotions are zero.

Cycle 003 is `completed_no_model_candidate`; global authorized technical
research-space exhaustion is active and Cycle 004 was not created. Do not
reinterpret the positive annual portfolio excess of some Folds as a model
Candidate: the daily official-label RankIC and FDR contracts failed. Exact
replay, Supervisor replay and cold validation are zero-call with healthy Store
integrity. No successor task is authorized by this contract.

## QM2-R2-008 handoff

Read `MULTI_HORIZON_LABEL_ALIGNMENT_RESEARCH_V1.md` after the R2-007
contract. Label Family `trlf1_7370ec7d...04561c`, audit
`ela1_c48a0518...274ff`, global test `mhmt1_9ba1acf8...c7ddc`, terminal
Report `mhlrr1_53bae8de...b8550f`, two L1 retrospective Candidates and their
two no-backfill Fresh Locks are authoritative.

The complete formal matrix used the exact R2-007 Bundles, model parameters,
three equal-weight seeds, four expanding Folds and fixed Qlib strategy. It
completed 108 fits, 36 predictions and 36 Qlib runs. Only expanded and
de-correlated L1 combinations pass both the retrospective gates and the
single nine-hypothesis 10% BH FDR boundary. L5 and L10 are not supported;
long-horizon apparent improvement is not cross-year consistent.

This is retrospective evidence only. It does not replace the production
Label, register/promote a model, or authorize trading. Fresh data strictly
after 2026-07-23 is absent, so no Fresh Cohort result exists. Cycle 004 is
complete, Cycle 005 was not created, and no successor task is authorized.

## QM2-R2-009 handoff

Read `AUTOMATED_FRESH_MODEL_COHORT_V1.md` after the R2-008 contract. Cohort
`mfcc1_faab1ee6...7bde6dc`, first-seen Snapshot
`fms1_e0aaaf86...9f83e3`, and Heartbeat
`fmhr1_224de05e...f9fe42` are authoritative.

The formal calendar establishes 2026-07-24 as the Fresh start. Both frozen L1
Candidates have one prediction and no mature Label yet, so both remain
`fresh_evidence_accumulating`; the cohort-wide HAC/BH test is legally waiting.
The interrupted post-Snapshot run recovered without another Tushare request.
Exact replay and cold recovery have zero calls/writes, Store integrity is
healthy, and Registry/Promotion writes are zero.

The project-local scheduling contract exists, but no system scheduler was
installed or loaded. No successor task is authorized.

## QM2-R2-010 handoff

Read `FRESH_HEARTBEAT_LAUNCHAGENT_V1.md` and
`FRESH_HEARTBEAT_OPERATIONS_V1.md` after the R2-009 contract. Repository
implementation, manual heartbeat, exact replay, Store integrity, cold
recovery, lock/log/status contracts and uninstall behavior are verified.

Scheduler status `fhss1_9bbdf90c...22f53d2` and operational run
`fhor1_ebc67320...d8f5d4` reference the unchanged Fresh heartbeat
`fmhr1_224de05e...f9fe42`. Both Candidates and the Cohort remain
`fresh_evidence_accumulating`; Registry and Promotion writes are zero.

The host LaunchAgent is intentionally not installed or loaded. The real
RunAtLoad drill showed macOS background denial/blocking when the job reached
the repository and Python runtime under `~/Documents`. The failed Agent was
booted out and uninstalled, preserving logs and Artifacts. Do not claim
automatic scheduling until that host boundary is explicitly resolved and
reverified. Do not silently copy the virtual environment or business source
into Application Support as a workaround.

## QM2-R2-011 handoff

Read `IMMUTABLE_FRESH_RUNTIME_DEPLOYMENT_V1.md` and
`IMMUTABLE_FRESH_RUNTIME_OPERATIONS_V1.md` after the R2-010 contracts. This
task is the governed authorization to deploy immutable Git and validated
environment snapshots below Application Support. It changes no Fresh research
semantics.

The existing Store below `~/.quantmind2` remains canonical and is not copied.
Dynamic host truth must be recovered from
`deployments/current-deployment.json`, the latest
`fresh_runtime_deployment_status`, Scheduler Status and Operational Artifact.
Candidate B `mhrmc1_6b1a97e5...527c3`, Candidate C
`mhrmc1_83272b1d...56c23`, their Locks, Cohort
`mfcc1_faab1ee6...7bde6dc`, Label, Bundles and strategy remain unchanged.
