# Database Schema Index

Status: partial static mapping; no deployed schema or migration

QM2-P0-001 introduces no database migration or table. Future schema versions
will be indexed here with migration IDs, owning component, rollback status, and
the Implementation Run that introduced them. Planned tables are not existing
database objects.

QM2-P0-002A1a confirmed that the repository currently combines:

- `data/quantmind_init.sql`, invoked for fresh installation by
  `deploy/deploy.sh`;
- transaction-wrapped, manually documented SQL upgrades under `data/` and
  `data/migrations/`, with operational deployment use not confirmed;
- runtime raw DDL and SQLAlchemy metadata `create_all` in formal service
  startup paths;
- no code-confirmed Alembic environment or ordered applied-version runner.

The audit recommends a future versioned PostgreSQL migration in an explicit
`quantmind2` schema, reconciled with fresh-install bootstrap, and prohibits
runtime DDL as the new Ledger migration authority. This is a selection only:
no `quantmind2` schema, deployed Ledger table, migration file, or API exists.

Authority: Git Implementation Runs remain immutable facts; future PostgreSQL
objects will be derived/query indexes, not replacements for Git history.

Evidence:
`docs/quantmind2/implementation/LEDGER_PERSISTENCE_REALITY_AUDIT_V1.md`.

QM2-P0-002A1b1 adds only persistence-agnostic frozen dataclasses, enums,
errors, and validators. It creates no ORM metadata, SQL, table, schema,
migration, index, Session, transaction, or database constraint. The schema
index therefore remains `planned`.

QM2-P0-002A1b2 adds Repository behavior contracts and a process-local in-memory
test double only. It creates no SQLAlchemy metadata, PostgreSQL object,
`quantmind2` schema, migration, Session, Unit of Work, database transaction, or
runtime DDL.

QM2-P0-002A2a1 registers three static mappings on the selected API Base:

- `quantmind2.implementation_tasks`;
- `quantmind2.implementation_runs`;
- `quantmind2.implementation_run_relationships`.

These are metadata targets only. Dialect-only compilation verifies the intended
PostgreSQL DDL shape, but no Engine, Connection, Session, credentials,
`CREATE SCHEMA`, `CREATE TABLE`, migration, or PostgreSQL server was used.
Core detail tables and domain mappers were deferred at A2a1; deployment remains
deferred to a separate migration task. Git Implementation Runs remain the
authority.

QM2-P0-002A2a2a additionally registers four static metadata targets:

- `quantmind2.implementation_changed_files`;
- `quantmind2.implementation_changed_symbols`;
- `quantmind2.implementation_test_executions`;
- `quantmind2.implementation_artifacts`.

The same undeployed boundary applies. No schema/table was created, no migration
was added, and no database was connected. Component/ADR references and all
Domain/ORM mappers remained deferred at that increment.

QM2-P0-002A2a2b1 adds two more static metadata targets:

- `quantmind2.implementation_component_references`;
- `quantmind2.implementation_adr_references`.

Each uses its Run/object natural identity as a composite primary key and only a
restrictive Run FK. No Component Catalog or ADR entity FK exists because Git
remains authoritative. The schema and tables were not created; Limitation,
RecommendedTask, mappers, migration, and database integration remained deferred
at that increment.

QM2-P0-002A2a2b2 completes the current static metadata target set with:

- `quantmind2.implementation_limitations`;
- `quantmind2.implementation_recommended_tasks`.

Both bind restrictively to Run. Limitation does not foreign-key Component
Catalog, and RecommendedTask does not foreign-key or create a future Task.
Their primary IDs are globally unique, while named Run/ID unique constraints
record the A1b2 repository identity. All eleven current Ledger target mappings
now exist in metadata. The `quantmind2` schema and tables were not created, no
database was connected, and mapper, migration, Repository, Session/UoW, API,
and UI remain deferred.

QM2-P0-002A2a2c1 changes no ORM metadata or database target. It defines the
future Mapper contract and technical-ID algorithms only. The current schema
still has no Mapper/identity-version columns, no deployed `quantmind2` schema,
no migration, and no database connection. Identity algorithm versions must be
recorded by a future Indexer/migration contract before durable indexing.

QM2-P0-002A2a2c2a adds no metadata or schema change. Task Domain-to-record
conversion initializes the already-defined ORM `version` column to 1;
record-to-Domain validates a positive version and excludes it from Domain.
Updates and expected-version behavior remain future Repository work. No schema,
table, migration, Session, database connection, or DDL execution was added.

QM2-P0-002A2a2c2b likewise changes no metadata or database target. Run
Domain-to-record conversion creates a new version-1 ORM instance, while
record-to-Domain conversion reads only loaded state and invokes the frozen
Domain constructor. No Manifest was parsed, no repository identity was
resolved, no schema/table was created, and no database was connected.

QM2-P0-002A2a2c2c completes the pure Mapper layer without changing ORM
metadata, database targets, or DDL. ChangedFile and ChangedSymbol technical IDs
are computed in memory from the frozen v1 payloads and validated during reverse
mapping; no identity-version column was added. No migration ran, no schema or
table was created, and no database was connected. Migration and isolated
PostgreSQL verification remain the QM2-P0-002A2b boundary.

QM2-P0-002A2b establishes the sole Ledger deployment DDL authority under
`data/migrations/quantmind2/`. Migration `0001` creates the explicit
`quantmind2` schema, eleven ORM-aligned business tables, and infrastructure-only
`_schema_migrations`. The runner provides exact-byte SHA-256, ordered
plan/status/validate/up/down, advisory transaction locking, atomic history,
idempotent up, and guarded latest-only down. Disposable PostgreSQL 15 found no
drift across 11 tables, 87 columns, 97 named constraints, and 49 explicit
indexes. QM2-P0-002A3 now supplies the asynchronous PostgreSQL Repository and
explicit business Unit of Work over that schema, verified only in disposable
PostgreSQL 15. No production database has been migrated and no Manifest/Git
indexer exists.
