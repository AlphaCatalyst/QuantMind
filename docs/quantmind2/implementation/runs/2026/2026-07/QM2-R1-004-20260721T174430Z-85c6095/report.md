# Implementation Report — QM2-R1-004

## 1. Task Result

Completed. The two immutable R1-003 Candidate Locks and their ensemble were
semantically audited and decomposed without creating or changing research
inputs.

## 2. Preflight State

Repository was clean on `master` at
`85c609504eb326f811857e47afc0d808422632e9`; unrelated dirty files: none.

## 3. Candidate Semantic Audit

Both historical IDs, formulas, parameters, orientations and names remain
immutable. Display semantics were added as diagnostic evidence only.

## 4. Candidate A Meaning

`momentum_60_10` is `adjusted_close[t-10] / adjusted_close[t-60] - 1`.
Subtracting its same-symbol trailing 40-observation mean is a momentum
deviation/surprise. There is no risk denominator, beta residualization or
risk penalty, so calling it risk-adjusted is a semantic mismatch.

## 5. Candidate B Meaning

`distance_to_high_60` is
`adjusted_close / rolling_max(adjusted_close, 60) - 1`, normally in `[-1,0]`.
The locked subtraction therefore adds `0.75 * abs(distance)`: it rewards a
larger pullback and is momentum plus mean-reversion/anti-crowding, not breakout
confirmation.

## 6. Period RankIC

Mean RankIC for A/B/ensemble is 0.00655/0.00879/0.00860 in 2019--2024,
0.00747/0.00482/0.00781 in 2025, and
-0.00438/-0.00866/-0.01110 in 2026H1. A's annual 2021--2024 values are
0.00924/0.00727/0.01131/-0.00312; B's are
0.00312/0.00513/0.02446/-0.00472. IC, ICIR, RankICIR, positive rate, weekly
and monthly detail are retained in the cross-sectional artifact.

## 7. Quantile Returns

All Q1--Q10 mean and cumulative returns are retained per entity and period.
2019--2024 Q10-Q1 spreads for A/B/ensemble are
-0.000660/-0.000989/-0.000905 per session; 2025 values are
-0.000393/0.000190/-0.000242; 2026H1 values are
-0.000038/0.000900/-0.001244. Monotonicity is unstable rather than a clean
decile gradient.

## 8. Top-Bottom Diagnostic

Top-minus-bottom and top-minus-observable-universe diagnostics use raw forward
returns. `CrossSectionalObservableMeanReturnDiagnostic` is explicitly not an
investable Fixed-100 benchmark and makes no lifecycle or settlement claim.

## 9. Portfolio Beta Decomposition

A/B/ensemble mean weighted stock beta is 0.946/0.862/0.924 in 2019--2024,
0.845/0.691/0.793 in 2025 and 0.805/0.765/0.823 in 2026H1. In 2025 all three
have positive absolute returns but negative CSI300 excess. In 2026H1 residual
component sums are -0.188/-0.169/-0.185, so losses are selection-residual
dominated rather than explained by market beta. This is diagnostic, not strict
causal attribution.

## 10. Style Exposure

Against the observable-universe median, later-period portfolios are generally
higher beta and more liquid, not low-beta or illiquid. A and the ensemble tilt
larger-cap; B shifts from larger-cap in 2025 to smaller-cap in 2026H1. All
three select names farther below their 60-session high and tilt to higher
volatility in 2026H1. Full weighted, median, difference and score-correlation
records are retained.

## 11. Holding Concentration

Average holdings remain about 20, effective holdings about 19.6--20.4,
top-five share about 27--28%, top-ten share about 53--54% and maximum single
weight about 6%. Stock concentration is not severe. Sector concentration is
not computed because no PIT industry contract exists.

## 12. Stock Contribution

Top and bottom ten stock contributors, top-ten share and return excluding the
top ten are retained for each entity and period. Losses are distributed enough
that no single-stock explanation replaces the broader residual/regime
diagnosis; the ensemble does not eliminate common exposure.

## 13. Trading-day Contribution

Extreme days matter. Excluding the best ten days leaves 2025 A/B/ensemble at
-7.92%/-9.01%/-8.36% and 2026H1 at -27.35%/-27.06%/-26.43%. Excluding the
worst ten turns those periods strongly positive. Later failure is tail-day
sensitive but not a single isolated event.

## 14. Transaction-cost Drag

2019--2024 A/B/ensemble cost drag is 25.82/20.73/26.01 percentage points.
2025 drag is 2.15/2.90/2.35 points and 2026H1 is 1.25/1.19/1.28 points.
Zero-cost 2026H1 remains negative at -6.63%/-9.66%/-6.74%; costs are not the
primary later-period failure.

