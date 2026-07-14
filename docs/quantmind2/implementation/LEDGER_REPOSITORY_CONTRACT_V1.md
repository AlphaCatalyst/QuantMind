# Implementation Ledger Repository Contract v1

Status: implemented contract and test double
Task: `QM2-P0-002A1b2 — Ledger Repository Contract and In-memory Test Double`

## 1. Scope

This contract defines synchronous persistence-independent Repository Protocols,
immutable query values, stable Repository errors, and a standard-library-only
`InMemoryLedgerRepository` test double. It verifies identity, exact replay,
immutable conflicts, controlled status changes, optimistic-version semantics,
append-only details, graph cycles, stable queries, and atomic batch behavior.

It does not implement SQLAlchemy, PostgreSQL, a database schema/table,
migration, Session, production Unit of Work, Manifest Parser/Indexer, Git
consistency service, API, or UI.

## 2. Domain and Repository Boundary

Domain Model v1 continues to own single-object value and combination rules:
safe IDs/paths, hashes, commits, UTC times, frozen dataclasses, Run status
combinations, and relationship self-loops. Repository v1 owns cross-object
rules: identity uniqueness, parent existence, exact replay, versions, legal
updates, target existence, complete in-memory graph cycles, append-only child
uniqueness, filtering, and atomic contract verification.

Repository methods do not execute Git, read manifests, open artifacts, perform
I/O, commit transactions, or authorize business promotion.

## 3. Repository Interfaces

`typing.Protocol` is used because callers need structural behavior contracts,
not inheritance or framework coupling. The contract is synchronous so it can be
tested without an event loop, Session, or database. A future SQLAlchemy adapter
may expose async application methods while preserving these identities,
transitions, errors, and query results.

- `ImplementationTaskRepository`: Task creation, lookup, version, query, status.
- `ImplementationRunRepository`: Run creation, lookup, query, finalization,
  consistency, and canonical status.
- `RunRelationshipRepository`: immutable edges, direction queries, existence,
  and cycle preview.
- `RunDetailRepository`: append/list detail records, history, and atomic batch.
- `LedgerRepository`: aggregate access to the four contracts.

There is deliberately no generic `save`, full-object `update`, `delete`,
`replace_all`, Session, commit, or rollback method.

## 4. Identity and Uniqueness

| Entity | Identity / natural key |
| --- | --- |
| Task | `task_id` |
| Run | `implementation_run_id` |
| Relationship | `relationship_id`; natural key is source, target, type |
| ChangedFile | Run, path, change type |
| ChangedSymbol | Run, file path, qualified name |
| TestExecution | Run, test execution ID |
| Artifact | Run, artifact ID |
| ComponentReference | Run, component ID |
| ADRReference | Run, ADR ID |
| Limitation | Run, limitation ID |
| RecommendedTask | Run, recommendation ID |

Task and Run IDs are repository-global in v1. A Run requires an existing Task.
Every detail requires an existing parent Run. Relationships require both Runs.
Database constraints and repository scoping remain deferred.

## 5. Exact Replay Semantics

Every create/add/append operation follows one rule:

```text
same identity + equal frozen object → return existing object, no version bump
same identity + different object → ImmutableEntityConflictError
```

Atomic batch replay applies the same rule to the Run and every child. Repository
does not infer or create a `retries` relationship; callers must add it explicitly.

## 6. Immutable Conflict Semantics

No last-write-wins merge exists. Conflicting Task, Run, relationship, or child
content never overwrites the stored object. `ImmutableEntityConflictError`
contains only a stable entity type and validated identity. Duplicate natural
relationship keys with different IDs raise `DuplicateChildEntityError`.

## 7. Task State Updates

Tasks start at any valid imported state, but controlled updates use this graph:

```text
planned → ready | running | blocked | cancelled
ready → running | blocked | cancelled
running → completed | partial | blocked | cancelled
blocked → ready | running | cancelled
completed | partial | cancelled → terminal
```

Same-status replay is idempotent. A real change increments the version. The
caller supplies `expected_version`; stale values raise
`OptimisticConcurrencyError`. Task completion does not make a Run canonical.

## 8. Run Finalization Semantics

Only a stored `running` Run can be finalized, and only once. `terminal_run`
must preserve Run ID, Task ID, logical repository, branch, base commit,
workspace-before flag, start time, agent type, Manifest schema/path, and Report
path. It may add terminal result, completion, end time, hashes, verification,
and final workspace evidence as permitted by Domain Model v1.

Finalization cannot change canonical status. Canonical and consistency use
their explicit methods and expected versions. An uncommitted terminal Run is
never rewritten as committed: commit confirmation/finalization is represented
by a new Run and explicit `finalizes` relationship. Corrections likewise create
new Runs rather than editing history.

## 9. Run Relationship Semantics

All six edge kinds—`finalizes`, `corrects`, `supersedes`, `depends_on`,
`retries`, and `continues`—participate in one directed acyclic graph. Source and
target must exist. An edge is immutable; no delete or replace operation exists.
Exact replay is checked before cycle detection so it does not produce a false
cycle error.

