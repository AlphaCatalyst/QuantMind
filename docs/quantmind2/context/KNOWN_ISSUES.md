# Known Issues

## QM2-KI-058 — Weak-Alpha model aggregation produced no Candidate

Open, medium. Three preregistered fixed-configuration LightGBM Bundles
completed four purged expanding Folds. Existing-core mean RankIC was only
`0.000643`; expanded and combined Bundles were negative. All adjusted
q-values were `0.917134`, so no Retrospective Model Candidate, Fresh Lock or
Fresh Cohort exists. The model-concentration gates passed, but seed prediction
correlations were materially below one and predictive RankIC was unstable.
This negative result does not authorize hyperparameter search, report-period
selection, gate relaxation, new technical Feature generation or Cycle 004.

## QM2-KI-059 — Qlib does not expose durable model-program holdings/trades

Open, medium. The existing formal Qlib consumer returns NAV, performance,
turnover and aggregate CnExchange cost evidence but not durable daily holdings
or trade tables through this service boundary. Model Fold Artifacts preserve
explicit empty schemas rather than synthesizing executions. This does not
affect formal Qlib aggregate metrics, but holdings/trade-level attribution is
unavailable.

## QM2-KI-057 — Expanded technical space produced no candidate

Open, medium. Factory 002 admitted and materialized 20 new unlabeled technical
features, but Supervisor Cycle 002 completed 18 Alpha rounds and 68 formal
Qlib calls with zero Retrospective Candidates under unchanged archetype,
default-first and global FDR gates. No Fresh Lock, Cohort or Promotion exists.

## QM2-KI-056 — Current authorized autonomous space produced no new candidate

Resolved by successor. The first Supervisor Cycle reused the current immutable
Feature-Catalog/Alpha-Program revision and correctly made zero repeated
Agent/Qlib calls. QM2-R2-006 supplied and evaluated genuinely new authorized
research space without repetition or relaxed gates.

## QM2-KI-055 — No project-level mature Fresh evidence

Open, high. All project-visible market evidence through 2026-07-23 is exposed
and `retrospective_research_only`. The Supervisor has no Candidate, Fresh
Lock, Cohort, mature observation, Fresh support or Promotion evidence.

## QM2-KI-054 — Autonomous technical/archetype search found no survivor

Open, medium. `QM2-R2-004` expands the Terminal Feature space by two admitted
research Features and tests both monotonic and top-tail Archetypes. Nine Union
objects enter locked 2021–2024 Validation, but none passes the unchanged
Archetype gate and global 10% BH FDR together. This is a valid negative
retrospective result, not permission to relax gates or use report/Fresh data.

## QM2-KI-053 — Optional Qlib service dependencies emit warnings

Open, low. Formal local Qlib backtests complete through the real Strategy,
Executor and Exchange chain, but the existing wrapper first probes unavailable
PostgreSQL model registry and COS `/data`, then falls back to the supplied
signal and local Qlib view. The warnings do not convert the run to mock
evidence, but should remain visible.

| ID | Severity | Status | Summary |
|---|---|---|---|
| QM2-KI-051 | medium | resolved | QM2-R1-008 proves fixed ten-session rebalancing reduces median annual turnover 34.54% and cost 33.21%, but none of four pre-registered signals passes all frozen RankIC/stability gates; the result is `stock_selection_signal_only` with zero Candidate Locks. |
| QM2-KI-052 | low | open | The isolated Redis-disabled formal Qlib result persists daily positions but an empty trade list. R1-008 derives holding transitions from positions and turnover/cost from the existing CnExchange collector; per-trade execution audit remains unavailable. |

## QM2-KI-046 — Skip-recent signals are not standalone Alpha evidence

Open, medium. `QM2-R1-004` finds positive but weak 2025 RankIC followed by
negative 2026H1 RankIC and negative stock-selection residual. Costs and
holding concentration do not explain the failure. The two signals remain
research-only and may be studied only as stock-selection overlays; this is not
Fresh Validation or Promotion evidence.

## QM2-KI-045 — Skip-recent continuation is negative

Resolved by successor, medium. `QM2-R1-003` repaired forward research-artifact completeness and
produced two fully replayable research locks, but both locks and their
two-family ensemble underperform CSI300 in contaminated 2025 and 2026H1
reports. They are not eligible for Promotion or production use.

