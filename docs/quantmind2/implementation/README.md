# QuantMind 2.0 Implementation Runs

Each development task creates a unique directory containing `report.md` and
`manifest.json`. Completed runs are immutable. A correction creates a new run
and sets `corrects_run_id`; it never overwrites the original.

## Git and state rules

- Git stores code plus portable report/manifest evidence.
- The future Implementation Ledger database indexes Git artifacts; it does not
replace them.
- New Implementation Runs default to Manifest v2. Use
  `tools/quantmind2/create_implementation_manifest.py`; do not copy a v1 Run.
- Manifest v1 is immutable compatibility evidence only. Its producer and hash
  semantics remain supported for historical Runs.
- An uncommitted run uses `result_commit: null` and status
  `completed_uncommitted` or `partial_uncommitted`; it is not canonical.
- Secrets must not be placed in reports or manifests.

## Manifest hash rules

`manifest_payload_hash` is SHA-256 over UTF-8 canonical JSON after removing the
`manifest_payload_hash` property. Canonical JSON uses sorted keys, no
insignificant whitespace, `ensure_ascii=false`, and rejects NaN/Infinity.

Manifest v2 uses nested `integrity.manifest_payload_sha256` and the separate
canonicalization contract documented in `IMPLEMENTATION_MANIFEST_V2.md`. New
Runs use the v2 Schema/example and the `new`, `finalize-payload`, and `validate`
producer commands. The producer never creates `result_commit`.

## Validation level

`tools/quantmind2/validate_context_bootstrap.py` implements a bounded,
zero-dependency subset of JSON Schema Draft 2020-12 covering only keywords used
by the repository v1/v2 schemas. It also checks repository paths, ADR references,
status consistency, official Factor Lab source boundaries, run pairs, report
hashes, and manifest payload hashes. It is not a general JSON Schema engine.

## Ledger database migration

The explicit versioned Ledger migration contract is
`LEDGER_MIGRATION_AND_POSTGRESQL_V1.md`. Its SQL authority lives under
`data/migrations/quantmind2/` and is coordinated by
`tools/quantmind2/ledger_migrations.py`. ORM metadata remains the current shape
contract; the migration is the only Ledger deployment DDL source.

## Ledger PostgreSQL Repository

`LEDGER_POSTGRES_REPOSITORY_V1.md` records the asynchronous Repository and Unit
of Work boundary implemented by QM2-P0-002A3. Repositories use one injected
shared-manager Session and never finish transactions; the UoW owns explicit
commit/rollback. Disposable PostgreSQL tests cover contract parity, savepoints,
optimistic concurrency, DAG admission, and atomic batches. QM2-P0-002B adds
Manifest/Git parsing and indexing under `LEDGER_MANIFEST_INDEXER_V1.md`.
Current Manifest v1 history remains non-indexable where formal Domain evidence
is absent; no values are invented. Manifest v2 is the default forward protocol
and can express every current Ledger Domain family without report prose.

## Factor Validation

`FACTOR_LABEL_CONTRACT_V1.md`, `FACTOR_VALIDATION_V1.md`, and
`FROZEN_TEST_PROTOCOL_V1.md` define the production-parity label, immutable
temporal validation artifacts, Validation-only selection, and isolated one-time
Frozen boundary implemented by QM2-P0-006. These artifacts are predictive
statistics only; they are not Registry promotion or backtest evidence.

The immutable QM2-P0-006 Run retains one incorrect manually recorded
`before_hash` and therefore remains Git-inconsistent. QM2-P0-006F adds a
strict, separately hashed evidence-correction Artifact and a `corrects`
relationship. It neither edits the original Run nor changes Factor Validation,
Selection, Frozen Test, promotion, database schema, or production behavior.
