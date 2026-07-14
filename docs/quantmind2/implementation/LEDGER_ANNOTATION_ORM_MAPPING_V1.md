# Ledger Annotation ORM Mapping v1

## 1. Scope

QM2-P0-002A2a2b2 maps exactly `Limitation` and `RecommendedTask` to two
static SQLAlchemy tables. It adds no Domain Mapper, Repository, Session, Unit
of Work, transaction service, migration, schema creation, database access,
Manifest Parser/Indexer, Git consistency service, API, or UI.

## 2. Domain / Repository / ORM Boundary

A1b1 remains authority for identifier validation, enum values, secret-safe
text, and frozen construction. A1b2 remains authority for Run-scoped natural
identity, exact replay, immutable conflict, parent existence at operation
boundaries, append-only behavior, and atomic batches. ORM records define
PostgreSQL shape and minimum repeated constraints only.

## 3. Shared Schema and Base

Both records subclass `backend.services.api.models.base.Base`, register in the
same metadata as the existing nine Ledger mappings, and explicitly target
schema `quantmind2`. Import creates no second Base, Engine, Session, schema,
table, transaction, or runtime hook.

## 4. Annotation Append-only Semantics

A Limitation records what one Implementation Run observed; a RecommendedTask
records what that Run advised at that time. Later resolution, supersession,
task creation, completion, or cancellation must not rewrite historical
annotations. The ORM exposes no update/delete/status-change/merge method.
Static metadata cannot block privileged SQL UPDATE, so future Repository and
database-role governance must enforce append-only access.

## 5. Limitation Mapping

`quantmind2.implementation_limitations` contains non-null `limitation_id
VARCHAR(255)`, Run ID, severity, description, and status plus nullable
`component_id VARCHAR(255)`. Description is `TEXT`; enum columns are
`VARCHAR(32)`. Checks cover severity/status values, nonblank description, and
nonblank component ID when present. Secret scanning and full identifier rules
remain Domain responsibilities.

## 6. RecommendedTask Mapping

`quantmind2.implementation_recommended_tasks` contains non-null
`recommendation_id VARCHAR(255)`, Run ID, `next_task_id VARCHAR(255)`, priority
`VARCHAR(16)`, and reason `TEXT`. Checks require a nonblank next task ID,
domain priority value, and nonblank reason. A recommendation does not create,
execute, or mutate an ImplementationTask or Roadmap entry.

## 7. Primary Keys

`limitation_id` and `recommendation_id` are direct named primary keys, with no
default, sequence, UUID, or autoincrement. This follows the domain object
catalog and task contract and requires future Mapper/Indexer IDs to be globally
stable. This is stronger than A1b2's Run-scoped lookup identity and is recorded
explicitly rather than hidden.

## 8. Foreign Keys

Each table has exactly one schema-qualified foreign key from
`implementation_run_id` to
`quantmind2.implementation_runs.implementation_run_id`, explicitly named with
`ON DELETE RESTRICT`. Neither nullable component ID nor recommended next task
ID has an external foreign key.

## 9. Natural Identity

A1b2 keys Limitation by `(implementation_run_id, limitation_id)` and
RecommendedTask by `(implementation_run_id, recommendation_id)`. Named unique
constraints retain these exact tuples even though the single-column global
primary keys make them physically redundant. No uniqueness is imposed on
`(run, next_task_id)`, so separate recommendation IDs may express distinct
advice about the same future task.

## 10. Check Constraints

Database checks repeat Limitation severity/status values, nonblank description,
optional-but-nonblank component ID, nonblank next task ID, recommendation
priority, and nonblank reason. They intentionally omit secret scanning,
Component/Task existence, current resolution/completion state, recommendation
validity, replay equality, append authorization, and Project State derivation.

## 11. Indexes

Limitation indexes cover Run, severity, status, component, Run/status, and
component/status. Recommendation indexes cover Run, next task, priority,
Run/priority, and next-task/priority. All PK/FK/UQ/check/index names are
explicit, globally unique in shared metadata, kind-prefixed, and within
PostgreSQL's 63-character limit.

## 12. Enum Persistence

Enum columns use VARCHAR plus named CHECK, not PostgreSQL native Enum.
`enum_check_sql` reads A1b1 `LimitationSeverity`, `LimitationStatus`, and
`RecommendationPriority` directly. Tests compare exported value tuples and
actual CHECK SQL with each Domain Enum; no handwritten duplicate values exist.

## 13. Why No Component Foreign Key

Component Catalog remains a Git/Project Memory-derived index without a stable
authoritative database entity table. A Limitation must remain representable
even if the derived Catalog is stale or missing. Component existence and
consistency belong to a future Indexer/Application Service, not this table.

## 14. Why No Task Foreign Key

`next_task_id` may describe a future task that has not been created. A
Recommendation is advisory evidence, not an ImplementationTask definition or
lifecycle transition. A Task FK would incorrectly require recommendation
consumers to create the future Task first and would collapse advice into state.

## 15. Why No ORM Relationships

A1b2 already defines Run-scoped listing. ORM relationships would introduce
loading, cascade, and aggregate-ownership semantics outside this task. Run
records therefore receive no `limitations` or `recommended_tasks` collection.

## 16. Status and Historical Truth

Limitation `status` is content captured for one immutable observation; no ORM
method changes it in place. A future resolution should be represented through
new Run evidence and derived current-state views. RecommendedTask remains the
historic advice even after the proposed task is created, completed, cancelled,
or no longer recommended.

## 17. Exact Replay and Immutable Conflict

A1b2 defines equal Run-scoped identity plus equal frozen object as exact replay
returning existing content. Different status, description, component,
severity, next task, priority, or reason at the same identity is immutable
conflict. ORM provides no upsert, merge, `ON CONFLICT DO UPDATE`, overwrite,
status update, or database error translation.

## 18. Static DDL Verification

Tests compile both tables and every index with `postgresql.dialect()` without
Engine or Session. They verify table/schema, columns, PKs, Run-scoped UQs,
only-Run FKs, RESTRICT, enum/text checks, indexes, explicit globally unique
bounded names, and absence of cascade, trigger, external Component/Task FK,
secret, Mapper, update, upsert, and runtime DDL behavior. The existing test
environment has SQLAlchemy 2.0.51; production requirements pin 2.0.25. String
compilation cannot prove schema privileges, migration order, server execution,
transactions, concurrency, or performance.

## 19. Deferred Domain Mappers

There is no `to_domain`, `from_domain`, mapper, serializer, deserializer,
Enum conversion, Manifest vocabulary conversion, replay comparison, or error
translation. A2a2c must handle all eleven object families consistently.

## 20. Deferred Migration

No migration, bootstrap SQL edit, migration version, `CREATE SCHEMA`, `CREATE
TABLE`, deployment invocation, checksum, privilege, or rollback mechanism is
introduced. All eleven mappings remain unapplied metadata targets.

## 21. Deferred PostgreSQL Repository

No database URL, credential, Engine, Connection, Session, Unit of Work,
transaction, SQLAlchemy Repository, row lock, Indexer, or PostgreSQL fixture is
used. SQLite is not accepted as evidence for schema or concurrency semantics.

## 22. Handoff to QM2-P0-002A2a2c

The only recommended next task is `QM2-P0-002A2a2c — Ledger Domain-to-ORM
Mappers`. It must independently define bidirectional conversions for all
eleven domain/ORM families, preserve these identity decisions, and must not
silently introduce migration, production Repository, or database deployment.
