# QuantMind 2.0 Implementation Runs

Each development task creates a unique directory containing `report.md` and
`manifest.json`. Completed runs are immutable. A correction creates a new run
and sets `corrects_run_id`; it never overwrites the original.

## Git and state rules

- Git stores code plus portable report/manifest evidence.
- The future Implementation Ledger database indexes Git artifacts; it does not
  replace them.
- An uncommitted run uses `result_commit: null` and status
  `completed_uncommitted` or `partial_uncommitted`; it is not canonical.
- Secrets must not be placed in reports or manifests.

## Manifest hash rule

`manifest_payload_hash` is SHA-256 over UTF-8 canonical JSON after removing the
`manifest_payload_hash` property. Canonical JSON uses sorted keys, no
insignificant whitespace, `ensure_ascii=false`, and rejects NaN/Infinity.

## Validation level

`tools/quantmind2/validate_context_bootstrap.py` implements a bounded,
zero-dependency subset of JSON Schema Draft 2020-12 covering only keywords used
by the v1 repository schemas. It also checks repository paths, ADR references,
status consistency, official Factor Lab source boundaries, run pairs, report
hashes, and manifest payload hashes. It is not a general JSON Schema engine.

## Ledger database migration

The explicit versioned Ledger migration contract is
`LEDGER_MIGRATION_AND_POSTGRESQL_V1.md`. Its SQL authority lives under
`data/migrations/quantmind2/` and is coordinated by
`tools/quantmind2/ledger_migrations.py`. ORM metadata remains the current shape
contract; the migration is the only Ledger deployment DDL source.
