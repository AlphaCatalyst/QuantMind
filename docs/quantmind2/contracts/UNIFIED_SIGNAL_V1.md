# Unified Signal Contract v1

Status: implemented by `QM2-P0-016`.

## Boundary

`FactorSignalInput` binds one locked Factor Template, Factor Instance, values
artifact, orientation, Dataset, Universe, evidence class and canonicality. It
also records `values_are_oriented`; this is required because the historical
Tushare round-lock files already contain oriented values, while future raw
Factor Value materializations may not.

`UnifiedSignalSpec` is separate from Factor research, Strategy specification,
portfolio targets and backtest results. V1 admits `raw`, `cs_rank`,
`cs_zscore` and explicitly bounded `winsorized_cs_zscore`. Orientation is
applied before transformation unless the input declares that its immutable
source is already oriented. Cross-sectional z-score uses `ddof=0`, does not
fill missing values, and emits NaN for a zero-variance cross-section.

V1 combinations are `single_factor`, `fixed_weight_sum` and `equal_weight`.
Weights are declared before evaluation, non-negative and sum to one. The
default missing policy is the only formal V1 policy:
`require_all_factors`. No Agent, IC weighting, dynamic weighting, model,
Factor Optimization, Strategy Optimization or Promotion is performed.

Identities are `uss_<sha256>` for the Spec and `usa_<sha256>` for the
materialized signal. The Artifact contains `spec.json`, `quality.json`,
`signal.parquet` and `manifest.json`; its score schema is exactly `symbol`,
`trade_date`, `score`.

## Real evidence

The three locked Tushare candidates produced four Unified Signals. The
equal-weight artifact is
`usa_4c824a58d0a17cb0aebea30bbc2197ae8246843b2aaae14a49fc1c091789fab0`.
Over 2019-01-02 through 2026-06-23 its 180,241 keys, NaN mask and all 180,231
finite cells are exactly equal to the historical equal-weight signal; maximum
absolute difference is zero.

All current inputs are `research_diagnostic`, with `predictive_claim=false`
and `eligible_for_production=false`.