## QM2-KI-044 — no robust Fixed-100 daily momentum lock

Open, medium. `QM2-R1-002` explored eight momentum families with 13 admitted
Templates and 37 Trials. One candidate passed standalone eligibility, but the
frozen final gate requires at least two eligible families. No candidate was
locked and no later-period/ensemble evidence was opened. Thresholds were not
relaxed and no extra round was added.

## QM2-KI-043 — Qlib target-weight observability

Open, medium. Existing formal TopKDropout results persist actual positions but
not the pre-trade target-weight object. QM2-P0-016 preserves deterministic
Portfolio Targets separately and marks target-to-actual-target equality not
verifiable. Actual positions are not relabeled as targets.

| ID | Severity | Status | Issue |
|---|---|---|---|
| QM2-KI-001 | high | resolved | ADR-0011 supersedes the unverified TongDaXin provider choice; Tushare Pro is active and the legacy data authority is retired and purged. |
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
| QM2-KI-012 | high | resolved | QM2-P0-005 implements bounded deterministic Factor Optimization v1 for declared lookback-window and factor-internal-weight parameters. Predictive validation, threshold, random/Bayesian and distributed search remain separate future scope. |
| QM2-KI-013 | high | open | V7 Factor Lab combines Python-first research decisions, concrete parameters, loop control, dispatch, and result feedback without a formal ResearchDecision/Decision Validator boundary. |
| QM2-KI-014 | high | resolved | Ledger schema now has a dedicated ordered explicit-SQL runner with history, checksum, lock, up/down, and fresh-install integration; unrelated legacy schema paths remain outside this resolution. |
| QM2-KI-015 | high | open | Shared async session contexts auto-commit, while many services also commit internally, so transaction ownership is inconsistent for future atomic Ledger indexing. |
| QM2-KI-016 | high | open | Database configuration contains credential-bearing defaults in several files, and shared async engine initialization may log the complete database URL. |
| QM2-KI-017 | medium | open | A disposable opt-in PostgreSQL integration test exists and passes locally; CI PostgreSQL capability and scheduling remain unconfirmed. |
| QM2-KI-018 | medium | open | Context schema v1 cannot encode fine-grained task IDs such as `QM2-P0-002A2a2`; machine-readable next-task lists temporarily use parent `QM2-P0-002`. |
| QM2-KI-039 | medium | open | Tushare authority is locked through 2026-06-23; incremental collection, late-data revision policy and scheduled publication are not implemented. |
| QM2-KI-040 | high | open | QM2-P0-015 Tushare fixed-100 signals have 0% NaN in 2026H1, but formal Qlib rejects the isolated interval because only 98 locked symbols have effective observations while the precheck requires 100. Dropping, replacing, filling or relaxing the gate is forbidden without a separate contract decision. |
| QM2-KI-019 | medium | resolved | Manifest v2 directly represents every current Ledger Domain family; immutable historical v1 Runs retain their original gaps. |
| QM2-KI-020 | medium | resolved | In-memory remains a test double; the async PostgreSQL Repository now has isolated PostgreSQL 15 transaction, rollback, savepoint, constraint, and cross-Session concurrency evidence. |
| QM2-KI-021 | medium | resolved | Ledger migration, Repository/UoW, Manifest/Git indexing and CLI exist; production deployment and API/UI remain separate open scope. |
| QM2-KI-022 | low | open | Real PostgreSQL 15 Repository behavior passed with SQLAlchemy 2.0.51 and asyncpg 0.31.0; pinned SQLAlchemy 2.0.25 and asyncpg 0.29.0 runtime parity remains outstanding. |
| QM2-KI-023 | high | resolved | ADR-0010 and the Indexer require explicit trusted logical-ID to worktree binding; Manifest v1 absolute path remains informational. |
| QM2-KI-024 | medium | resolved | Manifest v2 records and validates explicit `repository_path` or `uri` location kind before constructing the unchanged Domain object. |
| QM2-KI-027 | medium | open | The adjacent 2025 feature sidecar describes older bytes; exact Parquet bytes, not the stale sidecar, are authoritative for Legacy source identity. |
| QM2-KI-028 | high | open | Existing LightGBM training and Qlib still consume their legacy feature/Qlib views rather than the real immutable Legacy Dataset Snapshot. |
| QM2-KI-029 | high | resolved | Manifest v2 self-reference is rejected for new Runs; committed v2 self-reference is narrowly warned and excluded from ChangedFile mapping without weakening other Git evidence. |
| QM2-KI-030 | low | resolved | The 003LF post-commit PostgreSQL test referenced nonexistent `AnalyzedRun.git_consistency`; QM2-P0-003LF1 now uses the public `evidence.consistent` and `evidence.warnings` contract, and all four real opt-in tests pass. |
| QM2-KI-031 | medium | open | The current official Factor Lab bounded source references FactorSpec, CandidateManifest, admission, evaluator and sandbox modules whose source files are absent from that directory; QM2-P0-004 reused only surviving contract and runbook evidence. |
| QM2-KI-032 | high | resolved | QM2-P0-008 historical external calls remain immutable failures. QM2-P0-008F identified `invalid_json_schema`, added semantic Provider-schema normalization and safe classified diagnostics, and completed one admitted external Codex Campaign without changing ResearchDecision or Campaign controls. |
| QM2-KI-033 | high | resolved | Baseline and External Campaigns produced sibling Registry snapshots. QM2-P0-008G reconciled them into one immutable multi-parent canonical Snapshot without rewriting either branch. |
| QM2-KI-034 | high | open | The 2026 source ends before the 2026-07-17 Candidate Lock. Fresh Validation is awaiting its first strictly post-lock date and no real result exists. |
| QM2-KI-035 | medium | resolved | QM2-P0-010 implements the persistent content-addressed Store and migrates the complete current reachable research graph; QM2-P0-011 completes the Store-backed runtime cutover and recovery drill. |
| QM2-KI-037 | medium | open | Artifact Store and Runtime v1 are single-host filesystem components; NFS, cloud object storage, distributed locking/cache and deletion GC are deliberately unsupported. |
| QM2-KI-038 | medium | resolved | QM2-P0-010 omitted only its own Manifest from both integrity Git inventories. The original Run remains immutable, inconsistent and non-indexable; QM2-P0-010F records the exact 42 changed / 28 added path evidence and a `corrects` relationship without changing Store behavior or artifacts. |
| QM2-KI-036 | medium | resolved | QM2-P0-009 omitted 23 of 35 Git-proven business ChangedFiles. The original Run remains inconsistent; QM2-P0-009F adds complete immutable correction evidence and a `corrects` relationship. |
| QM2-KI-040 | high | resolved | QM2-P0-015F proves the two missing 2026H1 members were already delisted and adds an explicit lifecycle-aware Qlib capacity contract; all four historical strategies complete without replacement or fill. |
| QM2-KI-041 | high | open | The governed Tushare Artifact graph has no cash, conversion, merger-exchange or write-off settlement evidence for the two 2025 terminations. Strategy results are unaffected, but the 2025 and full-period Fixed-100 benchmark and related excess metrics remain noncanonical pending a formal Corporate Action Provider. |
| QM2-KI-042 | high | open | QM2-P0-015H live capability evidence confirms the current Tushare account cannot access issuer announcements (`anns_d`) or structured merger endpoints for either termination. The new Provider and Contract hard-block revisions; no allowed Tushare-only path currently supplies the missing settlement ratio, amount or date. |
| QM2-KI-047 | medium | open | Both R1-003 Templates have one three-point optimizable parameter, making F1 direct-neighbor and F2 full factor spaces identical. R1-005 preserves both evidence modes but cannot infer a factor search-size effect from their equality. |
| QM2-KI-048 | high | resolved | R1-005 finds likely overfit evidence for Candidate B's separate factor/strategy optimization and both Candidates' combined optimization. QM2-R1-006 applies default-first separate policies, diagnostic-only full search and suspended combined optimization to new research without changing historical objects. |
| QM2-KI-049 | medium | resolved_by_correction | The immutable R1-005 Manifest froze hashes before one trailing-whitespace cleanup, so the original Run remains non-indexable with `changed_file_hashes` and `source_bundle_hash` failures. R1-005F records commit-derived correction evidence and a `corrects` relationship without changing research results. |
| QM2-KI-050 | medium | resolved | QM2-R1-007 found zero eligible structures under default-first governance: all defaults exceeded turnover 45 and lacked positive excess/group evidence, and none of thirteen one-hop Trials rescued them. The task terminates without lowering gates, adding rounds, opening full search or creating Candidate/Promotion state. |
