# Implementation Ledger Domain Model v1

Status: implemented pure domain contract
Task: `QM2-P0-002A1b1 — Implementation Ledger Domain Model and Invariants`
Base commit: `6ec76c05591fd85489df87df985be28ba3fe5bc4`

## 1. Scope

This contract defines immutable Implementation Ledger values, enums, structured
domain errors, value validators, single-object invariants, and direct Run
relationship checks. The implementation is standard-library Python under
`backend/services/engine/project_knowledge/domain/`.

It does not define repositories, persistence, ORM mappings, tables, migrations,
sessions, transactions, indexing, Git reconciliation, APIs, or UI.

## 2. Domain vs Persistence Boundary

Domain construction accepts already supplied values, normalizes safe text,
hashes and timezone-aware datetimes, and rejects invalid combinations. It does
not generate IDs, inspect Git, read manifests, resolve paths, read environment
variables, access files, connect to a database, or call a network service.

Git remains the authority for code and immutable Implementation Runs.
PostgreSQL remains a future rebuildable query index. A future Repository will
map these objects to storage without moving persistence behavior into them.

The implementation uses `@dataclass(frozen=True)` plus `str, Enum` and explicit
validators. This matches the repository's existing standard-library dataclass
and Enum use while avoiding Pydantic, FastAPI, and SQLAlchemy. `slots=True` is
deliberately not used because the current system `python3` is 3.9 and must run
the required tests; frozen dataclasses still provide immutable value semantics.

## 3. Object Catalog

| Object | Responsibility | Identity/owner |
| --- | --- | --- |
| `ImplementationTask` | task intent, scope, non-goals, status | `task_id` |
| `ImplementationRun` | one implementation execution fact and state combination | `implementation_run_id` |
| `RunRelationship` | directed immutable relationship between two Runs | `relationship_id` |
| `ChangedFile` | file-level change or explicit unchanged verification | Run + path |
| `ChangedSymbol` | symbol-level semantic change | Run + file + qualified name |
| `TestExecution` | declared command, purpose, outcome counts, optional artifact | `test_execution_id` |
| `ImplementationArtifact` | repository path or structural URI plus metadata/hash | `artifact_id` |
| `ComponentReference` | component impact attributed to a Run | Run + component |
| `ArchitectureDecisionReference` | ADR relation attributed to a Run | Run + ADR |
| `Limitation` | structured severity/status limitation without secret content | `limitation_id` |
| `RecommendedTask` | one bounded P0/P1/P2 next-task recommendation | `recommendation_id` |

All sequences stored by `ImplementationTask` are converted to tuples. All
objects normalize timezone-aware timestamps to UTC and use `object.__setattr__`
only during frozen dataclass construction.

## 4. Enum Catalog

`domain/enums.py` defines stable values:

- `ImplementationTaskStatus`: planned, ready, running, completed, partial,
  blocked, cancelled.
- `ImplementationRunStatus`: running, completed_uncommitted,
  partial_uncommitted, completed_committed, partial_committed, failed, blocked,
  cancelled.
- `CompletionLevel`: none, partial, complete.
- `VerificationLevel`: not_verified, static_checks, targeted_tests,
  integration_tests, full_relevant_tests.
- `ConsistencyStatus`: unverified, consistent, warning, error, stale.
- `CanonicalStatus`: noncanonical, candidate, canonical, rejected.
- `RunRelationshipType`: finalizes, corrects, supersedes, depends_on, retries,
  continues.
- `TestExecutionStatus`: passed, failed, skipped, not_run.
- `FileChangeType`: added, modified, deleted, renamed, unchanged.
- `SymbolChangeType`: added, modified, deleted, renamed.
- `SymbolType`: module, class, function, method, constant, schema, table,
  endpoint, document, unknown.
- `ImpactType`: introduced, modified, deprecated, removed, verified,
  documented, unaffected.
- `ADRReferenceRelation`: implements, conforms_to, documents, supersedes,
  affected_by.
- `LimitationSeverity`: info, low, medium, high, critical.
- `LimitationStatus`: open, accepted, resolved, superseded.
- `RecommendationPriority`: P0, P1, P2.

Core states are never represented as unconstrained strings.

## 5. ImplementationTask Invariants

- `task_id`, title, objective, status, and aware `created_at` are required.
- IDs are normalized and validated; `QM2-P0-002A1b1` is legal.
- `parent_task_id` is optional but cannot equal `task_id`.
- Scope and explicit non-goals must be string sequences and become immutable
  tuples.
