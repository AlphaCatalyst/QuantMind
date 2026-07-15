# Implementation Report: QM2-P0-002A2a2c2b

## 1. Task Result

Completed. Pure bidirectional ImplementationRun conversion is implemented;
all 38 acceptance criteria pass. The generated Run is pre-commit
`completed_uncommitted`; work stopped before Relationship mapping.

## 2. Preflight State

QuantMind was clean on `master` at
`56730109b71aedadd9e2975fcb0633b95b222860`; unrelated dirty files: none.
Factor Lab remained clean/read-only at
`c83192c2278767e03f008bc39197b1ba33bfb6a9`.

## 3. Context Read Confirmation

All mandated Project Memory, architecture, Domain/Repository/ORM/Mapper
contracts, ADR-0005/0007, prior Run, and real Domain/ORM/Mapper code were read.
Domain is state authority; ORM is shape; Mapper converts loaded values;
Repository owns replay, transitions, version updates, conflict and transaction.

## 4. Run Mapper Design

`run.py` is separate because Run has twenty-three business fields and state
semantics distinct from Task. Explicit functions keep every field reviewable.
It does not parse Manifest or map Relationship because those require separate
input and authority boundaries. It reuses exact Enum and aware-time utilities.

## 5. Repository Identity Boundary

`repository_root` is copied only as an already validated logical repository
identity. No absolute execution path parameter, basename/remote inference,
Context lookup, filesystem check, Git read or default `quantmind-main` exists.
Future Indexer must first supply an explicit trusted binding.

## 6. ImplementationRun Domain-to-ORM

`implementation_run_to_record` requires a formal frozen Domain Run, explicitly
maps every business field, converts five Enums, converts present datetimes to
UTC, preserves nullable values, and returns a fresh ORM record with version 1.
It performs no lookup, status transition, canonical decision or persistence.

## 7. ImplementationRun ORM-to-Domain

`implementation_run_from_record` requires a formal record, reads only loaded
instance-state values, validates positive non-bool version, converts five
Enums and times, and calls the official `ImplementationRun(...)` constructor.
Expected Domain failures become safe RecordToDomainError; unexpected defects
are not swallowed. Missing/expired fields never trigger descriptor refresh.

## 8. Field Mapping Table

| Domain field | ORM field | Conversion |
| --- | --- | --- |
| implementation_run_id, task_id | same | exact IDs |
| repository_root | same | exact logical identity |
| branch, agent_type, manifest_schema_version | same | exact text/ID |
| base_commit | same | exact required full commit |
| result_commit | same | exact full commit or None |
| task_status | same | ImplementationRunStatus.value |
| completion_level | same | CompletionLevel.value |
| verification_level | same | VerificationLevel.value |
| consistency_status | same | ConsistencyStatus.value |
| canonical_status | same | CanonicalStatus.value |
| workspace_dirty_before/after | same | exact bools |
| started_at | same | aware datetime to UTC |
| completed_at | same | aware datetime to UTC or None |
| manifest_path, report_path | same | exact repository paths |
| four hash fields | same | exact SHA-256 or None |
| none | version | new 1 / stored positive validation |

## 9. Enum Conversion

All five Run Enums persist exact `.value` and reconstruct by exact Enum type.
Unknown, wrong-case, padded, null and non-string values fail as `UNKNOWN_ENUM`.
No trim, repair, Enum-name storage or fallback occurs.

## 10. Commit, Hash and Path Handling

Base commit, optional result commit, four optional hashes and two repository
paths are copied without Mapper normalization. No Git object/ancestry query,
hash calculation/content comparison, file existence check or path resolution
exists. ORM-to-Domain delegates stored-value validity to Domain constructors.

## 11. Datetime and Nullable Handling

Started time is required; completed time may be None. Present values must be
aware, normalize to UTC and retain microseconds. Result commit, completed time
and four hashes preserve None. Empty strings are never silently converted.

## 12. Version Field Boundary

Version is ORM-only. New records are version 1; stored version must be a
positive non-bool integer and is excluded from Domain. A version-9 record
reconstructed and converted creates a new version-1 record. Mapper is not an
existing-row update API; Repository owns expected version and increments.

## 13. State and Canonical Validation Boundary

Mapper converts state fields but never transitions, repairs, promotes or
recomputes them. Official Domain construction enforces committed/result,
running/terminal time, complete/partial, consistency and canonical gates.
Malformed records fail atomically with safe field/code metadata.

## 14. Round-trip Semantics

Tests cover running, completed uncommitted, completed committed noncanonical,
canonical, partial committed, failed, blocked and cancelled; null/present
hashes; non-UTC time; dirty combinations; safe paths; and logical identity.
UTC normalization and new-record version reset are the intended differences.

## 15. Purity and Side-effect Boundary

