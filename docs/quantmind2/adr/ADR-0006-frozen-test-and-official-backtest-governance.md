# ADR-0006: Frozen Test and Official Backtest Governance

- ADR ID: ADR-0006
- Status: accepted
- Date: 2026-07-14
- Supersedes: none
- Superseded By: none
- Related Components: `quantmind2.factor_validation`, `quantmind.qlib_backtest`, `quantmind.risk`
- Related Implementation Runs: `QM2-P0-001-20260713T183614Z-e9b0c7d`

## Context

Repeated tuning on final evaluation data invalidates research conclusions, and
fast research backtests are not equivalent to official portfolio simulation.

## Decision

Agent, Optimizer, and Campaign Memory cannot access Frozen Test. Only a final
authorized Validation Run may access it. Once observed, tuning cannot continue
in that Experiment. Official return and risk conclusions require real Qlib;
mock, fixture, fallback, and temporary chains are excluded.

## Consequences

Access control, audit logs, Experiment closure, and explicit evidence types are
required before production validation.

## Alternatives Considered

Treating a recent split as Frozen Test was rejected because it lacks access and
iteration isolation.

## Non-goals

This ADR does not implement validation splits or permissions.
