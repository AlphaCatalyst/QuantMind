# Implementation Ledger Core ORM Mapping v1

Status: implemented static mapping contract  
Task: `QM2-P0-002A2a1 — Core Implementation Ledger ORM Mapping`  
Base commit: `6a624a1dbaa8ba02073f3a5fc5b41805fc7481f0`

## 1. Scope

This contract maps only `ImplementationTask`, `ImplementationRun`, and
`RunRelationship` to SQLAlchemy tables. It proves their PostgreSQL persistence
shape through imported metadata and dialect-only DDL compilation. It performs
no database operation and creates no schema or table.

## 2. Persistence Mechanism Decision

The mapping uses SQLAlchemy 2.x on the API control-plane Base selected by the
A1a reality audit. Production requirements pin SQLAlchemy 2.0.25. Static tests
were executed with an already-installed SQLAlchemy 2.0.51 environment because
the checkout's system Python has no installed SQLAlchemy; no dependency was
installed or changed. A future production integration must reverify against
the pinned environment and PostgreSQL.

## 3. Domain vs ORM Boundary

`Domain Model != ORM Model`. A1b1 frozen domain objects remain the semantic
authority for complete state combinations, normalized paths, secret-like text
rejection, identifiers, and construction validity. ORM records define columns,
basic database checks, keys, indexes, and version storage only. They expose no
state transition, Git, filesystem, network, Repository, transaction, commit,
rollback, or promotion behavior.

## 4. Schema and Naming

All three tables explicitly target schema `quantmind2` and do not rely on
`search_path`:

- `quantmind2.implementation_tasks`
- `quantmind2.implementation_runs`
- `quantmind2.implementation_run_relationships`

All primary keys, foreign keys, unique constraints, checks, and indexes have
unique explicit names no longer than PostgreSQL's 63-character identifier
limit. Import registers the tables on
`backend.services.api.models.base.Base.metadata`; it has no database side
effect. No second Declarative Base or thin registration module is needed.

## 5. Enum Persistence Strategy

Enum columns use `VARCHAR(32)` plus named `CHECK` constraints, not PostgreSQL
native enums. `enum_check_sql()` derives each allowed value list directly from
the A1b1 domain Enum, and tests compare both the helper constants and table
checks with the domain declarations. This keeps enum evolution migration-
friendly while making drift visible.

## 6. `implementation_tasks`

| Column | Type | Nullable | Default | Meaning |
| --- | --- | --- | --- | --- |
| `task_id` | `VARCHAR(255)` | no | none | primary identity |
| `parent_task_id` | `VARCHAR(255)` | yes | none | optional self parent |
| `title` | `TEXT` | no | none | human title |
| `objective` | `TEXT` | no | none | bounded objective |
| `scope` | `JSONB` | no | none | JSON array |
| `explicit_non_goals` | `JSONB` | no | none | JSON array |
| `status` | `VARCHAR(32)` | no | none | domain Task status |
| `created_at` | `TIMESTAMPTZ` | no | none | aware creation time |
| `version` | `INTEGER` | no | server `1` | optimistic version token |

Checks require a supported status, different parent, positive version,
non-blank title/objective, and JSON arrays for scope/non-goals. No state
transition trigger exists.

## 7. `implementation_runs`

The table contains the 24 required fields. IDs, logical repository, branch,
agent type, and Manifest schema version use `VARCHAR(255)`; commits use
`CHAR(40)`; SHA-256 values use nullable `CHAR(64)`; Manifest/Report paths use
`TEXT`; workspace flags use non-null `BOOLEAN`; times use `TIMESTAMPTZ`; state
fields use checked `VARCHAR(32)`; version is a positive integer with server
default 1.

Simple checks repeat domain rules for enum membership, commit/hash hexadecimal
format, completion-time ordering, running/terminal time presence, committed and
uncommitted result-commit presence, completed/partial completion level, the
canonical gate, and failure-state noncanonical behavior. Canonical status is
never inferred or assigned automatically.

## 8. `implementation_run_relationships`

| Column | Type | Nullable | Meaning |
| --- | --- | --- | --- |
| `relationship_id` | `VARCHAR(255)` | no | primary identity |
| `source_run_id` | `VARCHAR(255)` | no | directed source Run |
| `target_run_id` | `VARCHAR(255)` | no | directed target Run |
| `relationship_type` | `VARCHAR(32)` | no | domain relationship kind |
| `reason` | `TEXT` | no | non-blank explanation |
| `created_at` | `TIMESTAMPTZ` | no | aware creation time |

The table rejects self-links and duplicate `(source, target, type)` tuples. It
does not attempt recursive DAG enforcement or exact-replay conflict handling.

## 9. Primary Keys

- `pk_qm2_tasks(task_id)`
- `pk_qm2_runs(implementation_run_id)`
- `pk_qm2_rels(relationship_id)`

