# Momentum Factor Family Iteration v1

Status: executed research contract for `QM2-R1-002`.

## Authority and scope

The only market-data inputs are the immutable Tushare Pro Fixed-100 normalized
bars, label Dataset, CSI300 benchmark and Qlib consumer view named by
`TUSHARE_AUTHORITY_V1.json`. The runtime makes no Tushare network call, does not
read retired legacy market data, does not accept a token and does not change
the fixed universe. This is retrospectively contaminated research, not Fresh
Validation, Frozen Test, Promotion or production evidence.

## Feature contract

`MomentumFeatureCatalogV1` defines 36 PIT-safe daily features in nine families:
absolute, skip-recent, relative, residual, path-quality, risk-adjusted,
acceleration, breakout and amount-confirmation momentum. Every definition binds
formula, economic meaning, source columns, lookback/min-periods, lag,
adjustment, missing-data, PIT, direction and allowed-operator semantics.
Warm-up remains null, infinity becomes null and no fill is permitted. High
correlations at or above 0.97 are reported explicitly; economically distinct
fixed horizons or normalizations are not silently collapsed.

## Research and optimization contract

The external Agent is `openai_codex_cli` with `gpt-5.6-terra` and proposes only
DSL structure. Six themed rounds are available, with two calls, four proposals,
three admissions, eight Trials per Template and 24 Trials per round; total caps
are 12 calls, 18 Templates and 144 Trials. A proposal uses one to three
Momentum Features, no more than three parameters and AST depth at most seven.
Round 6 requires at least two families. Family admission is capped at three and
window-only equivalent structures are rejected.

Parameters are selected independently in four expanding research windows:
2019--2020 for 2021, 2019--2021 for 2022, 2019--2022 for 2023, and 2019--2023
for 2024. Evaluation years never select their own parameters. A direct
parameter neighbor is stable only when RankIC direction agrees and CSI300
excess is no more than 15 percentage points below the selected Trial.

## Evaluation and state contract

Formal results use existing Qlib TopK20, n_drop5, five-session rebalance, equal
weight, one-session signal lag, open execution and CSI300. Strategy parameters
are not searched. Trend, volatility and breadth regimes are lagged, expanding,
past-only diagnostics and are unavailable to Agent/DSL/selection as inputs.

Eligibility requires four valid Folds, coverage >=90%, no infinity/PIT breach,
three positive RankIC Folds, median RankIC >=0.003, worst RankIC >=-0.008,
three positive CSI300-excess Folds, positive median excess, worst excess above
-10 percentage points, median turnover <=40, formal costs, median best-ten-day
contribution <=35%, neighborhood stability >=50%, and maximum correlation with
the four existing factors below 0.85. At most five candidates may be locked,
one per family and at least two families overall. Status is only
`research_registered`.

2025 and 2026H1 are opened only after locking, are report-only and cannot alter
Agent Memory, ordering or parameters. A new equal-weight momentum ensemble and
old/new 50/50 diagnostic are created only when at least two candidates lock.
Fixed-100-relative metrics are never selection evidence.

## Executed outcome

Canonical revision 2 supersedes an immutable first attempt whose early stop
preceded the six-family diversity gate. Revision 2 ran five real Agent rounds,
13 admitted Templates, 37 parameter Trials and 92 formal Qlib calls, explored
eight families, and stopped after two consecutive rounds without ordering
improvement. One candidate passed the standalone eligibility gates, but final
locking requires at least two families; therefore zero candidates were locked,
later-period candidate reports and ensembles were not opened, and no Registry
or Promotion write occurred. The formal conclusion is: the current Fixed-100
daily momentum space has not produced sufficiently stable Alpha.

Final experiment:
`mfi1_87177b7c06420e65159d3f5bdafee8149cdb3290c32f08712cd73e59a4e19dee`.
It cold-recovers and exact-replays with zero Agent, Optimization, Qlib, network,
new-artifact and new-blob calls from a healthy Store.

## Artifact and CLI contract

Artifact kinds are `momentum_feature_catalog`, `momentum_feature_dataset`,
`momentum_factor_iteration`, `momentum_factor_round_result`,
`momentum_factor_candidate_lock`, `momentum_factor_ensemble`, and
`momentum_iteration_assessment`. Identities are content-addressed and immutable.
The CLI is `tools/quantmind2/run_momentum_factor_iteration.py` with catalog,
feature, plan, execute, validation and inspection commands. Exact replay always
selects the unique highest contract revision.
