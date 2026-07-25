# Cross-Sectional Ranking and Style-Residual Alpha Discovery v1

## Authority and evidence semantics

This contract records `QM2-R3-002`. It extends the existing Autonomous
Research Supervisor and Rolling Blind Alpha Discovery engine; it is not a
parallel research system. The reused 60-session windows are historical
research evidence and are named `historical_rolling_evaluation`. They are not
real Fresh evidence or an independent project Holdout.

The implementation reuses the authoritative Tushare Dataset, immutable
R3-001 Window Set, Factor DSL, Technical Feature Catalog v3, existing
QuantMind LightGBM runtime, formal Qlib service and Artifact Store.

## Fixed partitions and isolation

- Discovery: `2019-01-02..2021-12-31`.
- Rolling evaluation: the exact immutable R3-001 18-window set,
  `2022-01-04..2026-06-23`.
- Rolling metrics, failures and 2025/2026 slices are invisible to the current
  Batch Agent, Planner and Failure Memory.
- Candidate configuration is frozen before the first rolling read.
- Existing real Fresh Candidates, Locks, Cohort, Heartbeat, LaunchAgent and
  Runtime Deployment are read- and write-isolated.

## Lane A: fixed style residualization

`CrossSectionalStyleResidualizationV1` uses the exact formal PIT-safe Feature
definitions `log_circ_mv`, `style_beta_20`, `style_idio_vol_20` and
`amount_ratio_20`. The first and fourth are deterministically materialized
from the same immutable normalized bars using their accepted Catalog v2
formulas; beta and idiosyncratic volatility retain their formal definitions.

For each date independently, finite raw scores and controls are selected, each
active control is population-z-scored, deterministic OLS with an intercept is
fitted, and the residual is population-z-scored. A date requires at least 80
finite members. Zero-variance controls are dropped for that date and recorded.
No return, Label, future row, cross-time fit, control search or industry
neutralization is permitted.

The Agent may propose at most three Terminal Features, one optimizable
parameter and AST depth six. Every admitted score is residualized. The raw
score is diagnostic evidence only and does not create a second hypothesis.

## Lane B: fixed cross-sectional ranking model

`technical_return_1d` raw returns are converted within each training date to
five deterministic relevance levels `0..4`. The relevance rule is frozen
before training.

The existing LightGBM runtime uses fixed `lambdarank`, NDCG@20, 200 rounds,
three fixed seeds and an equal-weight prediction ensemble. Hyperparameter
optimization, seed selection, early stopping, Label modification and
rolling-driven Feature deletion are absent.

Only `expanded_technical_space` and
`combined_decorrelated_technical` are hypotheses. Bundle C retains its
training-only, Label-free decorrelation rule.

## Lock, evaluation and inference

`RollingBlindCandidateBatchLockV2` freezes candidate type, DSL/model identity,
parameters, orientation, residualization or relevance contract, Feature
Bundle, primary statistic, strategy and Discovery order.

Every locked candidate runs all 18 windows. Residual candidates report raw and
residual RankIC plus Qlib portfolio evidence. Ranking candidates train only on
dates before each window and report RankIC, NDCG@20, deterministic same-day
random NDCG baseline, Top20 spread and Qlib portfolio evidence.

The unchanged rolling gate is combined with:

- residual median RankIC no worse than raw median RankIC; or
- ranking median NDCG@20 above the random baseline.

All candidate primary tests share one Benjamini-Hochberg family at `q=0.10`.

## Survivor and Fresh boundary

A passing object is an immutable `RollingEvaluationAlphaSurvivorV1` in
`research_registered` state. It records historical rolling passage,
`real_fresh_validated=false` and `production_eligible=false`. A no-backfill
Fresh Lock is separate from the existing model Fresh Cohort. This contract has
no Promotion, activation, trading or production authority and does not create
Batch 003.

## Recovery

Residualization and ranking contracts, every Agent round, the Batch Lock,
every window result, global multiple testing, Search Exposure, submission
ledger and terminal Report are immutable checkpoints. Exact replay performs
zero Agent, model-training, Qlib, Tushare, network, Candidate, Fresh Lock,
Registry, Promotion, Artifact or Blob writes.
