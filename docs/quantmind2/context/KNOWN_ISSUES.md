# Known Issues

| ID | Severity | Status | Issue |
|---|---|---|---|
| QM2-KI-001 | blocker | open | Formal TongDaXin Provider implementation is unverified. |
| QM2-KI-002 | high | open | Submitted `label_formula` metadata does not drive the training script's actual tradable-return label construction. |
| QM2-KI-003 | high | open | Daily data task references a missing Qlib synchronization script. |
| QM2-KI-004 | high | open | Existing Qlib conversion deletes/replaces the destination non-atomically. |
| QM2-KI-005 | high | open | PostgreSQL, Parquet, and Qlib authority is not unified by Dataset Snapshot. |
| QM2-KI-006 | high | open | Official Factor Lab candidate contract remains Python-first. |
| QM2-KI-007 | high | open | Factor Lab JSON experiment registry can replace historical records by ID. |
| QM2-KI-008 | high | open | Anti-overfit `recent` is not an access-isolated Frozen Test. |
| QM2-KI-009 | high | open | Official Factor Lab source is currently under `/tmp`, creating durability risk. |
| QM2-KI-010 | medium | open | Project Knowledge Center API and UI do not exist. |
| QM2-KI-011 | medium | open | Implementation Ledger database index does not exist. |
| QM2-KI-012 | high | open | Formal Factor Optimization does not exist. |
| QM2-KI-013 | high | open | V7 Factor Lab combines Python-first research decisions, concrete parameters, loop control, dispatch, and result feedback without a formal ResearchDecision/Decision Validator boundary. |
| QM2-KI-014 | high | open | PostgreSQL schema change is fragmented across bootstrap SQL, manually documented upgrade SQL, runtime raw DDL, and metadata `create_all`; no operational Alembic or ordered applied-version runner is code-confirmed. |
| QM2-KI-015 | high | open | Shared async session contexts auto-commit, while many services also commit internally, so transaction ownership is inconsistent for future atomic Ledger indexing. |
| QM2-KI-016 | high | open | Database configuration contains credential-bearing defaults in several files, and shared async engine initialization may log the complete database URL. |
| QM2-KI-017 | medium | open | No shared isolated PostgreSQL fixture or CI PostgreSQL service is confirmed; SQLite and mocked Session tests do not prove PostgreSQL schema, JSONB, concurrency, or transaction behavior. |
| QM2-KI-018 | medium | open | Context schema v1 cannot encode fine-grained task IDs such as `QM2-P0-002A2a2`; machine-readable next-task lists temporarily use parent `QM2-P0-002`. |
| QM2-KI-019 | medium | open | Manifest v1 cannot directly represent rich file/symbol changes, general Run relationships, structured limitations, or recommendation metadata defined by Ledger Domain Model v1. |
| QM2-KI-020 | medium | open | The in-memory Ledger Repository is a contract test double only: it has no durability, cross-process concurrency, database isolation, crash recovery, or PostgreSQL constraint evidence. |
| QM2-KI-021 | medium | open | Core and core-detail Ledger ORM metadata now covers seven objects; reference/annotation mappings, domain mappers, migration, schema deployment, production Repository, UoW, and PostgreSQL integration evidence remain absent. |
| QM2-KI-022 | low | open | Static DDL verification used an existing SQLAlchemy 2.0.51 environment while production requirements pin 2.0.25; pinned-runtime and real PostgreSQL verification remain outstanding. |
