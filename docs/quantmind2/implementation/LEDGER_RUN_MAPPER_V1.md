# Ledger ImplementationRun Mapper v1

## 1. Scope

QM2-P0-002A2a2c2b implements only bidirectional conversion between
`ImplementationRun` and `ImplementationRunRecord`. It adds no Relationship,
detail, reference, annotation, identity, Repository, migration, database,
Manifest Indexer, API, or UI behavior.

## 2. Mapper Contract Version

The implementation uses `MAPPER_CONTRACT_VERSION = "1.0.0"` and the common
exact Enum and aware-UTC datetime conversion utilities established by the Task
Mapper increment.

## 3. Domain / Mapper / ORM Boundary

Domain construction remains semantic authority for commits, hashes, paths,
times, identifiers, workspace flags, states, consistency and canonical
combinations. ORM is persistence shape. Mapper copies and converts loaded
values only. Repository remains authority for replay, conflict, transitions,
expected versions and transactions.

## 4. Repository Identity Semantics

`repository_root` currently means logical repository identity despite its
historical name. Both Mapper directions copy this already-valid identity
unchanged. The Mapper never receives or interprets an execution path, reads a
Git remote, consults Project Context, or generates `quantmind-main`.

## 5. Domain-to-ORM Mapping

`implementation_run_to_record` accepts only a formal `ImplementationRun`,
maps every business field explicitly, converts five Enums to exact values,
normalizes present datetimes to UTC, and creates a fresh record with version 1.
It performs no lookup, transition, canonical decision, Session operation, Git
query, file access, or Manifest parsing.

## 6. ORM-to-Domain Mapping

`implementation_run_from_record` accepts only `ImplementationRunRecord`, reads
all fields from already-loaded instance state, validates ORM-only version, and
calls the official `ImplementationRun(...)` constructor. Missing/expired fields
fail with `MISSING_REQUIRED_VALUE` without descriptor refresh. Expected Domain
errors are wrapped safely; programming defects are not swallowed.

## 7. Enum Conversion

`ImplementationRunStatus`, `CompletionLevel`, `VerificationLevel`,
`ConsistencyStatus`, and `CanonicalStatus` use exact Enum value conversion.
Unknown, wrong-case, whitespace-padded, null, and non-string stored values fail
with `UNKNOWN_ENUM`; no repair or fallback occurs.

## 8. Commit and Hash Fields

`base_commit` is required. `result_commit` may be `None`. `manifest_hash`,
`report_hash`, `source_bundle_hash`, and `git_diff_hash` may be `None`.
Domain-to-record copies values exactly. Mapper does not trim, change case,
calculate hashes, inspect Git objects, verify ancestry, or compare content.
ORM-to-Domain delegates format and normalization rules to Domain construction.

## 9. Datetime Conversion

`started_at` is required and aware. `completed_at` is aware when present and
may be `None`. Both directions normalize present values to UTC and preserve
microseconds. Naive values fail; the Mapper never assumes local timezone.

## 10. Nullable Fields

`result_commit`, `completed_at`, and all four hashes preserve `None`. Empty
string is never converted to `None`; Domain construction rejects illegal empty
values and invalid state combinations.

## 11. Path Fields

`manifest_path` and `report_path` are copied unchanged. The Mapper does not
open them, check existence, resolve them, absolutize them, or parse content.
Domain validates their repository-relative structure.

## 12. Workspace Dirty Flags

Both workspace flags are copied exactly. ORM-to-Domain relies on the Domain
constructor to require real booleans. Mapper does not use dirty state to infer
canonical status or commit state.

## 13. Version Field Boundary

Version is ORM-only. New records always use 1; stored versions must be positive
non-bool integers and do not enter Domain. A version-9 record reconstructed and
converted to a new record becomes version 1. This Mapper creates new records or
rebuilds Domain objects; it is not an existing-row update path. Repository owns
expected version and version increments.

## 14. Canonical and Consistency Boundary

Mapper converts the two Enums exactly but never promotes, rejects, repairs, or
recomputes them. The Domain constructor enforces committed result, completion,
consistency, terminal time, dirty-state and canonical gates. Invalid records
fail atomically as safe `RecordToDomainError` values.

## 15. Field Mapping Table

| Domain field | ORM column | Conversion |
| --- | --- | --- |
| implementation_run_id | implementation_run_id | exact existing ID |
| task_id | task_id | exact existing ID |
| repository_root | repository_root | exact logical identity |
| branch | branch | exact text |
| base_commit | base_commit | exact full commit |
| result_commit | result_commit | exact full commit or None |
| task_status | task_status | Enum value |
| completion_level | completion_level | Enum value |
| verification_level | verification_level | Enum value |
| workspace_dirty_before | workspace_dirty_before | exact bool |
| workspace_dirty_after | workspace_dirty_after | exact bool |
| started_at | started_at | aware datetime to UTC |
| completed_at | completed_at | aware datetime to UTC or None |
| agent_type | agent_type | exact identifier |
| manifest_schema_version | manifest_schema_version | exact identifier |
| manifest_path | manifest_path | exact repository path |
| manifest_hash | manifest_hash | exact SHA-256 or None |
| report_path | report_path | exact repository path |
| report_hash | report_hash | exact SHA-256 or None |
| source_bundle_hash | source_bundle_hash | exact SHA-256 or None |
| git_diff_hash | git_diff_hash | exact SHA-256 or None |
| consistency_status | consistency_status | Enum value |
| canonical_status | canonical_status | Enum value |
| none | version | new 1 / stored positive check |

## 16. Round-trip Semantics

Domain round trips cover running, uncommitted, committed noncanonical,
canonical, partial committed, failed, blocked and cancelled states; null and
present hashes; non-UTC times; dirty flags; safe paths; and logical repository
identity. Record-value round trip preserves business fields, with UTC time
normalization and new-record version reset to 1 as the only intended changes.

## 17. Error Safety

Errors may disclose a validated non-secret Run ID, field, stable code and
underlying exception type. They never disclose arbitrary repository values,
full Record repr, Manifest/Report content, database URLs, source bundles, or
secret-like identities.

## 18. Purity and Side-effect Boundary

The Mapper may construct ORM instances, read loaded columns, invoke common
conversions, and call Domain construction. It has no Engine, Session,
Connection, SQL, filesystem, Git, network, environment, random ID, logging,
merge, refresh, commit, rollback, state transition, or canonical promotion.

## 19. Deferred Manifest Binding

No `run_from_manifest`, Manifest parser, vocabulary translation, execution
path binding, or repository identity resolver exists. A future Indexer must
obtain explicit trusted logical repository binding before constructing Domain.

## 20. Deferred Relationship Mapper

`RunRelationship` conversion, relationship ID handling, graph checks and edge
queries remain entirely deferred. `run.py` does not import its ORM record.

## 21. Deferred Repository and Migration

Replay, parent existence, conflict translation, state updates, optimistic
concurrency, transaction ownership, migration, schema/table creation and real
PostgreSQL validation are not implemented.

## 22. Handoff to QM2-P0-002A2a2c2c

The only next task is `QM2-P0-002A2a2c2c — RunRelationship Mapper`. It may
implement Relationship conversion only under its own bounded contract. This
task does not begin it.
