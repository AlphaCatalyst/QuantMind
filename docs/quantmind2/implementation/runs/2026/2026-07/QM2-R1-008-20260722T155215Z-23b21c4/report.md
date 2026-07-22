# QM2-R1-008 Implementation Report

## 1. Task Summary

- Task: `QM2-R1-008 — Low-Frequency Momentum and Turnover-Control Study v1`
- Result: completed, pending containing commit and post-commit Planner
- Base: `23b21c44abfac5553d5c3b768ee351ced1812273`
- Study: `lfmsta1_18f3a4add9e0e224a7a8d35133af2dbfa9a23181edc94134d9c2c3738965ff80`
- Assessment: `lfma1_de242a62775b3ed793c17ae48cc3eee48e478e91974b982ea48d8c9f768319f3`

## 2. Goal and pre-registration

Test whether longer formation/skip-recent momentum plus fixed ten-session
rebalancing converts weak stock-selection information into net Alpha by
reducing turnover, cost and erroneous replacement. All four signals and both
protocols were immutable before any formal return backtest. This is
retrospective evidence, not a predictive claim, Fresh Validation, Frozen Test,
Promotion or production evidence.

## 3. Scope and non-goals

Implemented the signal/protocol contracts, deterministic study runtime,
Artifact types and validation, formal-Qlib evidence, eligibility/assessment,
Store publication, CLI, tests and Project Memory. It does not call Agent,
generate Features, optimize Factor/Strategy/Combined parameters, test a third
frequency, collect data, change Fixed-100/Label, select on report periods or
write Promotion/production state.

## 4. Preflight and feature audit

Repository, branch and HEAD matched the task contract; worktree was clean and
had no unrelated dirty files. Catalog evidence confirms
`momentum_efficiency_60` is signed return divided by accumulated absolute
daily movement. `residual_momentum_60` subtracts lag-one CSI300 beta exposure
using beta window 60, beta lag one, benchmark-return lag one and minimum 62
periods. Qlib's `rebalance_days` is a trade-session modulo step; TopK/n_drop,
lag one, open execution and CnExchange cost are executed by the existing
formal chain.

## 5. Signals and protocols

The signals are A classic `rank(momentum_120_20)`, B equal 60/10 plus 120/20,
C equal 120/20 plus signed path efficiency and D equal 120/20 plus residual
momentum. Composite inputs are cross-sectional z-scores, weights 0.5/0.5.
B0 and L1 both use TopK20, n_drop5, equal weight, lag one, open and CSI300;
B0 rebalances every five sessions and L1 every ten. B0 is comparison-only and
L1 is the only candidate protocol.

All signals pass the declared aggregate quality gate: finite coverage
0.976859 for 2019--2026H1, infinity/duplicates/PIT violations zero, and at
least 96 finite members after the declared 2019--2020 warm-up. The source
begins with 41 warm-up sessions having no available long-window values; these
remain missing and are neither filled nor used to relax formal evaluation.

## 6. Annual formal results

Values are L1 net return / CSI300 excess / RankIC / Sharpe / max drawdown /
turnover / transaction cost. B0 turnover and cost follow in parentheses.

| Signal | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|
| A | 11.37% / 17.58% / .00299 / .384 / -22.03% / 14.65 / 11,710 (20.92 / 17,000) | -15.58% / 5.69% / .01442 / -.890 / -22.47% / 17.11 / 12,928 (27.46 / 20,734) | -8.06% / 3.69% / -.00580 / -.665 / -19.00% / 15.84 / 13,291 (24.24 / 20,280) | 12.01% / -4.19% / .00054 / .532 / -12.90% / 13.70 / 12,829 (19.05 / 17,593) |
| B | 3.23% / 9.44% / -.00004 / .047 / -26.98% / 13.64 / 10,631 (21.00 / 16,126) | -18.16% / 3.11% / .00482 / -1.017 / -23.54% / 15.99 / 11,475 (24.56 / 18,410) | -6.45% / 5.30% / -.01570 / -.537 / -17.42% / 16.23 / 13,961 (23.59 / 19,847) | 20.53% / 4.33% / .00588 / .920 / -12.93% / 13.76 / 12,999 (17.51 / 16,743) |
| C | 5.66% / 11.87% / .00027 / .143 / -24.90% / 13.47 / 10,667 (20.09 / 15,533) | -13.54% / 7.73% / .00350 / -.794 / -21.88% / 14.88 / 10,876 (25.51 / 19,139) | -1.33% / 10.42% / -.01204 / -.203 / -16.04% / 16.37 / 14,723 (25.40 / 22,822) | 19.81% / 3.61% / .01009 / .870 / -14.24% / 13.00 / 12,479 (16.00 / 15,480) |
| D | 4.47% / 10.69% / .00053 / .095 / -24.57% / 13.06 / 10,333 (20.16 / 15,865) | -17.31% / 3.96% / .00568 / -.930 / -25.18% / 15.35 / 10,710 (24.21 / 17,166) | -2.31% / 9.44% / -.01506 / -.259 / -18.41% / 16.59 / 14,994 (25.30 / 22,160) | 26.16% / 9.96% / .00832 / 1.133 / -14.28% / 12.65 / 11,883 (17.51 / 16,928) |

## 7. Full-period result and low-frequency impact

