# QM2-R1-009 Implementation Report

## 1. Task Summary

- Task: `QM2-R1-009 — Momentum Tail-Alpha and Selection-Overlay Diagnostic v1`
- Result: completed, pending containing commit and post-commit Planner
- Base: `c071c0f02da89e1b5663a2fb32e26493bbe97ff9`
- Source study: `lfmsta1_18f3a4add9e0e224a7a8d35133af2dbfa9a23181edc94134d9c2c3738965ff80`
- Source Signal D: `lfmsa1_a4a99da30ef0dc99a03270bc5688f3edbe66bf944f899795d11aacf83a8e2262`
- Final diagnostic: `mtad1_308b26283cc78b37428b5527e69fd97f21c246746d5a0a908ff1c85571951951`

## 2. Goal, scope and frozen definition

The task determines whether immutable Signal D lacks Alpha or instead has a
nonlinear top-tail or regime-specific stock-selection profile. Signal D is
unchanged: `0.5*cs_zscore(momentum_120_20) +
0.5*cs_zscore(residual_momentum_60)`, orientation 1 and lag one. No Factor,
Agent, parameter/Top-N/frequency optimization, Candidate Lock, Registry state
or Promotion is created. 2021--2024 is the research interval; 2025 and 2026H1
are retrospective reports only and never participate in selection.

## 3. Metric contract

Formal annual RankIC uses the immutable R1-008 `model_label`. Decile, tail,
extreme-rank, decay, component and gross Top-N returns use adjusted-close
forward returns. Revision 3 persists these meanings separately and adds
component diagnostics; immutable revisions 1 and 2 remain historical Store
evidence. Q1--Q10 are daily cross-sectional buckets. Top 5/10/20/30 are fixed,
equal-weight, ten-session gross diagnostics with no n_drop and no selection.

## 4. Annual RankIC, tail and monotonicity

Values are formal label RankIC / adjusted-close T+1 RankIC / Q10-Q1 /
Q10-universe / full-decile monotonicity / extreme-rank IC.

| Period | Metrics |
|---|---|
| 2021 | .000530 / .009613 / .0599% / -.0309% / .4788 / .012353 |
| 2022 | .005675 / -.002805 / -.1467% / -.0840% / -.7091 / -.010557 |
| 2023 | -.015063 / .013780 / .0150% / -.0065% / .0788 / .013418 |
| 2024 | .008318 / .041022 / .1501% / .0765% / .7212 / .052510 |
| 2025 | -.011491 / -.005757 / -.0487% / -.0030% / -.2606 / -.011112 |
| 2026H1 | .013022 / -.002846 / -.0575% / -.0449% / -.0182 / -.014967 |

Formal and adjusted-close RankIC differ because the inherited model label is
the existing next-open label. Tail metrics do not replace that formal gate.
Across the research years Q10 exceeds the observable universe only in 2024;
the 2023 positive Q10-Q1 is caused by Q1 being slightly worse, not Q10 being
an absolute or universe-relative winner. The full and top-half ordering is
unstable rather than a clean U shape or monotonic curve.

## 5. Quantile returns

The complete mean/cumulative/win-rate/date-count table is immutable in
`quantile_returns.parquet`. Daily mean returns by horizon are:

