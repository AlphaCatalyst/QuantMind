# Fixed Configuration Model Alpha Program v1

Status: accepted implementation contract for `QM2-R2-007`.

## Boundary

This program aggregates already-authorized weak technical features. It reuses
the existing QuantMind LightGBM and Qlib chains. A model score is a distinct
research object and must not be represented as a DSL factor, Terminal Feature,
Factor Instance, or production signal.

The program creates no Feature, Primitive, Label, model hyperparameter trial,
strategy optimization trial, Registry entry, Promotion, or production switch.
Historical evidence is `retrospective_research_only`.

## Formal inputs

- provider: `tushare-pro-v1`
- universe: Tushare Fixed-100
- market pool: Tushare Fixed-500
- benchmark: CSI300
- label: existing `model_label`
- Feature Catalog:
  `tfc3_b903c85e328d359181c18ce3444d458a41ee970be8b2f6b79eff83cc6d523aea`
- Primitive Catalog:
  `tpc2_b9f6112bec9f5524d8d14eb0ff8d40244c0e143557d49c1676c2630686387208`

`model_label` is the same-day cross-sectional 5-MAD-winsorized, population
z-scored value of `adjusted_close[T+1] / adjusted_open[T+1] - 1`. A row is
absent when the next quote is unavailable, volume is non-positive, or the
next observation is conservatively locked at a price limit.

## Frozen model

Only the existing LightGBM implementation is authorized. One configuration is
frozen before Fold 1. It uses regression/L2, GBDT, learning rate `0.05`, 31
leaves, unlimited declared depth, minimum leaf data 50, feature and bagging
fractions `0.8`, bagging frequency 5, no L1/L2 penalty, one thread,
deterministic/column-wise execution, and 200 fixed boosting rounds.

Early stopping is disabled. The three seeds are `20260701`, `20260702`, and
`20260703`. Their predictions are always equally averaged; a seed is never
selected using performance.

## Feature Bundles

All three hypotheses freeze before training:

1. `existing_technical_core`: the 36 Catalog v3 research features that predate
   R2-006.
2. `expanded_technical_space`: the 20 R2-006 Terminal Features and six v2
   technical primitives.
3. `combined_decorrelated_technical`: the union of the first two. Each Fold
   applies the same train-only, label-free quality ordering using finite
   coverage, cross-sectional dispersion, and rank persistence, then greedily
   removes numeric redundancy at absolute Spearman correlation at least 0.95.

Bundle membership never reads Label, RankIC, returns, Feature Importance,
SHAP, outer-test observations, or report-period results.

## Walk-forward and leakage boundary

The four fixed outer tests are calendar years 2021 through 2024 with expanding
training starting 2019-01-02. The last ten official training sessions are
purged. Embargo is zero. Outer-test rows cannot enter training, preprocessing
fit, Bundle C selection, early stopping, or model configuration.

Preprocessing is the existing same-date cross-sectional 5-MAD winsorization and
population z-score. It is stateless across dates. Non-finite results become
zero only after this transform. Feature membership is the only fitted
preprocessing state and for Bundle C is derived only from the Fold train rows.

The 2025 and 2026-through-available-data results are contaminated reports only.
They cannot affect Bundle membership, model configuration, Candidate Gate,
multiple testing, or Supervisor decisions.

## Output and strategy

Each Fold preserves the three seed models, averaged raw prediction,
cross-sectional percentile score, unified signal, portfolio target, Qlib
result, daily official-label metrics, and truthful consumer output. Signal lag
is one session and execution is open.

The fixed Qlib strategy is TopK 20, `n_drop=5`, ten-session rebalance, equal
weight, and CSI300 benchmark. Strategy and combined optimization are forbidden.

The existing Qlib consumer currently returns NAV and aggregate order metrics
but not durable daily holdings/trade tables. Empty, schema-bearing tables
therefore declare the unavailable evidence; they must not be interpreted as
evidence that no holdings or trades occurred.

## Selection and Fresh boundary

Daily official-label RankIC is the only primary statistic. Each Bundle receives
one HAC test with lag 10. The three preregistered hypotheses share a single
Benjamini-Hochberg family at FDR 10%. The retrospective gate, incremental gate,
model-concentration gate, and adjusted q-value must all pass.

A survivor becomes only a `retrospective_model_candidate`. It is not a Factor,
validated feature, Registry entry, Promotion, or production model. A Fresh
Lock requires the first official trade date strictly after the later of the
market-data maximum and project contamination maximum. No backfill is allowed.
Monthly first-trading-day retraining may later use only the frozen expanding
window, configuration, Bundle rule, preprocessing, and seed ensemble.

If no model survives, Cycle 003 completes legally with zero Candidate and zero
Fresh Lock. No Cycle 004 is automatically created.
