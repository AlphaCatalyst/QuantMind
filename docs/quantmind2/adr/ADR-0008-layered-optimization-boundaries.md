# ADR-0008: Layered Optimization Boundaries

- ADR ID: ADR-0008
- Status: accepted
- Date: 2026-07-14
- Supersedes: none
- Superseded By: none
- Related Components: `quantmind2.factor_optimization`, `quantmind.training`, `quantmind.qlib_backtest`
- Related Implementation Runs: `QM2-P0-001-20260713T183614Z-e9b0c7d`

## Context

Factor parameters, model hyperparameters, and portfolio controls optimize
different objects and have different evidence and overfitting risks.

## Decision

Factor Optimization searches window, factor-internal weight, and signal
threshold. Model Optimization searches LightGBM hyperparameters. Portfolio
Optimization searches topk, n_drop, max_weight, rebalance, and risk controls.
They use separate task types, schemas, trials, objectives, and budgets.

## Consequences

Existing Qlib portfolio optimization cannot be relabeled as Factor
Optimization. Cross-layer experiments require explicit parent references.

## Alternatives Considered

A generic untyped optimization table was rejected because it erases semantic
and governance boundaries.

## Non-goals

This ADR does not choose the optimization algorithm beyond frozen v1 scope.