| Period/horizon | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 | Q7 | Q8 | Q9 | Q10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2021 T+1 | -.064% | -.015% | -.005% | .061% | .107% | .038% | .044% | .003% | .103% | -.004% |
| 2021 T+5 | -.415% | -.077% | -.038% | .458% | .407% | .179% | .161% | .244% | .115% | -.077% |
| 2021 T+10 | -.942% | -.120% | -.080% | .712% | .730% | .378% | .432% | .410% | -.015% | -.290% |
| 2022 T+1 | .032% | -.006% | -.056% | -.014% | -.026% | -.015% | -.006% | -.057% | -.046% | -.115% |
| 2022 T+5 | .190% | -.068% | -.183% | -.220% | -.294% | -.028% | .085% | -.136% | -.317% | -.392% |
| 2022 T+10 | .411% | -.089% | -.234% | -.333% | -.508% | -.211% | .071% | -.156% | -.630% | -.634% |
| 2023 T+1 | -.031% | .010% | -.033% | -.035% | .004% | -.008% | .038% | .017% | -.043% | -.016% |
| 2023 T+5 | -.202% | -.010% | -.067% | -.204% | -.133% | -.036% | .144% | .028% | -.146% | -.213% |
| 2023 T+10 | -.517% | -.223% | -.145% | -.385% | -.189% | -.084% | .117% | -.033% | -.142% | -.558% |
| 2024 T+1 | .025% | .090% | .069% | .118% | .108% | .052% | .115% | .093% | .137% | .175% |
| 2024 T+5 | .363% | .438% | .508% | .510% | .428% | .267% | .719% | .511% | .578% | .731% |
| 2024 T+10 | .760% | .851% | 1.166% | .946% | .730% | .773% | 1.218% | 1.189% | 1.163% | 1.253% |
| 2025 T+1 | .090% | .013% | .052% | .044% | .029% | .053% | .075% | .021% | .024% | .041% |
| 2025 T+5 | .498% | .246% | .242% | .185% | .260% | .314% | .277% | .242% | .155% | .284% |
| 2025 T+10 | .920% | .578% | .523% | .461% | .537% | .587% | .627% | .431% | .286% | .699% |
| 2026H1 T+1 | -.108% | -.094% | -.176% | -.139% | -.155% | -.044% | -.082% | -.093% | -.153% | -.166% |
| 2026H1 T+5 | -.603% | -.724% | -.792% | -.704% | -.639% | -.202% | -.268% | -.331% | -1.321% | -.860% |
| 2026H1 T+10 | -1.474% | -1.419% | -1.551% | -1.428% | -1.074% | -.647% | -.205% | -1.008% | -2.282% | -1.780% |

## 6. Tail metrics and persistence

T+1 top-tail spreads are -.0510%, -.0839%, -.0173%, .0751%, -.0022% and
-.0730% for 2021 through 2026H1. Hit rates are 49.38%, 47.93%, 48.35%,
52.89%, 47.93% and 51.35%. Q10 retention at the fixed ten-session interval is
71.11%; another 25.25% moves to Q8/Q9, 3.26% to Q3--Q7 and 0.38% to Q1/Q2.
The signal score is persistent, but persistence does not imply positive
forward return.

## 7. Fixed Top-N diagnostics

Values are ten-session gross return / CSI300 excess / maximum drawdown /
average overlap. Net is intentionally unavailable rather than fabricated.

| Period | Top5 | Top10 | Top20 | Top30 |
|---|---|---|---|---|
| 2021 | -18.70/-9.18/-34.71/51.21% | -1.16/8.36/-23.58/53.65% | -4.06/5.47/-20.36/64.53% | -.62/8.90/-16.20/69.45% |
| 2022 | -14.78/2.37/-22.70/53.57% | -14.70/2.45/-20.63/54.93% | -17.70/-.55/-24.85/61.93% | -13.06/4.09/-20.85/62.72% |
| 2023 | -6.48/9.04/-22.24/47.78% | -14.24/1.29/-21.94/53.91% | -10.31/5.21/-22.03/56.12% | -7.32/8.21/-19.01/62.02% |
| 2024 | 28.80/15.97/-17.81/56.66% | 20.19/7.37/-13.63/57.06% | 26.44/13.62/-10.48/67.79% | 32.51/19.69/-7.56/69.63% |
| 2025 | 10.13/-13.99/-22.79/53.17% | 6.16/-17.96/-18.31/57.21% | 7.07/-17.05/-12.33/61.80% | 7.40/-16.72/-11.25/67.87% |
| 2026H1 | -22.64/-26.92/-26.89/51.73% | -18.68/-22.96/-19.34/56.19% | -17.90/-22.18/-18.09/58.54% | -17.64/-21.91/-17.14/60.70% |

No Top-N result is chosen or promoted. Top20 excess is positive in only three
of six periods and fails both report periods.

## 8. 2023 anomaly and stock contributions

