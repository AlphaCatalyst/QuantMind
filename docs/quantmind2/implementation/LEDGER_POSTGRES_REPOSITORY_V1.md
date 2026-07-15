# Ledger PostgreSQL Repository v1

## 1. Scope

This contract realizes the frozen Implementation Ledger behavior over the
`quantmind2` PostgreSQL schema. It covers asynchronous repositories, transaction
ownership, concurrency control, and typed reads. It does not parse manifests,
inspect Git, expose APIs, or deploy the schema to a persistent database.

## 2. Async Repository Architecture

`AsyncLedgerRepository` mirrors the synchronous domain Repository contract.
`PostgresLedgerRepository` implements all Task, Run, Relationship, Detail,
Reference, Annotation, batch, and history methods with SQLAlchemy 2.x async
statements. Domain remains free of SQLAlchemy and asyncio.

## 3. Sync Contract Compatibility

The A1b2 synchronous contract is authoritative. The PostgreSQL implementation
returns the same immutable Domain values and stable domain errors. Shared
scenarios execute against `InMemoryLedgerRepository` and PostgreSQL; the full
in-memory suite remains the reference regression.

## 4. Session Injection

`PostgresLedgerRepository(session)` accepts one caller-owned `AsyncSession`. It
never creates, commits, rolls back, or closes a Session. ORM rows are mapped to
Domain values before returning; no lazy ORM state escapes the Repository.

## 5. Unit of Work

`AsyncLedgerUnitOfWork` accepts an injected Session, an async Session factory,
or the shared `DatabaseManager`. Its Repository and all sub-repository views use
exactly that Session. The shared manager exposes `create_master_session()` from
its existing engine/sessionmaker rather than creating a second engine path.

## 6. Transaction Ownership

Callers must explicitly `await uow.commit()`. Exit without commit and exception
exit roll back. Commit failure rolls back and becomes `LedgerTransactionError`.
Duplicate terminal actions and writes after commit/rollback fail. UoW-owned
Sessions close on exit; an injected Session remains caller-owned.

## 7. Exact Replay

Create and append first read by frozen identity. Equal Domain content returns
the stored value without write or version increment. A concurrent uniqueness
race is contained by a savepoint, followed by a fresh read at PostgreSQL's
default READ COMMITTED isolation and the same equality check.

## 8. Immutable Conflict

Different content under the same natural or technical identity raises
`ImmutableEntityConflictError` (or the frozen relationship natural-key
`DuplicateChildEntityError`). Existing rows are never merged, overwritten, or
updated by create/append methods; no `ON CONFLICT DO UPDATE` is used.

## 9. Savepoints

Potentially competing inserts use `begin_nested()`. An `IntegrityError` rolls
back only the insert savepoint, preserving the outer UoW transaction so the
stored row can be reconstructed and classified. The atomic batch adds an outer
savepoint so a late child failure removes every earlier row from that batch.

## 10. Constraint Error Translation

Constraint names are obtained from driver diagnostics and cause chains, never
localized message parsing. Known identity constraints enter replay/conflict
handling. Unknown CHECK/FK/unique failures become safe
`LedgerConstraintViolationError`; transport/driver failures become
`LedgerPersistenceUnavailableError`. SQL, URLs, credentials, and ORM reprs are
not included. Mapper failures retain only object type, safe identity, and mapper
error code.

## 11. Task Repository

Task create/get/require/version/list/status update are implemented. Parent
existence is checked before insert. Lists filter by status and parent, count
before pagination, and order by `(created_at, task_id)`. Status changes use the
frozen matrix and one conditional `UPDATE ... WHERE version = expected`; valid
changes increment version, exact no-ops do not, and stale writes fail.

## 12. Run Repository

Run create/get/require/version/list are implemented. Typed filters cover Task,
Run status, canonical/consistency status, component, ADR, current/previous file
path, time bounds, pagination, and fixed ascending/descending ordering by
`(started_at, implementation_run_id)`. Relationship filters use `EXISTS`, so
one Run cannot be duplicated.

## 13. Run Finalization

Only `running` may be finalized. The terminal Domain object is validated before
SQL. Run identity fields remain equal and canonical status cannot change.
Only the explicit completion/result/hash/consistency allowlist is updated with
an expected-version predicate. A terminal Run cannot be finalized again.

