# Ledger Migration and PostgreSQL Contract v1

## 1. Scope

This contract realizes the frozen eleven-table Implementation Ledger ORM shape
as explicit PostgreSQL SQL. It covers migration ordering, integrity, rollback,
fresh-install invocation, and isolated PostgreSQL verification. It does not
implement a Repository, business Session/UoW, Manifest Indexer, API, or UI.

## 2. Existing Persistence Reality

Before this task, fresh install piped `data/quantmind_init.sql` into the
`quantmind-db` container. Incremental SQL lived in `data/upgrade_v1.1.0.sql`
and `data/migrations/upgrade_v1.4.0_stock_tag.sql` and was manually invoked.
There was no active Alembic configuration, ordered runner, applied-version
table, checksum, down migration, advisory lock, or shared PostgreSQL fixture.
Runtime DDL and `metadata.create_all()` exist elsewhere but are not acceptable
Ledger deployment authorities.

## 3. Migration Mechanism

`tools/quantmind2/ledger_migrations.py` is a zero-third-party-dependency
coordinator around `psql`. SQL files are the deployment authority; ORM metadata
is the current shape contract and is used only as test expectations. The runner
supports `plan`, `validate`, `status`, `up`, and `down`.

## 4. File Layout

```text
data/migrations/quantmind2/
  README.md
  manifest.json
  0001_implementation_ledger.up.sql
  0001_implementation_ledger.down.sql
```

The manifest is authoritative for order. Filesystem traversal order is ignored.

## 5. Version and Naming

Version `0001`, name `implementation_ledger`, runner version `1.0.0`, and
manifest schema version `1.0.0` are stable identities. Versions are four
decimal digits, unique, and ascending.

## 6. Checksum Contract

Both SQL files are hashed as exact bytes with SHA-256. No trimming, newline
conversion, decoding/re-encoding, or whitespace normalization occurs.
Manifest/file drift fails before connection. Applied history drift fails
`status`, `up`, and `down`.

## 7. Migration History Table

`quantmind2._schema_migrations` records version, name, both checksums,
`applied_at` (`timestamptz`), and runner version. It is infrastructure, not one
of the eleven domain tables and not a substitute for Git Implementation Runs.
No connection coordinates or credentials are stored.

## 8. Up Transaction

Each migration is one `psql` transaction with `ON_ERROR_STOP=1`. The runner
acquires its lock, bootstraps the schema/history table, verifies any existing
row, conditionally executes exact up SQL, and inserts history before commit.
An identical applied migration is skipped. Any failure rolls back DDL and
history together.

## 9. Down Transaction

Down requires `--allow-destructive`, a known latest version, and matching
checksums. These facts are checked again after the transaction lock. The SQL
drops the eleven tables in reverse dependency order, deletes history, verifies
that no later history remains, drops the infrastructure table, and uses plain
`DROP SCHEMA quantmind2` without `CASCADE`. Unexpected objects therefore fail
the transaction and preserve the prior schema.

## 10. Advisory Lock

Every up/down transaction uses `pg_advisory_xact_lock(4379672674272511630)`.
The stable key is derived from `quantmind2-ledger-migrations-v1`. It is scoped
to the transaction, uses no business table lock, and is released automatically.
The migration runner, not an application Repository, owns this transaction.

## 11. Fresh-install Integration

`deploy/deploy.sh` step 10 calls the runner after the legacy base bootstrap,
using the existing `quantmind-db` container. Ledger DDL is not copied into
`quantmind_init.sql`. History and checksums make repeated deployment safe. A
Ledger migration failure is fatal and stops deployment rather than continuing
with a partial Project Knowledge database.

## 12. Schema and Table Inventory

Schema `quantmind2` contains eleven business tables:

1. `implementation_tasks`
2. `implementation_runs`
3. `implementation_run_relationships`
4. `implementation_changed_files`
5. `implementation_changed_symbols`
6. `implementation_test_executions`
7. `implementation_artifacts`
8. `implementation_component_references`
9. `implementation_adr_references`
10. `implementation_limitations`
11. `implementation_recommended_tasks`