Formal monthly RankIC is positive only in January and December; it is
negative in the other ten months, so the annual negative result is pervasive,
not one bad month. Adjusted-close RankIC is positive in seven months and Q10
beats the universe in February, March, April, October, November and December,
showing label/return-semantic divergence plus unstable middle ordering.

For the fixed Top20 diagnostic the top positive contributors are SH601857,
SH600958, SH601225, SH600028 and SH600276; the largest negatives are SH601336,
SZ000568, SH600519, SZ000333 and SZ002475. Additive return is -9.51%; excluding
the five largest winners is -15.05%, while excluding the five largest losers
is -4.38%. Q10 additive return is -3.93% and becomes -11.37% without its five
largest winners; Q1 additive return is -7.55%. The small positive Q10-Q1 is
therefore contribution-sensitive and partly reflects severe Q1 losses, not a
stable winning Q10. No non-PIT industry attribution is attempted.

## 9. Beta, style and breadth

Top20 beta60 / universe median / difference / residual-return diagnostic:

| Period | Values |
|---|---|
| 2021 | 1.005 / .637 / +.367 / +.2945% |
| 2022 | .886 / .833 / +.053 / +.1055% |
| 2023 | .990 / .910 / +.080 / +.0593% |
| 2024 | .594 / .899 / -.305 / +.1167% |
| 2025 | .913 / .713 / +.199 / -.0721% |
| 2026H1 | .740 / .578 / +.163 / +.1536% |

The basket is generally larger-cap, more liquid by amount ratio and higher in
idiosyncratic/total volatility than the universe median; it is not a
systematic small-cap, low-liquidity or low-beta portfolio. Both momentum
features are strongly correlated with the composite by construction. In
2024, unlike the other periods, beta is materially below the universe.

Breadth is decisive: broad has RankIC -.01313, Q10-Q1 -.1700% and Top20 excess
-8.24%; neutral has .01332, .0148% and -15.83%; narrow/weak has .02628,
.1323% and +39.05%. Only narrow/weak is jointly positive, supporting the
regime-specific classification.

## 10. Component diagnosis and report periods

In 2025 both components have negative formal RankIC (absolute -.00852,
residual -.01210). On adjusted-close T+1, absolute momentum is positive
(.00996; tail +.0185%) while residual momentum is negative (-.00956; tail
-.0200%). The composite formal RankIC is -.01149, Q10 does not lead at T+1,
and Top20 gross 7.07% trails CSI300 by 17.05%. Top20 beta is above—not below—
the universe and residual return is negative, so low-beta defense does not
explain the underperformance. T+10 Q10-universe is +.1328%, but this weak late
tail effect does not rescue the basket.

In 2026H1 both components retain positive formal RankIC (absolute .00430,
residual .01019), but adjusted-close T+1 separates sharply: absolute momentum
is -.01668 with tail -0.1522%, while residual momentum is +.01710 with tail
+0.0459%. Thus the observed forward-close tail reversal is concentrated in
the absolute-momentum component, not the residual component. The composite
formal RankIC is +.01302 but adjusted-close RankIC is -.00285, T+10
Q10-universe is -.4812%, and Top20 trails CSI300 by 22.18%. Ten-session holding
does not explain away the failure; it is worse at T+10.

## 11. Score stability, transition and decay

Score autocorrelation at 1/5/10/20 sessions is .98265/.92999/.87235/.77133.
Top10/20/30 membership overlap is .5655/.6298/.6661. The high persistence and
71.11% Q10 retention show slow rank decay rather than rapid reversal.

Across 2021--2024, adjusted-close RankIC at T+1/5/10/20/40 is
.01540/.00885/.00365/.00372/.00138. Q10-Q1 is
.0196%/.0282%/.0152%/-.0894%/-.9445%; Q10-universe is negative at every
horizon: -.0112%/-.0830%/-.2273%/-.6034%/-2.0055%. The signal's rank ordering
decays slowly, but its top tail does not earn a durable universe-relative
premium. No rebalance frequency is changed from this evidence.

## 12. Relation to formal B0/L1 implementation