| Signal | B0 net / excess / RankIC / Sharpe / DD | L1 net / excess / RankIC / Sharpe / DD | B0→L1 turnover | B0→L1 cost |
|---|---|---|---|---|
| A | -11.82% / 13.48% / .00304 / -.246 / -39.14% | -7.76% / 17.54% / .00304 / -.195 / -32.15% | 90.45→59.19 | 69,941→47,605 |
| B | -8.00% / 17.30% / -.00126 / -.186 / -44.18% | -10.15% / 15.16% / -.00126 / -.214 / -40.20% | 86.89→57.23 | 60,791→42,713 |
| C | 3.31% / 28.61% / .00045 / -.052 / -39.35% | -2.40% / 22.90% / .00045 / -.122 / -35.43% | 84.90→55.71 | 64,535→43,470 |
| D | -4.90% / 20.40% / -.00013 / -.146 / -43.66% | -3.46% / 21.84% / -.00013 / -.131 / -42.28% | 84.66→53.60 | 60,507→39,342 |

Across the 16 annual signal/year pairs, median turnover reduction is 34.54%
and median cost reduction is 33.21%, both above the frozen thresholds. Median
annual L1 net return improves over B0 for all four signals. RankIC is a signal
property and is unchanged by execution frequency. Full-period effects are
mixed: A and D improve, B and C deteriorate; reduced cost is not universally
converted into Alpha.

## 8. Holding, decay and regime diagnostics

Average holding duration rises from 29.9--30.3 sessions to 45.1--47.0;
entries/exits fall from roughly 637/617--643/623 to 410/390--428/408. Median
duration rises from 15--20 to 30--40 sessions. The change is genuine holding
extension with near-20 average holdings, not failed trading or insufficient
members. Rebalance-point overlap is lower because the ten-session comparison
spans a longer interval; it does not contradict lower cumulative turnover.

T+1/T+5/T+10/T+20 RankIC decays A .0212/.0150/.0086/.0083; B
.0167/.0030/-.0046/-.0107; C .0152/.0075/.0012/-.0007; D
.0154/.0088/.0036/.0037. D has the most persistent horizon profile. Regime
evidence is mixed: L1 often improves drawdown and excess in sideways/normal
conditions, but B and C lose excess in bull/high-vol states, consistent with
slower reversal response. Regime turnover values cannot be allocated from the
available formal result and remain zero rather than inferred.

## 9. Eligibility, reports and assessment

A fails median RankIC; B fails positive-year/median/worst RankIC; C fails
median/worst RankIC; D fails worst RankIC. All four otherwise show meaningful
turnover/cost reduction, positive median annual excess and L1 net improvement.
No signal passes every gate, so ordering is empty, Candidate Locks are zero,
and 2025/2026H1 reports are correctly not executed.

Final classification is `stock_selection_signal_only`. Ten-session rebalancing
does not merely make losses slower: annual medians improve and cross-sectional
or excess evidence survives. But it also does not establish stable standalone
Alpha. D is most stable and has the highest median RankIC; C has the best
median net return and risk-adjusted result. Research may continue only as a
stock-selection/portfolio overlay under a separately authorized task.

## 10. Runtime, Store and replay

- Formal Qlib calls: 40; Agent/Factor/Strategy/Combined Optimization: 0.
- Network/Tushare/Promotion writes: 0; Candidate Locks/reports: 0/0.
- Store: 715 Artifacts, 3,549 Blobs; inventory `sai_06ee449c...28be`.
- Integrity: healthy; Missing 0; Unreferenced 0.
- Cold recovery restored 39 study objects from Store into an empty cache.
- Exact replay: all research/external calls, new artifacts/blobs and state
  writes are zero.

The first successful execute emitted an unnecessarily large diagnostic return
because it included predecessor evidence. After immutable publication, only
the CLI summary boundary was narrowed to predecessor IDs; no research result
was rerun or mutated.

## 11. Implementation changes and architecture impact

Added `low_frequency_momentum` protocol, artifact and engine modules, seven
formal Artifact kinds, Store/runtime registration, CLI, focused tests and the
frozen contract. Project Memory records the zero-lock result. Existing
Momentum Dataset, Qlib service, strategy/executor/exchange and Store are reused.
No API, database, migration, configuration, dependency, lockfile, Electron,
LightGBM or production Registry behavior changes.

## 12. Security and lineage

No credential is accepted, persisted or logged; no network is called. Every
definition, result and assessment binds immutable Dataset/Catalog/protocol IDs.
Report periods cannot influence selection. Registry and Promotion state remain
unchanged.

## 13. Tests executed

Focused runtime tests pass. Formal plan, signal/protocol validation, 40-call
execute, Store validation, cold recovery and exact replay pass. Context,
relevant regression, JSON, `py_compile`, `git diff --check`, Git inventory and
post-commit Planner results are finalized in the Manifest and final response.
One initial aggregate pytest invocation inherited unavailable coverage plugin
arguments and ran zero tests; the corrected `-c /dev/null` invocation is the
recorded test execution.

## 14. Known limitations and rollback

- Retrospective, history-informed evidence cannot support predictive or
  production claims.
- The isolated Redis-disabled Qlib output exposes positions but no trade rows;
  holding transitions use positions, while cost/turnover use the formal
  CnExchange collector.
- Regime-specific turnover cannot be allocated from the persisted daily
  result and is left at zero rather than fabricated.
- Fixed-100 2025/full-period benchmark settlement remains noncanonical, but no
  report-period run occurred and 2021--2024 CSI300 evidence is unaffected.
- Runtime and Store remain single-host/single-process.

Rollback is a revert of the single task commit. Immutable Store artifacts must
remain historical and may only be superseded by new lineage. No successor task
is authorized; commit is created only after Manifest verification and push is
not performed.