## 14. Consistency and Canonical Updates

Consistency and canonical setters validate enum values, expected version, and
Domain combinations. Canonical changes additionally use the frozen transition
matrix; the Domain enforces committed/complete/consistent/result gates. Exact
no-ops do not increment version and no automatic promotion exists.

## 15. Relationship DAG Admission

Both endpoints must already exist. Every relationship type participates in one
directed graph. Exact ID replay, natural-key collision, self-edge Domain rules,
cycle rejection, stable incoming/outgoing lists, and existence checks preserve
the A1b2 contract.

## 16. Advisory Graph Lock

Admission takes `pg_advisory_xact_lock(6550840103452820112)`, the stable signed
64-bit key assigned to `quantmind2-ledger-relationship-graph-v1`. The lock is
transaction scoped and is released on commit or rollback. It serializes the
read-cycle-insert decision across independent processes and Sessions.

## 17. Recursive CTE

Cycle detection starts with all targets reachable from the proposed target and
recursively follows outgoing edges. If the proposed source is reachable, the
new edge would close a cycle. The CTE is one database query and uses `UNION` to
deduplicate visited nodes. Its work is proportional to the reachable graph in
v1; the conservative global graph lock limits admission throughput but is
appropriate for low-frequency Implementation Ledger writes.

## 18. Detail Repository

ChangedFile, ChangedSymbol, TestExecution, and ImplementationArtifact are
append-only. Parent Run checks, official mappers, exact replay/conflict, and
stable type-specific ordering are enforced. No update/delete method exists.

## 19. Reference Repository

ComponentReference and ArchitectureDecisionReference are append-only composite
identities. The Repository does not read Component Catalog or ADR documents and
does not infer references.

## 20. Annotation Repository

Limitation and RecommendedTask are append-only. The Repository neither mutates
limitation status in place nor creates the recommended Task object.

## 21. Atomic Batch

`record_run_details_atomic` creates/replays one Run and all eight child families
in the same Session and outer savepoint. It never commits. Exact replay is
idempotent; parent, identity, or late child conflict rolls back the entire batch
while leaving the surrounding UoW usable.

## 22. Query and Pagination

List operations use one count query and one ordered batch select. No per-row
child lookup or arbitrary SQL sort expression exists. Existing 0001 indexes are
used as defined; this task adds no speculative index or migration.

## 23. File, Component, and ADR History

`HistoryQuery` retains its exactly-one-target validation. File history matches
both current and rename previous paths. Component and ADR history use correlated
`EXISTS`. Results are paginated after total calculation and stably ordered.

## 24. Optimistic Concurrency

Task and Run mutable operations compare an explicit expected version, execute a
single conditional update, increment by one, and report actual version on a
lost race. Two independent PostgreSQL Sessions verify that only one stale
version update succeeds.

## 25. Contract Parity

The shared parity scenario covers replay, Domain equality, child behavior,
relationship cycle rejection, ordering, and returned collections across the
in-memory and PostgreSQL implementations. Dedicated PostgreSQL tests additionally
cover the database-only savepoint, advisory-lock, rollback, and race semantics.

## 26. PostgreSQL Concurrency Verification

Tests apply formal migration 0001 to a random, loopback-only, no-volume
`postgres:15-alpine` container. Independent Sessions verify same-content Task
replay, different-content conflict, stale version, opposing-edge cycle race,
and simultaneous batches sharing a technical child ID. Only one admissible row
or batch remains in each race and the container is removed afterward.

## 27. Error Safety and Known Limitations

The public boundary does not expose SQLAlchemy/driver exceptions or secrets.
V1 uses a whole-graph relationship lock and no read-only UoW optimization.
PostgreSQL 15 was verified with an existing SQLAlchemy 2.0.51/asyncpg 0.31.0
environment; the repository's pinned SQLAlchemy 2.0.25/asyncpg 0.29.0 runtime
parity still requires its normal deployment environment. No production database
was migrated and no CI schedule for the opt-in container test is established.

## 28. Handoff to Manifest Indexer

The next bounded task is `QM2-P0-002B — Manifest Parser, Git Consistency and
Ledger Indexer`. It may consume this UoW and Repository but must retain Git as
authority, explicitly bind repository identity, and must not move manifest or
Git parsing into this persistence layer.
