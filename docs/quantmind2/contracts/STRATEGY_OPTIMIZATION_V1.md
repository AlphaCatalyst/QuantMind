# Strategy Parameter Optimization Contract v1

Status: implemented by `QM2-P0-017`.

## Boundary

This service is Portfolio/Strategy Optimization under ADR-0008. It is not
Factor Optimization, model optimization, signal construction, risk control or
Promotion. Its only searched fields are `topk`, `n_drop` and the rebalance
interval measured in Qlib trade dates.

The frozen grid is TopK `[10, 20, 30]`, n_drop `[0, 5, 10]` and rebalance
interval `[1, 5, 10]`. `n_drop >= topk` is rejected before Trial creation,
leaving 24 combinations per signal and 96 across the four locked Unified
Signals. Weighting, signal transformation, one-trade-date lag, open execution,
CSI300, CnExchange costs, Universe and lifecycle semantics are fixed.

## Evidence protocol

Selection uses only 2019-01-02 through 2024-12-31, which is explicitly
`retrospective_contaminated_strategy_parameter_diagnostic`. Six annual formal
Qlib segments preserve actual annual costs, turnover and losing years. Trials
are ranked by the frozen lexicographic ordering: positive excess-year count,
median annual excess, worst annual excess, full-period Sharpe, drawdown,
turnover, cost and Trial ID.

Candidate Locks are immutable before 2025 and 2026H1 are run. Those later
periods are `retrospective_report_only`, were already exposed by predecessor
tasks, and never participate in eligibility, selection or tie-breaking. The
2026H1 execution uses the locked Fixed Universe Lifecycle Policy because two
members were delisted before the period; it does not replace members or fill
signals.

All output remains research-only: `predictive_claim=false`,
`usable_for_promotion=false` and `eligible_for_production=false`. Candidate
Lock does not mean validated, approved or active.

## Object and execution boundaries

```text
Unified Signal Artifact
→ StrategyOptimizationSpec / Study
→ deterministic StrategyOptimizationTrial
→ existing QlibBacktestService
→ immutable StrategyBacktestResult
→ annual metrics and eligibility
→ stable ordering
→ StrategyParameterCandidateLock
→ retrospective 2025 / 2026H1 report
→ StrategyOptimizationResult
```

Study IDs use `sos_`, Trial IDs `sot_`, Candidate Locks `spcl_` and Results
`sor_`. Trial identity binds the Study, signal, parameters, Strategy Spec and
formal Qlib Result. The Artifact Store kinds are separate and exact replay
must make zero Qlib, Agent and Factor Optimization calls.
