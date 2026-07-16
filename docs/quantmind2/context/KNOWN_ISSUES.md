# Known Issues

| ID | Severity | Status | Issue |
|---|---|---|---|
| QM2-KI-001 | high | open | Legacy TongDaXin scripts require absent proprietary `tqcenter`; pytdx/mootdx, local client/data root, explicit source units, rate limits and license semantics are unavailable. The legacy feature route is usable, but no real TDX Daily Bars Snapshot exists. |
| QM2-KI-002 | high | open | Submitted `label_formula` metadata does not drive the training script's actual tradable-return label construction. |
| QM2-KI-003 | high | open | Daily data task references a missing Qlib synchronization script. |
| QM2-KI-004 | high | open | Existing Qlib conversion deletes/replaces the destination non-atomically. |
| QM2-KI-005 | high | open | Dataset Snapshot v1 now exists, but current PostgreSQL, annual feature Parquet, and Qlib binary consumers have not migrated to it. |
| QM2-KI-006 | high | open | Official Factor Lab candidate contract remains Python-first. |
| QM2-KI-007 | high | open | Factor Lab JSON experiment registry can replace historical records by ID. |
| QM2-KI-008 | high | open | Anti-overfit `recent` is not an access-isolated Frozen Test. |
| QM2-KI-009 | high | open | Official Factor Lab source is currently under `/tmp`, creating durability risk. |
| QM2-KI-010 | medium | open | Project Knowledge Center API and UI do not exist. |
| QM2-KI-011 | medium | resolved | Git-to-Ledger parser/indexer exists; production deployment remains separate. |
| QM2-KI-025 | high | open | Manifest v1 cannot construct complete Ledger Domain Bundles without inventing Task and child semantics; 0/17 historical v1 Runs are indexable. Manifest v2 resolves only future production. |
| QM2-KI-026 | high | open | QM2-P0-001F declares a result commit that differs from its containing commit. |
| QM2-KI-012 | high | open | Formal Factor Optimization does not exist. |
| QM2-KI-013 | high | open | V7 Factor Lab combines Python-first research decisions, concrete parameters, loop control, dispatch, and result feedback without a formal ResearchDecision/Decision Validator boundary. |
| QM2-KI-014 | high | resolved | Ledger schema now has a dedicated ordered explicit-SQL runner with history, checksum, lock, up/down, and fresh-install integration; unrelated legacy schema paths remain outside this resolution. |
| QM2-KI-015 | high | open | Shared async session contexts auto-commit, while many services also commit internally, so transaction ownership is inconsistent for future atomic Ledger indexing. |
| QM2-KI-016 | high | open | Database configuration contains credential-bearing defaults in several files, and shared async engine initialization may log the complete database URL. |
| QM2-KI-017 | medium | open | A disposable opt-in PostgreSQL integration test exists and passes locally; CI PostgreSQL capability and scheduling remain unconfirmed. |
| QM2-KI-018 | medium | open | Context schema v1 cannot encode fine-grained task IDs such as `QM2-P0-002A2a2`; machine-readable next-task lists temporarily use parent `QM2-P0-002`. |
| QM2-KI-019 | medium | resolved | Manifest v2 directly represents every current Ledger Domain family; immutable historical v1 Runs retain their original gaps. |
| QM2-KI-020 | medium | resolved | In-memory remains a test double; the async PostgreSQL Repository now has isolated PostgreSQL 15 transaction, rollback, savepoint, constraint, and cross-Session concurrency evidence. |
| QM2-KI-021 | medium | resolved | Ledger migration, Repository/UoW, Manifest/Git indexing and CLI exist; production deployment and API/UI remain separate open scope. |
| QM2-KI-022 | low | open | Real PostgreSQL 15 Repository behavior passed with SQLAlchemy 2.0.51 and asyncpg 0.31.0; pinned SQLAlchemy 2.0.25 and asyncpg 0.29.0 runtime parity remains outstanding. |
| QM2-KI-023 | high | resolved | ADR-0010 and the Indexer require explicit trusted logical-ID to worktree binding; Manifest v1 absolute path remains informational. |
| QM2-KI-024 | medium | resolved | Manifest v2 records and validates explicit `repository_path` or `uri` location kind before constructing the unchanged Domain object. |
| QM2-KI-027 | medium | open | The adjacent 2025 feature sidecar describes older bytes; exact Parquet bytes, not the stale sidecar, are authoritative for Legacy source identity. |
| QM2-KI-028 | high | open | Existing LightGBM training and Qlib still consume their legacy feature/Qlib views rather than the real immutable Legacy Dataset Snapshot. |
