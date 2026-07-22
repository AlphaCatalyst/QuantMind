# Low-Frequency Momentum and Turnover-Control Study v1

## Authority and research status

This contract freezes QM2-R1-008 before formal return evaluation. It is a
retrospective, pre-registered research study, not Fresh Validation, Frozen
Test, Promotion or production evidence. `predictive_claim`,
`fresh_validation`, `frozen_evidence`, `usable_for_promotion` and
`eligible_for_production` are false.

## Data and signals

The sole data authority is the immutable Tushare Fixed-100 Momentum Feature
Dataset `mfd1_9bb717...c08db2c`, benchmark CSI300. No network collection or
new Feature is permitted. Four signals are fixed:

1. `classic_long_term_skip_recent`: `cs_rank(momentum_120_20)`.
2. `dual_horizon_skip_recent_consensus`: equal-weight cross-sectional z-scores
   of `momentum_60_10` and `momentum_120_20`.
3. `path_quality_long_term_momentum`: equal-weight z-scores of
   `momentum_120_20` and signed `momentum_efficiency_60`.
4. `residual_absolute_momentum_consensus`: equal-weight z-scores of
   `momentum_120_20` and `residual_momentum_60`.

All weights, orientation and Feature definitions are immutable and have no
optimization parameters. The residual Feature uses a 60-session beta, beta
lag one, CSI300 benchmark-return lag one and 62 minimum periods.

## Execution protocols

Both protocols use TopK20, n_drop5, equal weight, signal lag one session,
open execution and CSI300. B0 rebalances every five trade sessions and is
comparison-only. L1 rebalances every ten trade sessions and is the only
candidate protocol. No other frequency may be tested.

## Evaluation and chronology

The study runs 32 annual formal Qlib jobs (four signals, two protocols,
2021--2024) and eight full-period 2021--2024 jobs. Candidate eligibility uses
only these results. Only locked candidates may receive 2025 and 2026H1
report-only runs, which cannot change a lock.

Eligibility uses the frozen data-quality, RankIC, excess, turnover, cost,
concentration, independence and L1-increment gates in the task contract. At
most two candidates may be written, only as `research_registered`.

## Governance and replay

Agent, Factor Optimization, Strategy Optimization, Combined Optimization,
Tushare/network and Promotion calls are zero. Artifacts are content-addressed,
Store-backed and immutable. Cold recovery must restore the complete graph;
exact replay must create no calls, artifacts, blobs or state writes.

The terminal classification is exactly one of
`low_frequency_hypothesis_supported`, `stock_selection_signal_only`,
`turnover_reduced_but_alpha_absent` or `low_frequency_hypothesis_rejected`.
