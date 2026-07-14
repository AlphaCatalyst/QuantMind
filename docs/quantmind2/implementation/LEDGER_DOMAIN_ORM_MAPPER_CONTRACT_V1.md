# Ledger Domain / ORM Mapper Contract v1

Contract version: `1.0.0`
Status: accepted implementation contract for future mapper work

## 1. Scope

This contract defines deterministic conversion semantics for the eleven frozen
Ledger domain object families and their existing ORM records. It defines
identity, value conversion, error, version, and round-trip rules only. It does
not implement a mapper, Repository, Session, Unit of Work, migration, database
access, Parser/Indexer, API, or UI.

The eleven families are ImplementationTask, ImplementationRun,
RunRelationship, ChangedFile, ChangedSymbol, TestExecution,
ImplementationArtifact, ComponentReference, ArchitectureDecisionReference,
Limitation, and RecommendedTask.

## 2. Domain / ORM / Mapper Boundary

Domain constructors and validators are semantic authority. Repository contract
is authority for identity lookup, exact replay, immutable conflict, parent
existence, append-only behavior, transitions, graph rules, and concurrency.
ORM is database shape. A Mapper only converts values:

```text
Domain Object → Mapper → new ORM Record
ORM Record → Mapper → Domain Constructor → Domain Validation → Domain Object
```

It never returns a partially valid object, repairs a record, bypasses a Domain
constructor, returns an ORM record as an API object, or decides replay/conflict.

## 3. Mapper Purity

Future mappers are deterministic pure conversion logic: no database, Session,
commit, parent lookup, filesystem, Git, network, environment, random ID,
global mutable state, business transition, or historical mutation. They may
read ORM columns, instantiate ORM records, invoke Domain constructors, derive
the two specified technical IDs, and convert enums, datetime, and JSON.

## 4. Repository Identity

`ImplementationRun.repository_root` in the frozen Domain and ORM is interpreted
as a **Logical Repository Identity**, such as `quantmind-main` or
`factor-lab-v7`. It must be stable across machines and contain no username or
absolute working-tree path. Mapper copies this logical identifier unchanged
and never reads Git remote or resolves local configuration.

Manifest v1 uses the same field name for an execution-time absolute path. That
field is not directly mappable to Domain/ORM. A future Indexer must receive an
explicit, trusted Project Context binding from execution path/source repository
to logical repository ID. Missing or ambiguous binding is
`REPOSITORY_IDENTITY_UNRESOLVED`; guessing from basename, username, path, or Git
remote is forbidden.

This cross-module semantic distinction is a candidate for a future ADR. No
accepted ADR, Domain field, ORM column, or historical Manifest changes here.

## 5. Environment Path Boundary

Execution repository paths remain immutable Manifest/Execution Context facts.
They may be retained as source evidence or future environment artifacts, but
do not participate in cross-machine Run identity and are not copied into the
logical `repository_root` column. Manifest v2 should add distinct
`repository_id` and `execution_repository_path` fields; the existing Domain/ORM
column should eventually be renamed to `repository_id` through a separately
approved contract and migration. Historical Manifests remain byte-for-byte
unchanged and require explicit ingestion binding.

## 6. Stable Technical IDs

ChangedFile and ChangedSymbol have no Domain technical ID but their ORM tables
do. Future Domain-to-record conversion derives a lowercase SHA-256 ID from a
versioned canonical payload. Hashing uses strict UTF-8, Unicode NFC for every
payload field, LF (`U+000A`) separators, no trailing LF, no case folding, and
no whitespace trimming.

Paths must already be Domain-valid repository-relative POSIX paths: `/` is the
separator; absolute paths, backslashes, `.`/`..` traversal, empty segments, and
filesystem/symlink resolution are not normalized by identity logic. Case is
preserved, so case differences produce different IDs.

SHA-256 collision or one ID associated with another natural identity is a hard
`MAPPER_IDENTITY_COLLISION`; no suffix, random fallback, or overwrite is
allowed. Future Indexer metadata must record the identity algorithm version.

## 7. ChangedFile Identity

Version: `changed-file-v1`. Payload, with no final newline:

```text
changed-file-v1\n<implementation_run_id>\n<path>\n<change_type.value>
```

ID: `cf_` plus 64 lowercase hexadecimal SHA-256 characters; length 67.
This exactly mirrors A1b2 identity `(run, path, change_type)`. `before_hash`,
`after_hash`, and `previous_path` never enter identity. For rename, `path` is
the destination and `previous_path` is immutable content; changing it at the
same identity is Repository conflict, not a new ID. Same identity with changed
hashes likewise remains conflict. Exact replay produces the same ID.

## 8. ChangedSymbol Identity

