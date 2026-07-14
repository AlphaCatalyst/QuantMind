# Implementation Report: QM2-P0-002A1b2

## 1. Task Summary

`QM2-P0-002A1b2 — Ledger Repository Contract and In-memory Test Double`
implements persistence-independent Repository Protocols, Repository errors,
immutable query/page objects, and a pure in-memory test double. It verifies
identity, exact replay, immutable conflict, state/version behavior, append-only
details, complete relationship-cycle checks, stable queries, and atomic batches.

## 2. Goal

Define and test Ledger Repository behavior before choosing physical ORM rows,
tables, migration mechanics, or database transaction implementation.

## 3. Scope

- Synchronous `typing.Protocol` contracts for Task, Run, Relationship, Detail,
  and aggregate Ledger repositories.
- Stable Repository-layer errors and frozen typed query/page values.
- Instance-local standard-library `InMemoryLedgerRepository` test double.
- Repository contract document, 60 focused tests, Context regressions, Project
  Memory updates, one immutable Implementation Run, and one local commit.

## 4. Explicit Non-goals

No SQLAlchemy ORM, PostgreSQL Repository/table, `quantmind2` schema, migration,
Session, production Unit of Work, Manifest Parser/Indexer, Git consistency
service, API, UI, TDX, Dataset Snapshot, Factor DSL, Optimization, Validation
runtime, Registry, LightGBM, Qlib, or Factor Lab change.

