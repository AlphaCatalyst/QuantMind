# ADR-0003: TongDaXin Ingestion and Dataset Snapshot Authority

- ADR ID: ADR-0003
- Status: accepted
- Date: 2026-07-14
- Supersedes: none
- Superseded By: none
- Related Components: `quantmind2.data_foundation`, `quantmind.feature_snapshots`
- Related Implementation Runs: `QM2-P0-001-20260713T183614Z-e9b0c7d`

## Context

Existing PostgreSQL, Parquet, scripts, and Qlib binary do not form one explicit
research-data authority. The concrete TongDaXin implementation is unverified.

## Decision

The fixed chain is TongDaXin Provider → immutable Raw Data → Normalization →
Dataset Snapshot → Factor/Feature Materialization → Parquet and Qlib consumer
views. Dataset Snapshot is authoritative. PostgreSQL stores control and index
data; Parquet stores large materializations; Qlib binary is a consumer view.

## Consequences

Partially updated data cannot be consumed. Every derived artifact records
source Snapshot lineage. Provider capabilities require evidence before use.

## Alternatives Considered

Qlib binary or `stock_daily_latest` as the sole authority was rejected because
neither captures the complete immutable source and derivation lineage.

## Non-goals

This ADR does not select or install a TongDaXin dependency.