Version: `changed-symbol-v1`. Payload, with no final newline:

```text
changed-symbol-v1\n<implementation_run_id>\n<file_path>\n<qualified_name>
```

ID: `cs_` plus 64 lowercase hexadecimal SHA-256 characters; length 67.
This mirrors A1b2 identity `(run, file_path, qualified_name)`.
`symbol_type` and `change_type` never enter identity; different values at the
same identity are Repository conflict.

## 9. Existing Domain IDs

Mapper copies, never regenerates or renames, these primary IDs:

- `ImplementationTask.task_id`;
- `ImplementationRun.implementation_run_id`;
- `RunRelationship.relationship_id`;
- `TestExecution.test_execution_id`;
- `ImplementationArtifact.artifact_id`;
- `Limitation.limitation_id`;
- `RecommendedTask.recommendation_id`.

ORM-to-Domain passes exact values to constructors. Invalid stored IDs fail; no
trim, case repair, replacement, or historical cleanup occurs.

## 10. Composite Reference Identities

ComponentReference identity is `(implementation_run_id, component_id)`.
ArchitectureDecisionReference identity is `(implementation_run_id, adr_id)`.
Mapper copies both parts unchanged and creates no technical ID. Impact/relation
are content; changing them at the same identity is Repository conflict.

## 11. Enum Conversion

Domain-to-ORM always writes `enum.value`. ORM-to-Domain calls the exact Enum
type with the stored string, then passes the Enum to the Domain constructor.
Unknown strings, wrong case, surrounding whitespace, null, or non-string input
fail; there is no trim, case normalization, or fallback except an explicit
Domain member such as `SymbolType.UNKNOWN`.

This applies to ImplementationTaskStatus, ImplementationRunStatus,
CompletionLevel, VerificationLevel, ConsistencyStatus, CanonicalStatus,
RunRelationshipType, TestExecutionStatus, FileChangeType, SymbolChangeType,
SymbolType, ImpactType, ADRReferenceRelation, LimitationSeverity,
LimitationStatus, and RecommendationPriority.

Enum errors use `UNKNOWN_ENUM`, name the object/field, and include only a
bounded safe summary of the rejected scalar, never the complete record.

## 12. Datetime Conversion

Domain-to-ORM requires timezone-aware datetime, converts it to UTC with
`astimezone(timezone.utc)`, preserves microseconds, and writes datetime rather
than text. ORM-to-Domain rejects naive values as `INVALID_TIME`, converts aware
values to UTC, then invokes the Domain constructor. Mapper never assumes local
timezone or attaches UTC to a naive value. `completed_at=None` is passed as
None; the Domain constructor alone decides whether the state combination is
legal.

## 13. JSON and Tuple Conversion

ImplementationTask `scope` and `explicit_non_goals` convert from Domain
`tuple[str, ...]` to a new JSON list in original order. Mapper does not share a
mutable reference, sort, deduplicate, trim, or otherwise normalize values.

ORM-to-Domain accepts only list or tuple containers whose every item is a
string, creates a new tuple, and invokes the constructor. Mapping, scalar,
number, bool, and null container/items fail as `INVALID_JSON_SHAPE`. Domain
performs final empty/secret/text validation.

## 14. Path and URI Conversion

Repository path fields (`manifest_path`, `report_path`, ChangedFile `path` and
`previous_path`, ChangedSymbol `file_path`) pass unchanged to Domain
constructors. Mapper performs no filesystem access or existence check.

ImplementationArtifact `path_or_uri` also passes unchanged. Existing Domain
semantics are authoritative and deterministic: a value matching
`^[A-Za-z][A-Za-z0-9+.-]*:` is validated as a URI; every other value is
validated as a repository-relative path. Mapper must not replace this with the
informal `contains ://` rule. A value rejected or semantically ambiguous under
the Domain rule fails as `AMBIGUOUS_ARTIFACT_LOCATION`; it is never guessed or
rewritten. Manifest v2 should add `location_kind` (`repository_path` or `uri`)
to make producer intent explicit, but current Domain objects are mappable
without changing historical records.

## 15. Nullable Value Rules

None and empty string are distinct. Mapper preserves None for `parent_task_id`,
`result_commit`, `completed_at`, optional hashes, `previous_path`,
`not_run_reason`, test artifact URI/hash, artifact content hash/schema/size,
and Limitation `component_id`. Unknown hash/commit/location is None only when
the Domain field permits it. Empty string is never converted to None and must
fail through enum/type/Domain validation when illegal.

## 16. Record-to-Domain Errors

