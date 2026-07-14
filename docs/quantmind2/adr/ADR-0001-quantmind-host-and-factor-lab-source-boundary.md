# ADR-0001: QuantMind Host and Factor Lab Source Boundary

- ADR ID: ADR-0001
- Status: accepted
- Date: 2026-07-14
- Supersedes: none
- Superseded By: none
- Related Components: `factor_lab.official_v7_source`, `quantmind2.project_knowledge`
- Related Implementation Runs: `QM2-P0-001-20260713T183614Z-e9b0c7d`

## Context

QuantMind already owns model, inference, Qlib, strategy, backtest, and risk
capabilities. Factor Lab supplies research capabilities from a separate source.

## Decision

The QuantMind repository is the target host. The only official Factor Lab
source is `/tmp/quantmind_factor_lab_real_bounded_v7_orchestrator_v1/backend/services/engine/factor_lab/`.
Factor Lab is read-only unless a scoped migration task explicitly moves a
contract or module. Repositories are not copied or concatenated wholesale.

## Consequences

Migration is contract-driven. Existing QuantMind services keep ownership of
the back half. The temporary Factor Lab location is a recorded durability risk.

## Alternatives Considered

Whole-directory copy and the older QuantMind donor workspace were rejected as
non-authoritative and incompatible with controlled lineage.

## Non-goals

This ADR does not authorize copying, formatting, committing, or modifying
Factor Lab.