The ORM contract totals 87 columns, 97 named constraints (11 PK, 12 FK, 7 UQ,
67 CHECK), and 49 explicit non-constraint indexes. The infrastructure table is
additional and deliberately absent from ORM Domain metadata.

## 13. ORM/Migration Parity

The PostgreSQL integration test creates tables only through the migration. It
then compares API `Base.metadata` with `information_schema` and `pg_catalog`
for table/column inventory, normalized type category, length, nullability,
server default, named PK/FK/UQ/CHECK, FK target and `RESTRICT`, and explicit
index names/column order. The only accepted type equivalences are explicit:
`String/VARCHAR -> varchar`, `CHAR -> bpchar`, `Text -> text`, `JSONB -> jsonb`,
`Boolean -> bool`, `Integer -> int4`, `BigInteger -> int8`, and aware
`DateTime -> timestamptz`. Arbitrary drift is not ignored.

## 14. Constraint Verification

Every schema object is qualified. Foreign keys use `ON DELETE RESTRICT`.
Production SQL contains no `CASCADE`, trigger, automatic state transition,
cycle rule, canonical promotion, upsert policy, grant, role change, or global
`search_path` change. Domain and future Repository layers remain authorities
for graph cycles, replay/conflict, state transitions, and optimistic updates.

## 15. Isolated PostgreSQL Environment

The opt-in integration test starts a random-named `postgres:15-alpine`
container, publishes PostgreSQL to a random loopback port, creates a task-only
database, mounts no volume, passes a random password only through process
environment, and removes the container in `finally`. It never discovers or
uses application/production database configuration.

## 16. Valid Data Verification

A minimum graph containing two Tasks, two Runs, one Relationship, four Detail
families, two Reference families, Limitation, and RecommendedTask is inserted
with direct SQL. It verifies JSONB arrays, UTC `timestamptz`, Unicode text and
paths, valid enum values, checks, hashes, unique identities, and FKs.

## 17. Invalid Data Verification

Eighteen independent failing transactions verify invalid Task status, version
zero, missing Task FK, committed Run without result commit, invalid canonical
gate, reversed timestamps, relationship self-loop and duplicate natural key,
invalid ChangedFile shape, invalid ChangedSymbol enum, negative test count,
failed-test shape, negative artifact size, invalid ADR ID, blank Limitation,
blank recommendation, and restrictive Task and Run deletion. Each assertion
uses a named constraint rather than localized prose.

## 18. Idempotency

Running `up` again against a matching applied row does not execute DDL or add a
history row. It reports the migration as current.

## 19. Checksum Drift

Database-free validation rejects a changed SQL file. Integration verification
also creates a temporary internally consistent manifest/file copy whose new
checksum disagrees with applied history; the database operation hard-fails.
Official migration files are never modified by the test.

## 20. Rollback

An injected unexpected table proves rollback atomicity: plain schema removal
fails and PostgreSQL restores all dropped tables and history. After removing
the guard, explicit down removes only `quantmind2`; a `public` sentinel remains.

## 21. Reapply

After successful down, a second up recreates the schema. The full catalog/ORM
comparison produces the same counts and no drift.

## 22. Cleanup

The test performs a final down and removes the disposable container even when
an assertion fails. It asserts that no matching container remains.

## 23. Security and Secret Handling

Subprocess calls use argv lists and SQL stdin, never shell command strings.
Passwords are accepted through `PGPASSWORD`, absent from argv/status/plan, and
redacted if a subprocess error happens to repeat a known secret. The migration
does not grant public privileges, change roles/passwords, or log database URLs.

## 24. Limitations

- No production database has been migrated.
- Deployment-role/schema privilege policy is not yet frozen.
- CI execution of the opt-in Docker integration test is not configured.
- The existing shared database manager's URL logging risk is outside scope.
- Mapper/technical identity algorithm versions are not columns in these tables.
- PostgreSQL Repository concurrency and business transaction behavior remain
  unimplemented and unverified.

## 25. Handoff to PostgreSQL Repository

The next task may treat migration `0001` and the verified ORM metadata as the
database shape boundary. It must implement `QM2-P0-002A3 — PostgreSQL Ledger
Repository and Unit of Work` without committing inside Repositories and without
moving Domain replay/conflict/cycle/state behavior into migrations.
