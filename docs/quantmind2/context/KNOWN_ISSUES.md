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
| QM2-KI-014 | high | resolved | Ledger schema now has a dedicated ordered explicit-SQL runner with history, checksum, lock, up/down, and fresh-install integration; unrelated legacy schema paths remain outside this resolution. |
| QM2-KI-015 | high | open | Shared async session contexts auto-commit, while many services also commit internally, so transaction ownership is inconsistent for future atomic Ledger indexing. |
| QM2-KI-016 | high | open | Database configuration contains credential-bearing defaults in several files, and shared async engine initialization may log the complete database URL. |
| QM2-KI-017 | medium | open | A disposable opt-in PostgreSQL integration test exists and passes locally; CI PostgreSQL capability and scheduling remain unconfirmed. |
| QM2-KI-018 | medium | open | Context schema v1 cannot encode fine-grained task IDs such as `QM2-P0-002A2a2`; machine-readable next-task lists temporarily use parent `QM2-P0-002`. |
| QM2-KI-019 | medium | open | Manifest v1 cannot directly represent rich file/symbol changes, general Run relationships, structured limitations, or recommendation metadata defined by Ledger Domain Model v1. |
| QM2-KI-020 | medium | open | The in-memory Ledger Repository is a contract test double only: it has no durability, cross-process concurrency, database isolation, crash recovery, or PostgreSQL constraint evidence. |
| QM2-KI-021 | medium | open | Ledger migration and isolated PostgreSQL parity now exist, but production migration, PostgreSQL Repository, business Session/UoW, and indexing remain absent. |
| QM2-KI-022 | low | open | Real PostgreSQL 15 parity passed with SQLAlchemy 2.0.51 expectations; pinned SQLAlchemy 2.0.25 runtime parity remains outstanding. |
| QM2-KI-023 | high | open | Manifest v1 `repository_root` is an execution absolute path while frozen Domain/ORM `repository_root` is now contractually a logical repository identity; future indexing requires explicit trusted binding and a future ADR/Manifest v2 decision. |
| QM2-KI-024 | medium | open | ImplementationArtifact has one `path_or_uri` field and no explicit location kind; existing Domain prefix semantics are deterministic, but Manifest v2 should record producer intent. |
