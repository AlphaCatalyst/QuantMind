# ADR-0005: Memory and Implementation Ledger Separation

- ADR ID: ADR-0005
- Status: accepted
- Date: 2026-07-14
- Supersedes: none
- Superseded By: none
- Related Components: `quantmind2.project_knowledge`, `factor_lab.official_v7_source`
- Related Implementation Runs: `QM2-P0-001-20260713T183614Z-e9b0c7d`

## Context

Factor Lab memory serves factor research, while long-term software development
requires architecture and implementation knowledge with different authority.

## Decision

Research Memory, Project Architecture Memory, and Implementation Ledger are
separate systems. Git stores code and immutable run artifacts; ADRs store
long-term decisions; Ledger stores implementation semantics; PostgreSQL later
indexes them for query and web display. Chat is not authoritative.

## Consequences

Current State and Handoff are derived summaries. Frozen architecture cannot be
silently changed by an ordinary implementation run.

## Alternatives Considered

A single chat summary or Campaign Memory store was rejected because it mixes
audiences, retention, approval, and confidentiality boundaries.

## Non-goals

This ADR does not define the future Ledger database implementation.
