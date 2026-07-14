# ADR-0002: Canonical Factor DSL and Python Extension Boundary

- ADR ID: ADR-0002
- Status: accepted
- Date: 2026-07-14
- Supersedes: none
- Superseded By: none
- Related Components: `quantmind2.factor_dsl`, `quantmind2.factor_compute`, `factor_lab.official_v7_source`
- Related Implementation Runs: `QM2-P0-001-20260713T183614Z-e9b0c7d`

## Context

Factor Lab currently requires generated `factor_impl.py`, while QuantMind 2.0
needs canonical, parameter-searchable factor definitions.

## Decision

Canonical DSL AST is the authority for standard formula factors. v1 exposes
window, factor-internal weight, and signal threshold parameters and performs no
structure evolution. Python is excluded from the v1 standard path. A future
Python extension remains untrusted and Docker-only.

## Consequences

Agent output contracts must migrate from Python-first candidates to DSL
templates. Canonical hashing and deterministic compute become explicit duties.

## Alternatives Considered

Python source as the canonical factor definition was rejected because it is
difficult to normalize, compare, parameterize, secure, and reproduce.

## Non-goals

This ADR does not define operator implementation or permit local Python
execution.