- Completing a Task does not imply any Run is committed or canonical.

## 6. ImplementationRun Invariants

| Status | `result_commit` | `completed_at` | Completion requirement | Canonical allowed |
| --- | --- | --- | --- | --- |
| running | optional by base rule, normally none | forbidden | none or partial | no |
| completed_uncommitted | forbidden | required | complete | no |
| partial_uncommitted | forbidden | required | partial | no |
| completed_committed | required | required | complete | only with all canonical gates |
| partial_committed | required | required | partial | no, because canonical requires complete |
| failed | optional | required | any | no |
| blocked | optional | required | any | no |
| cancelled | optional | required | any | no |

A canonical Run must be committed, have a full result commit, be consistent,
and have complete completion level. `completed_committed` alone remains
noncanonical unless canonical status is explicitly supplied and all gates pass.

`base_commit` is always a full 40-character SHA. `result_commit` is either a
full SHA or `None`. Manifest/report paths are repository-relative. Optional
hashes use `None` for unknown and a 64-character SHA-256 when present. Start
must not be after completion.

`repository_root` is a logical repository identity, despite the historical
field name. It is validated as an identifier and cannot contain a machine-local
absolute path. Manifest v1's `repository` field is the preferred mapping;
Manifest v1's absolute `repository_root` is environment evidence, not portable
domain identity.

## 7. Run Relationship Semantics

- `finalizes`: source records finalization work for target; it does not mutate
  target.
- `corrects`: source adds corrected immutable evidence; target remains intact.
- `supersedes`: source becomes preferred for future use; target is not deleted.
- `depends_on`: source requires target as prior evidence.
- `retries`: source is a new Run retrying a terminal target.
- `continues`: source continues incomplete work from target.

Source and target must differ, reason is mandatory and secret-checked, and time
must be aware. `has_direct_reverse_conflict` identifies a two-node reversed
edge regardless of relationship kind. `validate_direct_relationship` checks one
candidate against supplied direct edges. Complete DAG cycle detection,
cross-record uniqueness, relationship admission, and target existence are
deferred to the Repository layer.

## 8. Changed File and Symbol Semantics

File rules:

- added: `before_hash=None`, valid `after_hash` required;
- deleted: valid `before_hash` required, `after_hash=None`;
- modified: both valid and different hashes required;
- renamed: `previous_path` required and different from `path`; hashes are
  optional because rename detection may be metadata-only;
- unchanged: both hashes required and equal; reserved for explicit verification;
- `previous_path` is forbidden for non-renames.

All paths are safe repository-relative POSIX paths. `ChangedSymbol` records a
non-empty qualified name, safe file path, constrained symbol type, and
constrained change type. It does not parse or verify a real AST.

## 9. Test Execution Semantics

- All counts are non-negative integers.
- passed requires zero failures.
- failed requires at least one failure.
- not_run requires a non-empty reason.
- executed statuses forbid `not_run_reason`.
- command and reason reject obvious secret-like patterns.
- optional artifact URI is structurally validated and never fetched.
- optional artifact hash is SHA-256.
- construction never executes the command.

## 10. Artifact and Reference Semantics

`ImplementationArtifact.path_or_uri` requires exactly one location string. A
scheme-prefixed value receives minimal URI validation; otherwise it is treated
as a repository-relative path. Content is never opened. Hash and size are
optional; present size is non-negative.

Component impact, ADR relation, limitation severity/status, and recommendation
priority use enums. ADR IDs use `ADR-NNNN` or a longer numeric suffix.
Limitation descriptions and recommendation reasons reject obvious secrets.

## 11. Path, Hash, Commit and Time Rules

- Identifier: trimmed, 1-255 characters, explicit alphanumeric/dot/underscore/
  colon/hyphen set, no path separators or controls.
- SHA-256: exactly 64 hexadecimal characters; normalized lowercase.
- Full commit: exactly 40 hexadecimal characters; normalized lowercase.
- Short commit: only explicit short-SHA fields accept 7-12 hexadecimal
  characters. No core Run field uses a short commit.
- Path: non-empty, already-normalized POSIX repository-relative path; rejects
  absolute, drive-qualified, backslash, NUL, dot, and parent traversal.
- URI: requires a syntactically valid scheme plus authority or path; rejects
  embedded username/password; performs no network access.
- Datetime: must have an offset and is normalized to UTC; naive values fail.

