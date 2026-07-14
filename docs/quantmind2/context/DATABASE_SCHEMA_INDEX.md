# Database Schema Index

Status: planned; persistence mechanism audited

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
no `quantmind2` schema, Ledger table, migration file, model, or API exists.

Authority: Git Implementation Runs remain immutable facts; future PostgreSQL
objects will be derived/query indexes, not replacements for Git history.

Evidence:
`docs/quantmind2/implementation/LEDGER_PERSISTENCE_REALITY_AUDIT_V1.md`.

QM2-P0-002A1b1 adds only persistence-agnostic frozen dataclasses, enums,
errors, and validators. It creates no ORM metadata, SQL, table, schema,
migration, index, Session, transaction, or database constraint. The schema
index therefore remains `planned`.
