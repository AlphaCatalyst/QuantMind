# Ledger Reference ORM Mapping v1

## 1. Scope

QM2-P0-002A2a2b1 maps exactly `ComponentReference` and
`ArchitectureDecisionReference` to two static SQLAlchemy tables. It does not
map Limitation or RecommendedTask and adds no Mapper, Repository, Session,
Unit of Work, migration, schema creation, database access, Indexer, API, or UI.

## 2. Domain / Repository / ORM Boundary

A1b1 remains authority for valid identifiers, ADR format, enum values, frozen
construction, and secret-safe values. A1b2 remains authority for natural
identity, parent existence at operation boundaries, exact replay, immutable
conflict, append-only behavior, query semantics, and atomic batches. ORM
records provide PostgreSQL shape and minimum repeated constraints only.

## 3. Shared Schema and Base

Both records subclass `backend.services.api.models.base.Base`, register in the
same metadata as the existing seven Ledger records, and explicitly target
schema `quantmind2`. Import creates no second Base, Engine, Session, schema,
table, or transaction.

## 4. Why Composite Primary Keys

The domain has no separate reference IDs. `(implementation_run_id,
component_id)` and `(implementation_run_id, adr_id)` are both the A1b2 natural
identities and the database primary keys. This lets a Repository locate an
exact replay without an invented technical ID. `impact_type` and `relation`
are immutable content: changing either at the same identity is a conflict, not
a new record, so neither belongs in its primary key. There is no duplicate
natural unique constraint, sequence, UUID, or autoincrement value.

## 5. ComponentReference Mapping

`quantmind2.implementation_component_references` has three non-null columns:
`implementation_run_id VARCHAR(255)`, `component_id VARCHAR(255)`, and
`impact_type VARCHAR(32)`. The Run/component pair is the named primary key.
The database rejects blank component IDs and impact values outside A1b1
`ImpactType`; complete identifier validation remains a domain rule.

## 6. ArchitectureDecisionReference Mapping

`quantmind2.implementation_adr_references` has three non-null columns:
`implementation_run_id VARCHAR(255)`, `adr_id VARCHAR(32)`, and `relation
VARCHAR(32)`. The Run/ADR pair is the named primary key. A PostgreSQL regex
check requires exactly `ADR-` plus four digits, matching current domain v1,
and relation values come from A1b1 `ADRReferenceRelation`.

## 7. Primary Keys

- `pk_qm2_component_refs(implementation_run_id, component_id)`;
- `pk_qm2_adr_refs(implementation_run_id, adr_id)`.

The composite order supports Run-scoped listings. No technical ID column and
no separate unique constraint repeats either key.

## 8. Foreign Keys

Each table has one schema-qualified FK from `implementation_run_id` to
`quantmind2.implementation_runs.implementation_run_id`, explicitly named and
using `ON DELETE RESTRICT`. No FK points from component or ADR IDs to another
table.

## 9. Check Constraints

Component checks cover nonblank `component_id` and the domain-derived impact
value set. ADR checks cover the `^ADR-[0-9]{4}$` format and the domain-derived
relation value set. The database does not validate the full component
identifier grammar, file existence, Catalog membership, ADR status, or
business approval meaning.

## 10. Indexes

Component indexes cover `component_id`, `impact_type`, and `(component_id,
impact_type)`. ADR indexes cover `adr_id`, `relation`, and `(adr_id, relation)`.
The composite primary keys already index Run-first access, so no redundant Run
index or full-primary-key duplicate index is added. All names are explicit,
globally unique in the shared metadata, and within PostgreSQL's 63-character
limit.

## 11. Enum Persistence

Enum columns use `VARCHAR(32)` plus named CHECK, not PostgreSQL native Enum.
`enum_check_sql` reads A1b1 `ImpactType` and `ADRReferenceRelation` directly;
tests compare exported value tuples and actual CHECK SQL with those Enums. No
second handwritten value list exists.

## 12. Delete Semantics

Run deletion is RESTRICTed. There is no CASCADE, SET NULL, delete-orphan,
trigger, soft-delete flag, update/delete/change/merge method, or automatic
timestamp mutation. Static metadata cannot stop privileged direct SQL UPDATE;
future Repository permissions must enforce audit immutability.

## 13. Exact Replay and Immutable Conflict

A1b2 defines identical primary identity plus equal frozen content as exact
replay returning the existing object. The same identity with a different
impact or relation is `ImmutableEntityConflictError`. ORM metadata provides
identity constraints only; it performs no upsert, merge, `ON CONFLICT DO
UPDATE`, overwrite, or conflict translation.

## 14. Why No Component or ADR Foreign Key

Component Catalog and ADR Index are Git/Project Memory-derived facts, not
stable authoritative database entity tables. Adding external FKs now would
incorrectly make a future PostgreSQL projection an upstream authority. Git
documents and immutable Implementation Runs remain authoritative; PostgreSQL
is a rebuildable query index.

## 15. Why No ORM Relationships

Foreign-key columns are sufficient for static shape. A1b2 already defines
queries, and ORM collections would introduce loading/cascade/aggregate
semantics that this task does not own. Run records therefore receive no
`component_references` or `adr_references` relationship collections.

## 16. Static DDL Verification

Tests compile both tables and all indexes through
`postgresql.dialect()`, without Engine or Session. They verify schema, columns,
composite primary keys, the only Run FK, RESTRICT, checks, indexes, explicit
globally unique bounded names, and absence of cascade, trigger, external FK,
secret, upsert, Mapper, and runtime DDL behavior. The existing environment uses
SQLAlchemy 2.0.51 while production requirements pin 2.0.25. String compilation
does not prove schema privileges, migration ordering, server execution,
transactions, concurrency, or query performance.

## 17. Deferred Annotation Tables

`Limitation` and `RecommendedTask` mappings are explicitly absent. No table,
column, enum mapping, or test in this task begins their implementation.

## 18. Deferred Domain Mappers

There is no `to_domain`, `from_domain`, mapper, serializer, deserializer,
manifest vocabulary conversion, database-error translation, or replay
comparison. These concerns remain deferred until the ORM surface is complete.

## 19. Deferred Migration

No migration, migration version, bootstrap SQL edit, `CREATE SCHEMA`, `CREATE
TABLE`, deployment invocation, checksum, privilege, or rollback mechanism is
introduced. These table definitions remain unapplied metadata targets.

## 20. Deferred PostgreSQL Repository

No database URL, credentials, Engine, Connection, Session, Unit of Work,
transaction, SQLAlchemy Repository, row lock, Indexer, or PostgreSQL fixture is
used. SQLite is not accepted as evidence for schema, regex, or concurrency.

## 21. Handoff to QM2-P0-002A2a2b2

The only recommended next task is `QM2-P0-002A2a2b2 — Ledger Limitation and
Recommended Task ORM Mapping`. It must independently map the two remaining
annotation objects without adding mappers, migration, production persistence,
or claims that any Ledger table has been deployed.