String capacity is 255, matching rather than narrowing the domain identifier
maximum.

## 10. Foreign Keys

- `fk_qm2_tasks_parent`: Task parent to Task.
- `fk_qm2_runs_task`: Run to Task.
- `fk_qm2_rels_source_run`: relationship source to Run.
- `fk_qm2_rels_target_run`: relationship target to Run.

Every reference is schema-qualified and explicitly uses `ON DELETE RESTRICT`.

## 11. Unique Constraints

`uq_qm2_rels_source_target_type` protects the A1b2 relationship natural key.
The ORM alone does not implement exact replay or compare immutable content.

## 12. Check Constraints

Task checks cover enum values, self-parent, version, non-blank text, and JSONB
array shape. Run checks cover five enum columns, version, commit/hash syntax,
time/status presence, result-commit rules, completed/partial levels, canonical
eligibility, and terminal failure exclusion. Relationship checks cover
distinct Runs, type values, and non-blank reason. Complex path safety,
secret-like detection, state-transition authorization, graph cycles, and
cross-row reconciliation remain outside simple checks.

## 13. Indexes

Task indexes cover status, parent, and creation time. Run indexes cover Task,
Run status, canonical status, consistency status, start time, result commit,
and `(task_id, started_at)`. Relationship indexes cover source, target, type,
`(source, type)`, and `(target, type)`.

## 14. Version Columns

Task and Run each store a non-null positive `version` with server default 1.
This is storage support for A1b2 expected-version semantics, not a working
optimistic-lock algorithm. No mapper, Repository update statement, row lock,
or compare-and-swap behavior exists in this task.

## 15. Delete Semantics

Every foreign key is `ON DELETE RESTRICT`. The Ledger is immutable audit
history, has no physical-delete workflow, and must not lose child evidence by
cascade. No `CASCADE`, `SET NULL`, delete-orphan relationship, or soft-delete
column is defined.

## 16. Domain Fields Not Enforced by Database

The database does not validate repository-relative path traversal, logical
repository identifier characters, branch text semantics, reason secrets,
timezone normalization to UTC, Git object existence/ancestry, report/hash
agreement, artifact existence, or complete domain construction. These remain
domain, Repository, Indexer, or Git consistency responsibilities.

## 17. Domain-to-ORM Mapping Table

| Domain | ORM record/table | Mapping status | Future mapper responsibility |
| --- | --- | --- | --- |
| `ImplementationTask` | `ImplementationTaskRecord` | all fields plus persistence `version` | tuple/JSONB conversion and domain reconstruction |
| `ImplementationRun` | `ImplementationRunRecord` | all fields plus persistence `version` | Enum/string conversion and domain reconstruction |
| `RunRelationship` | `RunRelationshipRecord` | all fields | Enum/string conversion and immutable conflict translation |

The domain has no version field; version is Repository persistence metadata.
No formal mapper is implemented here.

## 18. Static DDL Verification

Tests compile each table with `CreateTable` and every index with `CreateIndex`
using `sqlalchemy.dialects.postgresql.dialect()`. This constructs SQL strings
only—no Engine, URL, Connection, Session, execute call, database credential, or
database process is involved. Compiled SQL confirms schema qualification,
JSONB, `TIMESTAMP WITH TIME ZONE`, named checks, and `ON DELETE RESTRICT`.

## 19. Deferred Detail Tables

ChangedFile, ChangedSymbol, TestExecution, ImplementationArtifact,
ComponentReference, ArchitectureDecisionReference, Limitation, and
RecommendedTask tables are not mapped. Metadata tests explicitly reject their
accidental introduction in this increment.

## 20. Deferred Domain Mappers

Domain-to-ORM and ORM-to-domain conversion, validation error translation,
version mapping, exact replay comparison, and persistence row conversion are
deferred to `QM2-P0-002A2a2`.

## 21. Deferred Migration

No migration file, `CREATE SCHEMA`, `CREATE TABLE` execution, migration order,
checksum, privilege, upgrade, or rollback mechanism is introduced. Metadata is
a mapping contract, not a deployment artifact.

## 22. Deferred PostgreSQL Integration

No PostgreSQL connection or credential was read. Schema existence,
permissions, actual DDL acceptance, JSONB behavior, FK enforcement,
transaction isolation, locks, concurrency races, and performance remain
unverified. PostgreSQL-specific types intentionally make this mapping
incompatible with SQLite as an integration substitute.

## 23. Handoff to QM2-P0-002A2a2

`QM2-P0-002A2a2 — Ledger Detail ORM Mapping and Domain Mappers` is the only
next task. It must independently map detail objects and define explicit domain
conversion without turning ORM records into the semantic authority. It must
not infer that migration, production Repository, Session/UoW, or PostgreSQL
deployment has been completed by this task.