AST/source guards exclude Engine, Session, Connection, SQL, add/flush/refresh/
merge/commit/rollback, filesystem, Git, network, environment, random IDs,
Manifest binding and Relationship conversion. No database or service ran.

## 16. Files Added

- `persistence/mappers/run.py`.
- `test_project_knowledge_ledger_run_mapper.py`.
- `LEDGER_RUN_MAPPER_V1.md`.
- This Run's Report and Manifest.

## 17. Files Modified

Mapper exports; Task/Repository/Context boundary regressions; Bootstrap
validator/test; allowed Current State, Component Catalog, Known Issues,
Roadmap, Handoff, Terminology, Database Schema Index and machine peers. No
Domain, ORM model, Repository, ADR, dependency, lockfile or Factor Lab change.

## 18. Core Functions and Classes

| Symbol | Responsibility |
| --- | --- |
| `implementation_run_to_record` | validated Run to new version-1 record |
| `implementation_run_from_record` | loaded record to validated Domain Run |
| `_safe_run_identity` | bounded non-secret diagnostic Run ID |
| `_loaded_column` | no-lazy-load required-column access |

## 19. Boundary and Error Handling

Wrong types, five unknown Enums, naive time, invalid version, absent columns,
invalid commit/hash/path/repository identity, missing commit, illegal terminal
time and illegal canonical combinations fail safely. Errors omit record repr,
arbitrary repository values, content, source bundle, URL and secrets.

## 20. Tests Executed

| Scope | Passed | Failed | Skipped | Not run |
| --- | ---: | ---: | ---: | ---: |
| dedicated Run Mapper | 19 | 0 | 0 | 0 |
| Task Mapper regression | 25 | 0 | 0 | 0 |
| all eleven ORM mappings | 108 | 0 | 0 | 0 |
| Domain | 76 | 0 | 0 | 0 |
| Repository contract | 60 | 0 | 0 | 0 |
| Context unittest | 19 | 0 | 0 | 0 |
| final combined unittest | 307 | 0 | 0 | 0 |
| Context Bootstrap | 33 | 0 | 0 | 0 |
| changed Python compile | 7 | 0 | 0 | 0 |
| JSON parse before Run | 28 | 0 | 0 | 0 |
| real PostgreSQL | 0 | 0 | 0 | 1 |

No failed test iteration occurred. The first targeted and final combined runs
both passed. PostgreSQL remained intentionally not run by task prohibition.

## 21. Expected vs Actual

| Requirement | Expected | Actual | Evidence | Status |
| --- | --- | --- | --- | --- |
| both directions | explicit Run mapping | two functions | 19 tests | passed |
| all fields | twenty-three business fields | explicit mapping | table/tests | passed |
| five Enums | exact values | common utilities | negative vectors | passed |
| state validity | Domain authority | formal constructor | malformed records | passed |
| logical repository | no guessing | exact copy | source/round trip | passed |
| version | new 1/stored positive | ORM-only boundary | tests | passed |
| purity | no I/O/DB | AST and source guards | tests | passed |
| scope | Task + Run only | no other family | Bootstrap | passed |

## 22. Implementation Run

Run `QM2-P0-002A2a2c2b-20260715T043224Z-5673010`; base
`56730109b71aedadd9e2975fcb0633b95b222860`; pre-commit result null; status
`completed_uncommitted`; verification `targeted_tests`.

## 23. Project Memory Updates

Memory records Task and Run Mappers as implemented, all other Mapper families
and persistence runtime as absent, logical repository identity boundary, and
exact human handoff to A2a2c2c. Machine next-task fields retain legal parent.

## 24. Known Limitations

No Relationship/detail/reference/annotation Mapper; no technical ID, artifact
location, Manifest binding or repository identity resolver; no Repository,
Session/UoW, migration, database, Indexer, API or UI. Existing-row version
update path and real PostgreSQL/pinned-runtime evidence remain absent.

## 25. Unresolved Questions

Future Indexer trusted repository binding, Mapper/identity version persistence,
Repository conflict/update translation, and real PostgreSQL behavior remain
unresolved. Relationship graph admission remains Repository work.

## 26. Compatibility and Rollback

Additive Run conversion under Mapper contract 1.0.0. Rollback is the single
containing commit; no database/data/migration/config rollback is needed.

## 27. Scope Confirmation

Not implemented: RunRelationship; ChangedFile/Symbol identities; detail,
reference, annotation mappers; Manifest binding; repository identity resolver;
Repository, Session/UoW, migration, Parser/Indexer, API/UI; TDX, Dataset
Snapshot, Factor DSL/Optimization/Validation/Registry; LightGBM/Qlib changes.

## 28. Git State After

One commit will use `feat(qm2): implement ledger run mapper`. Manifest remains
truthfully pre-commit with null result commit. No amend or push.

## 29. Recommended Next Task

Only `QM2-P0-002A2a2c2c — RunRelationship Mapper`. It must remain a separate
bounded increment. This task did not begin it.