Validators do not check path existence, commit existence, hash/content
agreement, URI reachability, repository membership, or Git ancestry.

## 12. Secret-handling Boundary

The conservative detector rejects obvious private-key headers,
credential-bearing URIs, password/token/API-key/secret assignments, and Bearer
authorization values. Errors expose only stable error code, field name, and a
generic reason; the rejected value is never included.

This is not a complete secret scanner and does not replace repository secret
scanning. Fields that should never contain content store only identifiers,
paths/URIs, booleans, counts, hashes, or key names.

## 13. Manifest v1 Mapping

| Manifest v1 | Domain mapping | Gap |
| --- | --- | --- |
| task fields | `ImplementationTask` | Manifest lacks Task lifecycle time/status separate from Run |
| Run identity/status/times/hashes | `ImplementationRun` | verification names require explicit mapping; repository root semantics differ |
| changed_files | `ChangedFile` | v1 stores paths only, not change type or before/after hashes |
| changed_symbols | `ChangedSymbol` | v1 stores strings, not file/type/change dimensions |
| tests_executed | `TestExecution` | v1 has no test execution ID/artifact URI; status vocabulary maps directly |
| artifacts | `ImplementationArtifact` | v1 separates path but has no artifact ID, size, or path/URI union |
| component_refs | `ComponentReference` | v1 lacks impact type |
| architecture_decision_refs | `ArchitectureDecisionReference` | v1 lacks relation |
| known_limitations | `Limitation` | v1 lacks identity, severity, component, and status |
| next_recommended_tasks | `RecommendedTask` | v1 lacks recommendation ID, priority, and reason |
| `corrects_run_id` | `RunRelationship(CORRECTS)` | v1 lacks general relationships |

No Manifest v1 file or historical Run is changed. A future mapper must define
vocabulary translations such as `structural → static_checks`,
`integration → integration_tests`, and `full_suite → full_relevant_tests`.
Manifest v2 is deferred.

## 14. Rules Deferred to Repository Layer

- ID uniqueness and target existence;
- complete relationship graph/DAG cycle detection;
- direct conflict queries across persisted edges;
- canonical candidate selection and promotion authorization;
- correction/finalization cardinality;
- Git object existence, ancestry, containing-commit resolution, and immutable
  historical Run enforcement;
- idempotency, concurrent writes, rebuild/reconciliation, and query semantics;
- in-memory test double and Repository Protocol/ABC.

## 15. Rules Deferred to ORM/Migration Layer

- SQLAlchemy mapping, PostgreSQL types, constraints, indexes, foreign keys,
  schema qualification, and transaction ownership;
- `quantmind2` schema/table creation;
- migration ordering, checksums, rollback, deployment invocation, and role
  privileges;
- persistence serialization and enum storage.

No ORM, table, migration, Session, Unit of Work, or database call exists in the
domain package.

## 16. Compatibility Notes

- Standard-library-only construction runs with the current system Python 3.9.
- Type annotations use postponed evaluation for compatibility.
- Frozen dataclasses are straightforward to map to ORM rows or manifest DTOs
  without making domain objects ORM entities.
- Domain `repository_root` intentionally maps to a logical repository identity,
  not the environment-specific absolute Manifest v1 path.
- The package location does not determine future persistence ownership; the
  persistence audit continues to assign a future API control-plane Repository.

## 17. Evidence and Source Files

- `backend/services/engine/project_knowledge/domain/enums.py`
- `backend/services/engine/project_knowledge/domain/errors.py`
- `backend/services/engine/project_knowledge/domain/validators.py`
- `backend/services/engine/project_knowledge/domain/models.py`
- `backend/services/engine/project_knowledge/domain/relationships.py`
- `backend/services/tests/test_project_knowledge_ledger_domain.py`
- `docs/quantmind2/implementation/LEDGER_PERSISTENCE_REALITY_AUDIT_V1.md`
- ADR-0005, ADR-0007, and ADR-0009

## 18. Handoff to QM2-P0-002A1b2

`QM2-P0-002A1b2 — Ledger Repository Contract and In-memory Test Double` may
define repository operations, query semantics, target existence, uniqueness,
full cycle detection, and an in-memory test double against these immutable
objects. It must remain independent of SQLAlchemy and must not implement ORM,
PostgreSQL tables, migration, indexer, API, or UI unless its own contract
explicitly authorizes them.

This task does not define a Repository interface or in-memory Repository.
