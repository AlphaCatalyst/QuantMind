# ADR-0004: Reuse Existing LightGBM and Qlib

- ADR ID: ADR-0004
- Status: accepted
- Date: 2026-07-14
- Supersedes: none
- Superseded By: none
- Related Components: `quantmind.training`, `quantmind.inference`, `quantmind.qlib_backtest`, `quantmind.risk`
- Related Implementation Runs: `QM2-P0-001-20260713T183614Z-e9b0c7d`

## Context

QuantMind already has functional LightGBM training/inference and a Qlib
portfolio, exchange, execution, backtest, and risk chain.

## Decision

Retain these implementations. LightGBM combines feature-eligible factors and
must lock Factor Instance, Materialization, Dataset Snapshot, and Transform
versions. Formal returns and risk require real Qlib. Factor Lab SimpleTopK is
only a fast research screen.

## Consequences

New work is limited to explicit feature, model, signal, data, and experiment
contracts around the existing services.

## Alternatives Considered

Reimplementing LightGBM or Qlib was rejected as unnecessary and outside the
platform objective.

## Non-goals

This ADR does not change model algorithms or Qlib financial semantics.