## 15. Signal Horizon Decay

Locked-signal RankIC and top-bottom spread are recorded at T+1, T+2, T+3,
T+5 and T+10 without parameter selection. Later-period results vary materially
by horizon and often reverse between T+1 and longer horizons, confirming
horizon/regime instability without authorizing a rebalance change.

## 16. Regime Attribution

Frozen PIT bull/bear/sideways, volatility and breadth regimes retain trading
days, RankIC, spread, CSI300 excess, beta and drawdown. Results are conditional
and unstable across trend, volatility and breadth states; regime evidence is
diagnostic and never enters selection or Agent memory.

## 17. Signal and Holding Correlation

A/B signal correlation is 0.281 and implied Top20 Jaccard is 0.201. Despite
that diversity, daily strategy-return correlation is 0.818 in 2019--2024,
0.725 in 2025 and 0.757 in 2026H1. Low signal/holding overlap did not become
long-only return diversification because market and style exposures remain
shared. Correlations against all four prior Factors are also persisted.

## 18. 2019–2024 Diagnosis

Both signals had weak positive aggregate RankIC and positive formal strategy
returns, but decile monotonicity and year-by-year RankIC were not uniformly
stable. Their historical returns combined stock selection, market exposure
and material turnover/cost drag.

## 19. 2025 Diagnosis

RankIC remains weakly positive and absolute net returns remain positive, yet
both signals and the ensemble trail CSI300. This is primarily benchmark/beta
and residual/style mismatch, not a complete disappearance of ranking signal
and not cost-only failure.

## 20. 2026H1 Diagnosis

RankIC turns negative for both candidates and the ensemble. Net and zero-cost
returns remain negative, and residual components dominate the loss. This is
genuine later-period signal degradation with regime/style interaction, not a
transaction-cost explanation.

## 21. Failure Classification

Both candidates receive `signal_degradation`, `benchmark_beta_mismatch`,
`regime_dependency` and `semantic_defect`. `portfolio_implementation_drag` is
not the primary label. No strict causal claim is made.

## 22. Research Decision

The sole recorded decision is
`continue_as_stock_selection_overlay_only`. It records a bounded research
conclusion and does not execute a successor task.

## 23. Registry

Both Candidate Locks remain `research_registered`. No validation-candidate,
promotion-candidate, approved, active or production state was written.

## 24. Artifact Store

Five immutable artifacts were published: semantic audit
`mada1_c7a8b815...04306`, cross-sectional diagnostic
`mada1_91779ecb...63d38`, alpha decomposition `mada1_a149cf3a...1ea09`,
style report `mada1_918a2443...45719` and failure classification
`mada1_9a421ba7...3941e`. Inventory is `sai_5973e667...979cf`; Store
integrity is healthy with Missing 0 and Unreferenced 0.

## 25. Cold Recovery

Every published artifact was materialized into a separate cold destination
and file/hash/identity validated before completion.

## 26. Exact Replay

Exact replay restored five artifacts with Agent 0, Optimization 0,
diagnostic Qlib 0, network 0, new artifacts 0, new blobs 0 and Promotion 0.

## 27. Files Added

Momentum alpha diagnostic domain package, CLI, tests, formal contract and this
Implementation Run.

## 28. Files Modified

Artifact kind/validation/cache routing, Project Memory and the two context
validation expectations. No Candidate, Factor, Strategy, Qlib, data authority,
model, dependency or runtime configuration was modified.

## 29. Tests Executed

Diagnostic tests: 15 passed. Relevant momentum/Store/runtime regression:
68 passed. Context unit suite: 21 passed. Context Bootstrap, JSON parse,
`py_compile`, Git diff/inventory and post-commit Planner are recorded during
finalization.

## 30. Expected vs Actual

Expected calls were Agent 0, Optimization 0, network 0 and Promotion 0; actual
counts are all zero. Initial computation made 30 explicitly diagnostic Qlib
calls (21 formal-cost and 9 zero-cost); exact replay made zero. Five artifacts
were expected and recovered.

## 31. Implementation Run

`QM2-R1-004-20260721T174430Z-85c6095`, Manifest v2, one independent commit,
no amend and no push.

## 32. Project Memory Updates

Current State, Handoff, Component Catalog, Known Issues and Roadmap record the
semantic correction, later-period diagnosis, immutable artifacts and bounded
overlay-only decision.

## 33. Known Limitations

2025 and 2026H1 are retrospective reports, not Fresh Validation. Beta
decomposition is approximate rather than causal. Sector concentration is
omitted without a PIT industry contract. The official Factor Lab bounded
source directory remains externally empty and was not modified.

## 34. Git State After

The Run is prepared uncommitted; result commit and Planner evidence are
resolved after the single commit. No push is performed.
