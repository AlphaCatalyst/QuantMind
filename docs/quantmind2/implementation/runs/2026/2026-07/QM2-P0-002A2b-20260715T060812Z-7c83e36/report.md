# Implementation Report: QM2-P0-002A2b

## 1. Task Summary

- Run: `QM2-P0-002A2b-20260715T060812Z-7c83e36`
- Task: `Versioned Ledger Migration and Isolated PostgreSQL Verification`
- Result: completed, pending the task's single local commit at report creation
- Base: `7c83e36e5e7088a2f4c6ebdc570364a8d437a5cf`

## 2. Goal

Realize the frozen eleven-object Ledger ORM shape through one versioned,
reviewable, checksummed, transactional, lock-protected, reversible PostgreSQL
migration and prove it against a disposable real PostgreSQL instance.

## 3. Scope

- Explicit migration `0001`, manifest, history table, and contract document.
- Zero-dependency `psql` runner for plan/validate/status/up/down.
- Fresh-install invocation through the same DDL authority.
- Static contract tests and real PostgreSQL lifecycle/parity tests.
- Bounded Project Memory, schema-enum, validator, and regression updates.

## 4. Explicit Non-goals

No PostgreSQL Repository, Repository Protocol adapter, business Session/UoW,
Manifest Parser/Indexer, repository identity resolver, Git consistency service,
API, UI, TDX, Dataset Snapshot, Factor DSL/Optimization/Validation/Registry,
LightGBM change, Qlib change, production database migration, dependency install,
lockfile change, accepted ADR change, or Factor Lab modification.

## 5. Preflight State

- Repository: expected root, branch `master`, clean.
- Base commit: expected `7c83e36e5e7088a2f4c6ebdc570364a8d437a5cf`.
- Factor Lab: expected `c83192c2278767e03f008bc39197b1ba33bfb6a9`, clean and read-only.
- PostgreSQL client: 15.18; Docker Desktop engine: 29.6.1; Compose: 5.3.0.
- Unrelated dirty files: none.

## 6. What Changed

`data/migrations/quantmind2` now owns Ledger DDL. Manifest `0001` binds exact
up/down bytes to SHA-256. A standard-library runner validates bundles and owns
per-migration `psql` transactions under a stable advisory transaction lock.
The up path atomically creates the schema, infrastructure history, eleven
business tables, and history row. The guarded down path removes only the latest
known matching version without `CASCADE`. Deploy step 10 calls this runner.

Two test modules cover database-free contracts and an opt-in disposable
PostgreSQL 15 lifecycle. Context and handoff now state that migration/parity are
complete but production persistence and indexing are not.

## 7. Why It Changed

The prior system had a base SQL dump and manual upgrade files but no active
ordering, applied version, checksum, down path, lock, or isolated database
proof. Explicit SQL matches the accepted persistence audit and keeps deployment
DDL reviewable without introducing an unconfigured migration framework.

## 8. Files Changed

Added migration README/manifest/up/down, runner, migration contract, two test
modules, and this Run pair. Modified only the existing deploy entry, bounded
context/roadmap/catalog/issue documents and JSON, three context/manifest schema
enums, context validator, and two stale regression guards.

## 9. Important Classes / Functions / Documents

- `load_manifest`, `exact_sha256`, `status`, `up`, `down`, `run_psql`.
- `LEDGER_MIGRATION_RUNNER_VERSION = 1.0.0`.
- `ADVISORY_LOCK_KEY = 4379672674272511630`.
- `LEDGER_MIGRATION_AND_POSTGRESQL_V1.md`.
- Migration `0001_implementation_ledger`.

## 10. API Changes

None.

## 11. Database Changes

Migration `0001` defines schema `quantmind2`, infrastructure table
`_schema_migrations`, and 11 business tables. The ORM business shape totals 87
columns, 97 named constraints (11 PK, 12 FK, 7 UQ, 67 CHECK), and 49 explicit
indexes. No production or existing development database was changed.

## 12. Configuration / Environment Changes

No runtime configuration, dependency, or lockfile changed. Fresh install
requires `python3` plus its existing Docker CLI and invokes the runner against
`quantmind-db`. The integration test is opt-in through
`QM2_LEDGER_POSTGRES_INTEGRATION=1`.

## 13. Runtime Flow