## 10. Graph Cycle Detection

Before adding source → target, the test double performs iterative depth-first
search starting at target over existing outgoing edges. If source is reachable,
the new edge closes a cycle and raises `RunRelationshipCycleError`.

For vertices `V` and edges `E`, each check is `O(V + E)` time and `O(V)` space.
This is sufficient for contract tests and is not optimized for a large Ledger.
Future PostgreSQL enforcement/query strategy remains separate.

## 11. Child Entity Append-only Rules

Children may only be appended and listed. They cannot be deleted, replaced in
bulk, or moved to another Run. Natural-key replay returns the existing frozen
object; different content at the same key is an immutable conflict. List
methods return a newly created tuple, never an internal dictionary or list.

## 12. Query and Pagination Semantics

`TaskQuery`, `RunQuery`, and `HistoryQuery` are frozen dataclasses. `Page.items`
is a tuple. Limits are `1..200`, offsets are non-negative, times are UTC-aware,
paths reuse Domain Model v1 validation, and sort order is the fixed `asc/desc`
enum rather than a caller-supplied SQL field.

Run filtering supports Task, Run status, canonical, consistency, component,
ADR, file path, and inclusive start-time range. Filtering precedes sorting and
pagination. Runs sort by `(started_at, run_id)`; Task sort uses
`(created_at, task_id)`. `total` is computed before slicing. File history
matches current or previous rename paths. History queries accept exactly one
of path, component, or ADR.

Queries are side-effect-free and create no implicit index records.

## 13. Atomic Batch Contract

`record_run_details_atomic` accepts one Run plus all supported detail groups.
The in-memory test double shallow-copies every internal dictionary, applies the
Run and children to the isolated copy using ordinary contract methods, and
adopts all copied dictionaries only after every operation succeeds. Frozen
domain objects make shallow copying safe. A late conflict or missing parent
discards the copy and leaves the original instance unchanged.

This atomicity verifies all-or-nothing semantics only. It does not prove a
PostgreSQL transaction, isolation level, durability, crash recovery, or
multi-process behavior.

## 14. Transaction Ownership

No Repository method commits. Future Application Service / Unit of Work code
must own one formal transaction around Run creation and all related details.
Repository implementations must remain transaction-neutral. The shared async
manager selected in the persistence audit may host that transaction later, but
no Session or Unit of Work is defined here.

## 15. In-memory Test Double Boundary

`InMemoryLedgerRepository` is instance-local, synchronous, process-local,
non-durable, and standard-library-only. Python insertion-ordered dictionaries
store immutable values; integer version dictionaries model expected-version
checks. No global singleton or `clear_all` exists—tests reset state by creating
a new instance. It does not simulate SQL, locks, indexes, isolation, latency,
serialization, or database failure.

It is a test double, not the default, canonical, or production Ledger.

## 16. Rules Deferred to ORM

- SQLAlchemy mapping and async adapter design;
- PostgreSQL column types, enum serialization, foreign keys, indexes, and
  optimistic version columns;
- transaction/session injection and row locking;
- persistence serialization and database error translation.

## 17. Rules Deferred to Migration

- `quantmind2` schema and table creation;
- versioned upgrade SQL, order/checksum tracking, bootstrap reconciliation;
- role privileges, rollback, operational invocation, and deployment evidence.

No table, schema, metadata, Column, SQL, migration, or runtime DDL exists here.

## 18. Rules Deferred to Manifest Indexer

- Manifest v1 parsing and vocabulary mapping;
- Git object/report/hash verification and containing-commit resolution;
- rebuild/reconciliation, source precedence, corrections, and stale detection;
- atomic orchestration of parsed Run plus all details.

Git Manifest and Report files remain authoritative; Repository data is a
future derived query index.

## 19. Error Catalog

The Repository layer defines `LedgerRepositoryError`, Task/Run/Relationship
already-exists and not-found errors, `ImmutableEntityConflictError`,
`OptimisticConcurrencyError`, `RunRelationshipCycleError`,
`InvalidStateTransitionError`, `DuplicateChildEntityError`, and
`RepositoryQueryError`. Errors do not inherit HTTP or database exceptions and
carry safe IDs rather than object contents or secrets.

## 20. Compatibility with Domain Model v1

Repository code imports and stores A1b1 frozen objects without changing their
fields or single-object invariants. `dataclasses.replace` constructs a new
validated object for the explicitly authorized Task status, Run finalization,
consistency, and canonical changes. The old object is never mutated.

Protocol and test-double code runs on the current Python 3.9 runtime, uses no
new dependency, and contains no SQLAlchemy or FastAPI import.

## 21. Handoff to QM2-P0-002A2

`QM2-P0-002A2 — Ledger ORM Models and Database Migration` may map these
contracts to the selected async PostgreSQL boundary and create explicit,
versioned database structures. It must independently verify PostgreSQL schema,
constraints, transaction ownership, migration execution, rollback, and isolated
integration testing. The in-memory test double is reusable contract evidence,
not proof that A2 has been implemented.
