# ADR-0007: Immutable Research Identities and Lineage

- ADR ID: ADR-0007
- Status: accepted
- Date: 2026-07-14
- Supersedes: none
- Superseded By: none
- Related Components: `quantmind2.factor_registry`, `quantmind2.experiment_manager`, `quantmind2.signal_service`
- Related Implementation Runs: `QM2-P0-001-20260713T183614Z-e9b0c7d`

## Context

Definition, parameters, values, validation evidence, models, and results have
different lifecycles and cannot safely share a mutable record.

## Decision

Factor Definition, Factor Template, Factor Instance, Candidate, Optimization
Trial, Dataset Snapshot, Factor Value Materialization, Validation Result,
Feature Snapshot, Model, Signal Artifact, Backtest Result, Experiment, Run, and
Artifact are separate immutable identities linked by lineage.

## Consequences

Corrections create new versions. Consumers lock exact source IDs and hashes.
Registry transitions cannot rewrite historical evidence.

## Alternatives Considered

A single replaceable FactorSpec or experiment JSON was rejected due to
ambiguity and lost provenance.

## Non-goals

This ADR does not prescribe physical table names or storage technology.