`validate` checks manifest shape, ordered identities, path containment, UTF-8,
exact checksums, SQL scope, and exact table inventory. `up` begins a transaction,
locks, bootstraps history, rechecks applied checksum, skips or executes SQL,
inserts history, then commits. `down` requires the explicit destructive flag,
checks latest/checksum outside and inside the locked transaction, executes
reverse DDL/history cleanup, and commits only if plain schema removal succeeds.

## 14. Architecture Impact

This realizes the already frozen Implementation Ledger storage shape; it does
not change Domain, ORM, Mapper, Repository contracts, accepted ADRs, or Git's
authority. Migration infrastructure remains separate from the eleven domain
objects. Application Repositories do not own migration transactions.

## 15. Security Impact

Runner subprocesses use argv lists and SQL stdin, never shell command strings.
Passwords use `PGPASSWORD`, never argv or runner output, and known environment
secrets are redacted from database failures. SQL grants no broad privileges,
changes no role/password/search path, and uses explicit schema qualification.

## 16. Data Lineage Impact

No research, market, model, or production data changed. Git remains the
Implementation Run authority; `_schema_migrations` records database shape only.
The disposable test data was destroyed with its container.

## 17. Tests Executed

1. Database-free migration contract: 12 passed.
2. Disposable PostgreSQL lifecycle: 1 passed after correcting test harness
   connection argument and catalog-query issues found during initial runs.
3. First full relevant regression after context changes: 333 passed, 3 failed,
   247 subtests passed. All three failures were stale pre-migration context
   guards and were updated to the approved A2b/A3 state.
4. Context bootstrap: 35 named checks passed after migration-aware guards.
5. Final full relevant regression, JSON/hash/syntax/diff/Git guards: recorded in
   the paired manifest after execution.

## 18. Test Results

Real PostgreSQL 15 verified initial absence, first up, one migration history
row, complete catalog/ORM parity, minimum complete Unicode/JSONB/UTC data, all
18 required invalid writes, restrictive deletes, idempotent up, temporary-copy
checksum drift, failed-down atomicity with an unexpected object, successful
down, public sentinel survival, second up with identical parity, final down,
and container cleanup.

## 19. Known Limitations

- No PostgreSQL Repository, business Session/UoW, or database concurrency
  behavior exists.
- No Manifest Parser/Indexer or automatic Git-to-database indexing exists.
- No production database was migrated.
- Production execution-role/schema privilege governance is not frozen.
- CI does not yet schedule the opt-in Docker integration test.
- ORM expectations used an existing SQLAlchemy 2.0.51 environment; pinned
  2.0.25 parity remains to be confirmed.
- Mapper and technical identity versions are not business-table columns.

## 20. Compatibility / Migration Notes

The migration creates a new isolated schema and does not alter `public` tables.
Fresh-install Ledger creation is new and idempotent. Existing installations
must explicitly run `up`; this task did not run it against any persistent
database. The runner requires `psql` locally or `psql` inside a named Docker
container.

## 21. Rollback Notes

Before production use, `down --allow-destructive` is safe only for a database
whose latest applied Ledger migration matches the manifest. It intentionally
fails if unexpected schema objects exist. Code rollback is the single task
commit; no persistent database rollback was needed for this implementation run.

## 22. Remaining Work

Implement the production PostgreSQL Repository and explicit Unit of Work over
this verified schema. Manifest parsing/indexing, Git consistency, API/UI, and
production migration remain separate later work.

## 23. Recommended Next Task

`QM2-P0-002A3 — PostgreSQL Ledger Repository and Unit of Work` only.

## 24. Git / Workspace State

The task began clean, has no unrelated files, installs nothing, does not push,
and is intended to end with one local commit and a clean worktree. The manifest
captures the true pre-commit implementation state with `result_commit: null`
and `completed_uncommitted`, per the immutable Run protocol.

## 25. Artifact Index

- Migration contract: `docs/quantmind2/implementation/LEDGER_MIGRATION_AND_POSTGRESQL_V1.md`
- Migration manifest: `data/migrations/quantmind2/manifest.json`
- Up/down SQL: `data/migrations/quantmind2/0001_implementation_ledger.*.sql`
- Runner: `tools/quantmind2/ledger_migrations.py`
- Contract and integration tests under `backend/services/tests/`
- Paired machine manifest beside this report.