Future `RecordToDomainError` contains `object_type`, safe
`record_identity`, `field_name`, `stable_error_code`, `safe_message`, and
`underlying_domain_error_type`. Codes include `UNKNOWN_ENUM`,
`INVALID_IDENTIFIER`, `INVALID_HASH`, `INVALID_COMMIT`, `INVALID_PATH`,
`INVALID_TIME`, `INVALID_STATE_COMBINATION`, `INVALID_JSON_SHAPE`,
`MISSING_REQUIRED_VALUE`, and `AMBIGUOUS_ARTIFACT_LOCATION`.

It never includes secrets, full command, database URL, full description or
reason, ORM repr, or complete record. A malformed record fails atomically;
Mapper does not return a partial object or swallow the Domain exception.

## 17. Domain-to-Record Errors

Future `DomainToRecordError` covers missing technical-ID context, unsupported
Mapper/identity version, a field unrepresentable by the target ORM,
repository identity unresolved, artifact location ambiguity, and target type
limits. It does not duplicate all Domain validation. Safe structured fields
follow the same disclosure restrictions as record-to-domain errors.

## 18. Round-trip Contract

For all eleven families, `domain → record values → Domain constructor` must
equal the original Domain value. Datetimes may normalize to UTC but must
represent the same instant and retain microseconds; task JSON returns tuples;
ChangedFile/Symbol ORM technical IDs do not enter Domain equality; execution
repository path is outside Domain and is not round-tripped.

`record values → domain → record values` must preserve every mapped business
column. SQLAlchemy instrumentation, load state, database defaults, and the two
derived technical ID columns need not be preserved as object internals, but
the technical IDs must deterministically recompute to the same values.

## 19. Mapper Versioning

`mapper_contract_version = "1.0.0"`. A Mapper version change may alter
conversion/error semantics only through a new contract and compatibility
tests. It must not silently reinterpret stored values. The future Indexer must
record Mapper contract version for each indexing run.

## 20. Identity Versioning

`changed_file_identity_version = "changed-file-v1"` and
`changed_symbol_identity_version = "changed-symbol-v1"`. Any change to input,
normalization, separator, encoding, prefix, or digest requires a new version
and therefore new IDs. Old IDs are immutable; Migration/Indexer must never
silently recompute or overwrite history. Current ORM has no identity-version
column, so persistence of the version is deferred and required before durable
indexing.

## 21. Security and Secret Boundary

Mapper never logs or serializes complete objects on failure. It invokes Domain
secret validation for sensitive text and emits only stable codes, type/field,
safe identity, and bounded non-secret summaries. No database URL, environment,
credential, command body, reason, description, or artifact content is read for
diagnostics. Test vectors contain no secret or machine-local path.

## 22. Rules Deferred to Core Mappers

QM2-P0-002A2a2c2 will implement only Task, Run, and RunRelationship conversion,
including enum/time/JSON rules and explicit logical repository identity input.
It must not implement detail/reference/annotation mappers or database access.

## 23. Rules Deferred to Detail Mappers

ChangedFile/Symbol ID derivation, TestExecution, and ImplementationArtifact
conversion remain future detail-mapper work. This contract and vectors are
normative; no function exists in this task.

## 24. Rules Deferred to Repository

Parent existence, exact replay, immutable conflict, updates allowed by the
Repository contract, graph cycles, optimistic concurrency, transactions,
locking, append authorization, and database error translation remain
Repository responsibilities.

## 25. Rules Deferred to Manifest Indexer

Parsing Manifest vocabulary, supplying logical repository binding, storing
Mapper/identity versions, mapping Manifest omissions, creating parent order,
deduplication, Git/hash consistency, and atomic persistence remain Indexer
responsibilities. Mapper never reads a Manifest file itself.

## 26. Compatibility with Manifest v1

Manifest v1 directly supplies most Task/Run scalar fields, tests, artifacts,
Component/ADR refs, limitations, recommendations, timestamps, hashes, and
paths, subject to vocabulary transformation by the future Indexer. It lacks
ChangedFile/Symbol technical IDs, identity-algorithm version, general Run
relationship fields, explicit artifact `location_kind`, and a logical
repository ID distinct from execution path. Its richer changed-file/symbol
objects also require explicit Indexer mapping rather than blind field copying.

Historical Manifests are immutable. Manifest v2 candidates are
`repository_id`, `execution_repository_path`, `location_kind`, Mapper version,
identity versions, and first-class relationship/annotation vocabulary. These
are proposals, not implemented schema changes.

## 27. Handoff to QM2-P0-002A2a2c2

The only next task is `QM2-P0-002A2a2c2 — Core Task, Run and Relationship
Mappers`. It may implement the future `mappers/` error/identity/core boundary
only as explicitly authorized by its own task. This task creates no Mapper
Python file and does not begin that implementation.