R1-008 remains authoritative for trading implementation. Signal D B0/L1
full-period turnover is 84.66/53.60 and cost is 60,507/39,342; L1 net return
improves from -4.90% to -3.46% and excess from 20.40% to 21.84%. Annual L1
turnover is 13.06, 15.35, 16.59 and 12.65; annual costs are 10,333, 10,710,
14,994 and 11,883. Lower frequency saves costs, but the negative
Q10-universe decay and later-period gross failures show that cost reduction
cannot turn this into stable broad or tail-only Alpha.

## 13. Classification and decision

Primary class is `regime_specific_factor`; there are no secondary labels.
Evidence counts are three positive formal-RankIC research years, one positive
Q10-universe research year, three positive Top20-excess periods, zero positive
report-period T+1 tails, and one robust PIT breadth regime. The advisory
decision is `retain_for_regime_specific_research`, `execute_decision=false`.
It does not establish predictive performance and does not authorize a new
task, overlay, Candidate, Registry write or Promotion.

## 14. Runtime, Store and replay

- Revision-3 child artifacts: quantile
  `mqrr1_7780e004...a62905`, transition `mrtr1_35f80cf8...7f1aa`, style
  `mtse1_d907cb11...8c194`, classification `mtsc1_bc4dac92...cbff7`.
- Inventory: `sai_b4d1dc9e1603562eda8b88015273eff8c1ab36d80e9c4ce66885f9f54d4019e2`.
- Integrity is healthy; Missing 0; Unreferenced 0.
- Cold recovery validates five artifacts from an empty cache.
- Exact replay recovers the same five with Agent, all Optimization, Qlib
  strategy, network, new Artifact/Blob, Registry and Promotion counts zero.
- Earlier computation revisions remain immutable and reachable; the runtime
  deterministically selects the highest computation revision.

## 15. Implementation and architecture impact

Added the bounded diagnostic protocol, artifact publisher/validator, engine,
CLI, five Store/runtime kinds, focused tests and Project Memory contract.
Existing Tushare authority, R1-008 signal values, feature matrix, regime
builder and Store are reused. No API, database, migration, dependency,
lockfile, configuration, Qlib result, LightGBM, Electron or production
behavior changes. A defensive empty-final-date guard affects only synthetic
or truncated monthly diagnostic inputs.

## 16. Tests and verification

Focused tests cover identity, frozen governance, formal/forward RankIC
separation, deciles/tails, fixed Top-N, monthly and stock attribution,
beta/style/component exposure, breadth classification, stability, transition,
decay, reports, Artifact validation and zero state writes. Formal spec/source
validation, revision-3 execution, Store integrity, cold recovery and exact
replay pass. The focused suite passes 19 tests; the bounded regression suite
passes 90 tests; Context Bootstrap passes 42 checks; all nine CLI commands,
113 JSON files, py_compile and diff-check pass. A broader first regression
attempt passed 88 tests and failed 10: eight pre-existing real-Store fixtures
refer to artifacts removed by the prior Tushare cutover, while two Context
assertions still named R1-008 and were updated for this task. The corrected
bounded suite excludes only those stale external Store fixtures. Git inventory
and post-commit Planner are recorded in the Manifest and final response.

## 17. Known limitations and rollback

- All evidence is retrospective and history-informed, not Fresh Validation,
  Frozen Test, predictive or production evidence.
- Adjusted-close diagnostics and the inherited next-open formal label answer
  different questions and must remain visibly separate.
- Top-N results are gross-only; formal cost-aware evidence remains R1-008 B0/L1.
- Beta/style decomposition is diagnostic, not causal; PIT industry attribution
  is unavailable.
- Fixed-100 benchmark settlement caveats from the existing data authority are
  unchanged; CSI300 is the benchmark used here.
- Runtime and Store remain single-host/single-process.
- Eight old real-Store regression cases remain environment-stale because their
  fixed artifact IDs are absent from the current Tushare-authoritative Store;
  this task neither recreates retired artifacts nor weakens Store-required
  resolution.

Rollback is a revert of the single task commit. Immutable Store artifacts are
historical facts and are not deleted or overwritten. No push is performed and
no successor task is authorized.
