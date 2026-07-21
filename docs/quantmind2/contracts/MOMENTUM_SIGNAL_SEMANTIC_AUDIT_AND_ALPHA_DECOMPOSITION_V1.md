# Momentum Signal Semantic Audit and Alpha Decomposition v1

## Scope

This contract diagnoses the two immutable `QM2-R1-003` Candidate Locks and
their immutable equal-weight ensemble. It does not create Factors, search
parameters, call an Agent, change Strategy parameters, use the network, or
write Promotion state.

## Locked inputs

- Candidate A: `srmcl1_56201db3ca8a2b4ccd88be58abfddc127d4c077e16407c400a3f4312edd9f95b`
- Candidate B: `srmcl1_4e0abd499038faf0ecc9f178b89712d7055790e91d3e391f41a0e338352c80b4`
- Ensemble: `srmen1_7200c57baf718a80992e812e28de0241a479f443e5e64bb2581830fecbe25ab2`
- Strategy: TopK 20, n_drop 5, five-session rebalance, lag one, open
  execution, CnExchange costs and CSI300.

The Candidate IDs, DSL, AST, parameters, orientation, Factor Values, signals,
Strategy inputs and historical results are immutable. Both Candidate states
remain `research_registered`.

## Semantic authority

Candidate A computes the cross-sectional z-score of current
`momentum_60_10` less its own trailing 40-observation mean. It has no risk
denominator, residualization or risk penalty. Its display classification is
therefore `momentum_deviation_or_surprise`; the historical `risk_adjusted`
name is retained only as immutable lineage and is a semantic mismatch.

Candidate B uses
`distance_to_high_60 = adjusted_close / rolling_max(adjusted_close, 60) - 1`.
Because the distance is normally non-positive, subtracting 0.75 times it is
equivalent to adding `0.75 * abs(distance_to_high_60)`. It rewards a larger
pullback from the high and is classified as
`momentum_plus_mean_reversion_or_anti_crowding_discount`, not breakout
confirmation.

## Diagnostic boundaries

The periods are 2019--2024, the calendar years 2021--2024, 2025 and 2026H1.
The latter two are `retrospective_report_only_not_fresh_validation` and may
not drive selection, tuning or Promotion.

The diagnostic records IC, RankIC, ICIR, RankICIR, positive rate, weekly and
monthly RankIC, quantile returns, top-minus-bottom spreads, signal horizon
decay, PIT beta decomposition, style exposure, holding concentration, stock
and trading-day contribution, formal and zero-cost results, regimes, and
Candidate/legacy-factor correlations. `CrossSectionalObservableMeanReturn`
is an equal-weight observable-universe diagnostic, not an investable Fixed-100
benchmark. Beta decomposition is diagnostic rather than strict causal
attribution. Sector attribution is omitted until a PIT industry contract
exists.

## Artifact contract

The Artifact Store recognizes five immutable kinds:

- `momentum_semantic_audit`
- `momentum_cross_sectional_diagnostic`
- `momentum_alpha_decomposition`
- `momentum_style_exposure_report`
- `momentum_failure_classification`

Every artifact has a canonical content identity, file hashes, required-file
validation, Store lineage and cold-recovery validation. Initial computation
may run explicitly counted diagnostic Qlib calls. Exact replay restores the
five artifacts with zero Agent, Optimization, Qlib, network, new-artifact,
new-blob and Promotion calls.

## Decision boundary

The only legal decisions are `continue_skip_recent_factor_research`,
`continue_as_stock_selection_overlay_only`, and
`stop_skip_recent_research`. A decision records evidence; it does not execute
another task or change Registry state.
