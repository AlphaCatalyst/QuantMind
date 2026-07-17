# Research Data Exposure Ledger v1

The ledger is append-only Git authority for research-period exposure. Each
record names its dataset/protocol, date range, exposure class, consumers,
purpose, adaptive flag, publication flag, and source artifacts. New exposure
creates a new content-addressed ledger snapshot; prior records cannot be
deleted or rewritten.

The initial snapshot records the adaptive 2025 Development period consumed by
Agent/control, formal 2024 Validation consumed by control/report/Registry, and
the non-adaptive 2026-01-05..2026-06-23 historical Frozen period consumed by
control/report/Registry. Candidate locking is a lock fact and does not claim
future data exposure. The additional already-generated source cutoff is
2026-06-24.

The global cutoff is the maximum of all published exposure ends and previously
available research data. Fresh start is strictly after both this cutoff and the
candidate lock market date. If a Fresh result later informs Agent or adaptive
control, that full window must be appended as adaptive exposure and cannot be
reused as fresh evidence.