## 5. Preflight State

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`
- Base: `200665bd9eb5d9393011f8c3d9a3c31001b8cf15`
- Dirty before: no
- Unrelated dirty files: none
- Factor Lab: clean at `c83192c2278767e03f008bc39197b1ba33bfb6a9`; read-only.

The mandated context, audit, Domain Model v1, ADRs, implementation protocol,
and complete A1b1 report/manifest were read in order. Git Reports/Manifests
remain authoritative; the future database remains a derived query index.

## 6. Existing Repository Convention Review

Repository searches found no shared Repository abstraction, Protocol pattern,
in-memory Repository, pagination value object, or Unit of Work convention.
Existing persistence is predominantly direct Session/service code; unrelated
abstractions often use ABC. This task uses synchronous `typing.Protocol`
because structural contracts avoid inheritance and framework coupling and can
be verified under Python 3.9 without an event loop or dependency. A future
async SQLAlchemy adapter may preserve the same behavioral semantics at its
application boundary.

The in-memory implementation is explicitly named and documented as a test
double. It does not establish production storage, durability, or transaction
facts.

## 7. Repository Architecture

```text
Validated A1b1 frozen domain objects
→ synchronous Repository Protocol behavior
→ instance-local in-memory contract verification
→ future async SQLAlchemy/PostgreSQL adapter (not implemented)
```

There is no generic `save`, full-object update, delete, replace-all, Session,
commit, rollback, or Unit of Work. Children are append-only. Run updates are
limited to finalization, consistency, and canonical status; Task updates are
limited to status.

## 8. Interfaces and Query Objects

| Contract | Responsibility |
| --- | --- |
| `ImplementationTaskRepository` | create/get/require/version/list/status transition |
| `ImplementationRunRepository` | create/get/require/version/list/finalize/consistency/canonical |
| `RunRelationshipRepository` | immutable edges, direction lists, existence, cycle preview |
| `RunDetailRepository` | append/list details, history, atomic Run-detail batch |
| `LedgerRepository` | aggregate access to the four contracts |

`TaskQuery`, `RunQuery`, and `HistoryQuery` are frozen. `Page.items` is a tuple.
Limit is `1..200`; offset is non-negative. Run sort is a fixed `asc/desc` enum,
not an arbitrary SQL field. Times must be timezone-aware. File paths reuse A1b1
validation.

## 9. Repository Error Model

`LedgerRepositoryError` provides a stable code plus safe entity type/ID.
Specific errors cover Task, Run, and Relationship existence; immutable
conflicts; optimistic concurrency; relationship cycles; state transitions;
duplicate children; and invalid queries. They do not inherit HTTP or database
exceptions and never include object content or rejected secret-like values.

## 10. In-memory Test Double

The test double uses insertion-ordered dictionaries for Tasks, Runs,
Relationships, each child collection, and integer Task/Run version maps. Every
instance owns independent state; no singleton or clear-all operation exists.

Objects are frozen, so returning the object reference is safe. Collection
queries create new tuples and never expose dictionaries or mutable lists.
Dictionary copies in the atomic path are shallow because all stored values are
immutable.

## 11. Identity, Uniqueness, and Idempotency

Task and Run use their IDs. Relationship uses its ID plus a natural
source/target/type key. Child natural keys are:

- ChangedFile: Run/path/change type;
- ChangedSymbol: Run/file/qualified name;
- TestExecution: Run/test ID;
- Artifact: Run/artifact ID;
- Component and ADR reference: Run/reference ID;
- Limitation and RecommendedTask: Run/object ID.

All create/add/append methods uniformly return the existing object for an exact
replay without incrementing version. The same identity with different content
raises `ImmutableEntityConflictError`; no merge or last-write-wins exists.
Repository never creates an implicit retry relationship.

## 12. State and Version Semantics

Task transitions are explicitly enumerated. Completed, partial, and cancelled
Tasks are terminal; blocked Tasks may return to ready/running or be cancelled.
Same-state replay is idempotent.

Run finalization requires a stored running Run and a terminal replacement that
preserves Run/Task/repository/branch/base/start/agent/schema/path identity. A
terminal Run cannot be finalized again. Finalization cannot set canonical
status. Uncommitted-to-committed and correction/finalization facts use a new Run
and explicit relationship rather than rewriting history.

Consistency and canonical status are separately controlled and still pass all
A1b1 constructor invariants. Mutating methods compare caller
`expected_version`; successful real changes increment it, exact no-op replays
do not. This validates the optimistic concurrency contract only.

## 13. Relationship Graph Algorithm

All six relationship kinds participate in one DAG. Before adding source →
target, iterative DFS starts at target and follows existing outgoing edges. If
source is reachable, the edge would close a cycle and is rejected. Exact replay
is resolved before DFS. Complexity is `O(V + E)` time and `O(V)` space per edge.
No large-graph optimization is claimed.

## 14. Queries and History

Runs filter in deterministic order by Task, Run status, canonical, consistency,
component, ADR, file path, and inclusive start-time interval. Results sort by
`(started_at, run_id)` ascending or descending, then paginate. `total` is the
pre-pagination count. Task sorting is `(created_at, task_id)`.

History accepts exactly one path, component, or ADR criterion. File history
includes the current and previous rename path. Queries are read-only and do not
create an implicit index.

## 15. Atomic Batch Semantics

`record_run_details_atomic` copies all internal dictionaries, performs Run
creation/replay and every child append against the isolated copy, then adopts
all copied dictionaries only after success. Any early or late validation,
parent, replay, or conflict error discards the copy, leaving original state
unchanged. Whole-batch exact replay is idempotent.

This proves only test-double all-or-nothing behavior. It does not prove
PostgreSQL isolation, durability, locking, crash recovery, or commit semantics.

## 16. Transaction Ownership

Repository methods never commit. A future Application Service / Unit of Work
must own one transaction for Run plus all child records. This task defines no
Unit of Work or Session and does not connect to a database.

## 17. A1b1 Boundary Comparison

- A1b1 still owns value normalization, frozen objects, single-object state
  combinations, paths/hashes/commits/times, and relationship self-loop checks.
- A1b2 owns cross-object existence, identity, replay, versions, legal updates,
  complete in-memory cycles, natural keys, queries, and batch semantics.
- ORM owns mapping, database constraints, serialization, row versions, and
  database error translation.
- Migration owns schema/table/index creation, order/checksums, permissions,
  deployment, and rollback.

A1b1 object definitions were not rewritten.

## 18. Tests and Verification

Final acceptance verification includes:

- Repository contract suite: 60 tests.
- A1b1 domain regression: 76 tests.
- Context regression: 18 tests.
- Context Bootstrap: 19 named checks.
- Python compilation, JSON parsing, actual Manifest hashes/schema, AST/import
  boundaries, path allowlist, diff checks, and Factor Lab read-only checks.

`ruff` was not installed and was not added; this is recorded as not-run rather
than described as passed.

## 19. Expected vs Actual

| Requirement | Expected | Actual | Evidence | Status |
| --- | --- | --- | --- | --- |
| Repository errors | stable, no DB/HTTP | full catalog | imports/tests | passed |
| Query values | immutable and bounded | frozen typed queries/Page | query tests | passed |
| Protocols | Task/Run/Relationship/Detail/aggregate | all defined | contract source | passed |
| Test double | standard library, isolated | per-instance dictionaries | scope tests | passed |
| Exact replay/conflict | uniform | shared immutable-store rule | replay tests | passed |
| Expected versions | stale rejection | Task/Run version maps | version tests | passed |
| Terminal Run immutability | no refinalization/rewrite | explicit finalization gate | Run tests | passed |
| Complete cycle detection | reject A→B→C→A | iterative DFS | graph tests | passed |
| Queries/history | stable filters/page/total | file/component/ADR | query tests | passed |
| Atomic batch | no partial write | isolated-copy adoption | batch tests | passed |
| No persistence/API | absent | static scope checks | regressions | passed |
| Independent commit | one local commit | performed after Run generation | Git | pending at generation |

## 20. Project Memory and Architecture Impact

Current State, Component Catalog, Known Issues, Roadmap, Handoff, Terminology,
and Database Schema Index now distinguish implemented Repository contracts and
test double from unimplemented production persistence. Context validation now
requires the contract/test-double files and continues rejecting ORM, migration,
and API expansion. No accepted ADR or frozen architecture changed.

## 21. Security and Data Lineage Impact

Repository errors expose validated IDs and stable messages, not stored object
contents. The test double performs no file, network, environment, Git, or
database access. No research data or model/backtest lineage changed. Git
Reports/Manifests remain authoritative; the test double is never authoritative.

## 22. Known Limitations and Unresolved Questions

- Process-local only; no multi-process or true concurrent behavior.
- Expected version is contract simulation, not a lock or database constraint.
- No database transaction, ORM, migration, Indexer, API, or durability.
- DFS is not optimized for a large relationship graph.
- Task/Run IDs are repository-global in v1; future repository scoping remains
  to be confirmed.
- Canonical demotion policy and same-node-pair cross-type relationship
  cardinality require future policy confirmation.
- PostgreSQL cycle enforcement strategy and race handling remain unresolved.

## 23. Compatibility and Rollback

The implementation is additive, Python 3.9 and standard-library compatible.
No dependency, lockfile, runtime configuration, historical Run, accepted ADR,
database, API, or Factor Lab changed. Rollback is the single containing commit;
no data or schema rollback is needed. The Run manifest keeps
`result_commit=null` because it cannot self-reference its containing commit.

## 24. Recommended Next Task

The only recommendation is
`QM2-P0-002A2 — Ledger ORM Models and Database Migration`. It must separately
prove ORM mapping, PostgreSQL constraints, explicit migration and rollback,
transaction ownership, and isolated integration behavior. None is implemented
or implied by this task.

## 25. Artifact Index

- Contract: `docs/quantmind2/implementation/LEDGER_REPOSITORY_CONTRACT_V1.md`
- Protocols: `backend/services/engine/project_knowledge/domain/repositories.py`
- Queries/errors: `backend/services/engine/project_knowledge/domain/`
- Test double: `backend/services/engine/project_knowledge/testing/in_memory_ledger_repository.py`
- Tests: `backend/services/tests/test_project_knowledge_ledger_repository_contract.py`
- Run manifest: sibling `manifest.json`
