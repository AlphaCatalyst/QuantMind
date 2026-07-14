# Implementation Report: QM2-P0-002A2a2a

## 1. Task Result

- Result: completed.
- Generated task status: `completed_uncommitted`; the Run is recorded before
  its containing commit and therefore has `result_commit = null`.
- Completion level: complete.
- Acceptance: all 40 task criteria passed, including the four mappings,
  bounded scope, static PostgreSQL DDL, regressions, Project Memory, independent
  commit preparation, and a clean Factor Lab source.

## 2. Preflight State

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`.
- Base: `53efb7436b059acb93a23fdce9edb34014fd18ef`.
- Dirty before: no; unrelated dirty files: none.
- Factor Lab: read-only and clean at
  `c83192c2278767e03f008bc39197b1ba33bfb6a9`.
- No reset, stash, clean, amend, rebase, dependency install, lockfile update,
  database access, or push occurred.

## 3. Context Read Confirmation

The mandated sequence was read: AGENTS, Context Index, Charter, Architecture,
Current State, Handoff, Component Catalog, Known Issues, Roadmap, Terminology,
Database Schema Index, persistence audit, A1b1 domain contract, A1b2 Repository
contract, A2a1 ORM contract, ADR-0005, ADR-0007, implementation instructions,
and the A2a1 Report and Manifest. The implementation preserves their authority
order: domain semantics, Repository behavior, then ORM persistence shape.

## 4. Existing ORM Boundary Confirmation

The existing API declarative Base remains the only Base. A2a1's Task, Run, and
RunRelationship mappings were not redesigned. The new records share their
metadata and explicit `quantmind2` schema. Import registers metadata only; it
does not create an Engine, Connection, Session, schema, table, or transaction.

## 5. ORM Package Placement

The four records are in
`backend/services/api/project_knowledge/persistence/orm_detail_models.py`.
The existing core file was already substantial, so one detail module keeps the
boundary legible without fragmenting one class per file. `persistence.__init__`
exports all seven records. No `relationship()` collection is present because
the task needs FK shape, not loading/cascade ownership, and A1b2 behavior will
belong to a future Repository.

## 6. Detail Persistence Decisions

- Schema: explicit `quantmind2` on every table.
- Base: `backend.services.api.models.base.Base`.
- Technical IDs: caller-supplied `VARCHAR(255)` for files/symbols, with no
  default, sequence, UUID, or autoincrement.
- Natural keys: exactly the A1b2 tuples, represented as named unique constraints.
- Domain IDs: `test_execution_id` and `artifact_id` are direct primary keys;
  future indexing must make them globally stable.
- Enums: `VARCHAR(32)` and named checks generated from A1b1 enum values.
- Delete: all Run FKs use `ON DELETE RESTRICT`; no cascade or soft delete.
- Naming: every PK/FK/UQ/check/index is explicit, globally unique in shared
  metadata, type-prefixed, and at most PostgreSQL's 63-character limit.

## 7. ChangedFile ORM

`quantmind2.implementation_changed_files` has seven columns: non-null
`changed_file_id`, Run ID, `path`, and `change_type`; nullable `CHAR(64)`
before/after hashes and nullable previous path. The technical ID is the primary
key. `(implementation_run_id, path, change_type)` is the A1b2 natural unique
key. A rename is identified by its current path; previous path is immutable
provenance, required/nonblank/different only for rename, and indexed.

Checks cover nonblank current path, domain enum values, SHA-256 format, added
(no before, required after), deleted (required before, no after), modified
(both and different), renamed (valid distinct previous path), unchanged (both
and equal), and previous-path scope. Indexes cover Run, current path, previous
path, type, and Run/current path. The FK is restrictive.

## 8. ChangedSymbol ORM

`quantmind2.implementation_changed_symbols` has six non-null columns: technical
ID, Run ID, file path, 512-character qualified name, symbol type, and change
type. The technical ID is primary. The unique key is exactly A1b2's
`(implementation_run_id, file_path, qualified_name)` and deliberately excludes
change type. Thus two types for the same logical symbol in one Run conflict.

Checks cover nonblank file/name plus domain-derived SymbolType and
SymbolChangeType. Indexes cover Run, file, qualified name, symbol type, and
Run/file. No AST or path interpretation occurs in the database.

## 9. TestExecution ORM

`quantmind2.implementation_test_executions` stores the domain ID as primary
key, Run ID, command, purpose, status, passed/failed/skipped integers, nullable
not-run reason, artifact URI, and artifact hash. The run/ID tuple is also the
A1b2 named natural unique key.

Checks require nonblank command/purpose, a domain status, nonnegative counts,
zero failures when passed, positive failures when failed, a nonblank reason
only when not run, and SHA-256 shape when the artifact hash exists. Indexes
cover Run, status, and Run/status. Secret-like command scanning and URI
validation remain domain rules; no command is executed.

## 10. ImplementationArtifact ORM

`quantmind2.implementation_artifacts` stores domain artifact ID as primary key,
Run ID, `VARCHAR(255)` artifact type, opaque path/URI, nullable SHA-256,
nullable `VARCHAR(255)` schema version, and nullable `BIGINT` size. The run/ID
tuple is the A1b2 named natural unique key.

Checks require nonblank type/location, valid hash shape when present, and a
nonnegative size when present. Indexes cover Run, type, hash, and Run/type.
The database neither reads the artifact nor decides whether its location is a
repository path or URI.

## 11. Constraints and Indexes

| Table | Constraint / index | Purpose | Source domain rule |
| --- | --- | --- | --- |
| changed files | `pk_qm2_files`, `fk_qm2_files_run`, `uq_qm2_files_run_path_type` | technical identity, parent, natural identity | A1b2 file key and Run ownership |
| changed files | 10 `ck_qm2_files_*` | enum/hash/change-shape/path scope | A1b1 ChangedFile invariants |
| changed files | 5 `ix_qm2_files_*` | Run/path/rename/type lookup | A1b2 query and provenance needs |
| changed symbols | `pk_qm2_symbols`, `fk_qm2_symbols_run`, `uq_qm2_symbols_run_file_name` | technical identity, parent, natural identity | A1b2 symbol key |
| changed symbols | 4 checks; 5 indexes | nonblank/enums and lookup | A1b1 symbol values |
| tests | `pk_qm2_tests`, `fk_qm2_tests_run`, `uq_qm2_tests_run_id` | domain identity and parent | A1b2 test key |
| tests | 8 checks; 3 indexes | status/count/reason/hash and lookup | A1b1 TestExecution invariants |
| artifacts | `pk_qm2_artifacts`, `fk_qm2_artifacts_run`, `uq_qm2_artifacts_run_id` | domain identity and parent | A1b2 artifact key |
| artifacts | 4 checks; 4 indexes | type/location/hash/size and lookup | A1b1 artifact invariants |

All four FKs target
`quantmind2.implementation_runs.implementation_run_id` with RESTRICT.

## 12. Domain / Repository / Database Boundary

| Rule | Domain | Repository | Database |
| --- | --- | --- | --- |
| path/URI safety | normalize, traversal and credential safety | persist validated values | nonblank only |
| hash | validate and normalize SHA-256 | compare immutable content | nullable `CHAR(64)` regex |
| file change shape | construct valid value | reject conflicting replay | repeated cross-column checks |
| command Secret-like data | reject before persistence | never bypass domain | intentionally not scanned |
| exact replay | immutable object equality | return existing object | unique key only, no equality decision |
| append-only | immutable dataclasses | authorize append/no update/delete | restrictive FK/unique; privileged SQL still possible |
| parent Run | carry Run ID | require existing Run | restrictive FK |
| natural uniqueness | expose logical identity | conflict/exact-replay semantics | named UQ |
| atomic transaction | none | future adapter/UoW responsibility | future transaction, not static metadata |

## 13. Enum Drift Protection

`orm_types.enum_values` extracts values directly from `FileChangeType`,
`SymbolType`, `SymbolChangeType`, and `TestExecutionStatus`; `enum_check_sql`
generates the checks. Tests compare constants and actual check SQL to each
domain Enum. There is no second value list and no PostgreSQL native Enum.

## 14. PostgreSQL DDL Compilation

An existing read-only Python environment at
`/Users/yj/Documents/Codex/2026-06-30/nih/work/QuantMind/.venv/bin/python`
provided SQLAlchemy 2.0.51. Production requirements pin 2.0.25. Tests compiled
`CreateTable` and every `CreateIndex` using `postgresql.dialect()`, confirming
schema qualification, checks, names, indexes, and RESTRICT while rejecting
CASCADE, trigger text, URLs, and secret markers.

Compilation constructs SQL strings only. Static source tests exclude Engine,
Session, execute, commit, rollback, `create_all`, and `drop_all`. It does not
prove migration order, schema permissions, pinned-version output, real-server
execution, concurrent uniqueness, or PostgreSQL transaction behavior.

## 15. Files Added

- `backend/services/api/project_knowledge/persistence/orm_detail_models.py`:
  four mappings.
- `backend/services/tests/test_project_knowledge_ledger_detail_orm.py`: static
  detail contract and DDL suite.
- `docs/quantmind2/implementation/LEDGER_CORE_DETAIL_ORM_MAPPING_V1.md`: the
  25-section persistence contract.
- This Run's `report.md` and `manifest.json`.

## 16. Files Modified

- Persistence exports and domain enum-derived ORM constants.
- A2a1 ORM and A1b2 scope regressions to admit exactly the one new detail file.
- Context validator and Context unittest to enforce the new contract and exact
  A2a2b handoff.
- Human/machine Current State, Component Catalog, Known Issues, Roadmap, Handoff,
  Terminology, and Database Schema Index. No accepted ADR changed.

## 17. Core Classes and Symbols

| File | Symbol | Responsibility | Future consumer |
| --- | --- | --- | --- |
| `orm_detail_models.py` | `ChangedFileRecord` | file change row/constraints | mapper, migration, Repository |
| `orm_detail_models.py` | `ChangedSymbolRecord` | symbol change row/constraints | mapper, migration, Repository |
| `orm_detail_models.py` | `TestExecutionRecord` | test result row/constraints | mapper, migration, Repository |
| `orm_detail_models.py` | `ImplementationArtifactRecord` | artifact reference row/constraints | mapper, migration, Repository |
| `orm_types.py` | four detail value tuples | domain Enum persistence values | checks/tests/migration |
| `validate_context_bootstrap.py` | detail contract/source checks | prevent scope/status drift | Codex bootstrap |

## 18. Runtime / Registration Flow

```text
API Base
→ Core Ledger ORM
→ Core Run Detail ORM
→ Shared metadata with seven quantmind2 table targets
→ Future migration
```

Only the first four metadata-registration steps exist. No database, runtime
registration hook, migration, or table is run or deployed.

## 19. Boundary and Edge-case Handling

- Rename uses current path in the natural key and preserves/indexes previous path.
- Unchanged requires equal present hashes; modified requires unequal present hashes.
- `not_run` requires a reason; every executed status forbids it.
- Artifact location remains opaque to the database.
- File/symbol technical IDs must be stable future Indexer inputs.
- Test/artifact domain IDs are primary keys, so future IDs must be globally stable.
- No Mapper, migration, schema creation, relationship, Repository, or database exists.

## 20. Tests Executed

| Command | Purpose | Passed | Failed | Skipped | Not run | Key output |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| external Python `-m unittest ...ledger_detail_orm ...ledger_core_orm` | new ORM and A2a1 regression | 66 | 0 | 0 | 0 | OK; 32 detail + 34 core |
| `python3 -m unittest ...ledger_domain ...repository_contract ...context_bootstrap` | A1b1/A1b2/Context regression | 154 | 0 | 0 | 0 | OK |
| `python3 tools/quantmind2/validate_context_bootstrap.py` | machine/human context and scope | 23 | 0 | 0 | 0 | passed, 23 named checks |
| external Python `-m py_compile` on 6 targeted files | syntax/import surface | 6 | 0 | 0 | 0 | no output |
| Python JSON parse over `docs/quantmind2/**/*.json` | machine documents before Run | 22 | 0 | 0 | 0 | parsed_json=22 |
| actual Manifest schema/report/payload hash validation | immutable Run contract | 3 | 0 | 0 | 0 | passed after Run generation |
| `git diff --check` plus allowlist/dependency/migration/business scope guards | whitespace and task boundary | 3 | 0 | 0 | 0 | clean |
| Factor Lab HEAD/status read-only check | donor identity and cleanliness | 2 | 0 | 0 | 0 | expected commit; empty status |
| real PostgreSQL integration | explicitly prohibited/deferred | 0 | 0 | 0 | 1 | not run |

No service, Electron, database, TDX, Qlib, LightGBM, or Factor Lab Campaign ran.

## 21. Expected vs Actual

| Requirement | Expected | Actual | Evidence | Status |
| --- | --- | --- | --- | --- |
| table scope | exact four details | exact four registered | metadata tests | passed |
| shared Base/schema | API Base/quantmind2 | identity and DDL exact | ORM tests | passed |
| identities | technical/file-symbol and domain/test-artifact | no generated IDs; A1b2 UQs | metadata tests | passed |
| fields/types/nullability | domain-aligned | all asserted | per-table tests | passed |
| checks/indexes | named and complete | all expected sets exact | contract tests | passed |
| enum drift | domain-derived | four enums compared | drift tests | passed |
| deletion | RESTRICT/no cascade | all DDL restrictive | DDL tests | passed |
| runtime | no DB/DDL/session | static metadata only | AST/source tests | passed |
| regressions | A1b1/A1b2/A2a1/Context | 220 unittest cases clean | final commands | passed |
| Project Memory | truthful partial state | seven mappings, absent deployment | Context validator | passed |
| Factor Lab | read-only/clean | unchanged at expected HEAD | Git check | passed |
| forbidden work | no refs/mappers/migration/repo/API | absent | scope tests/diff | passed |

## 22. Implementation Run

- Run ID: `QM2-P0-002A2a2a-20260714T164637Z-53efb74`.
- Report: this file.
- Manifest: adjacent `manifest.json`.
- Base: `53efb7436b059acb93a23fdce9edb34014fd18ef`.
- Result commit: null in the immutable, pre-commit Manifest.
- Generated status: `completed_uncommitted`.
- Verification: targeted unit/static tests and dialect-only PostgreSQL DDL.

## 23. Project Memory Updates

Current State and Handoff identify A2a2a and this Run. The Component Catalog
lists all four records while keeping Project Knowledge partial. Known Issues
now distinguishes mapped core details from absent references/mappers/deployment.
Roadmap splits A2a2a from A2a2b. Terminology and Database Schema Index explain
that seven mappings are metadata targets, not deployed tables. Machine-readable
next-task fields retain parent `QM2-P0-002` due schema v1.

## 24. Known Limitations

- ComponentReference, ArchitectureDecisionReference, Limitation, and
  RecommendedTask ORM records remain absent.
- No Domain/ORM Mapper, migration, schema/table creation, real PostgreSQL,
  production Repository, Session/UoW, Indexer, API, or UI exists.
- Static SQLAlchemy 2.0.51 differs from the production 2.0.25 pin.
- SQLite is not valid evidence for schema, regex, JSONB, transaction, or
  PostgreSQL concurrency behavior.
- Database checks cannot enforce path/URI safety, secret scanning, exact replay,
  append authorization, immutable-content equality, or atomic batches.

## 25. Unresolved Questions

- What deterministic algorithm will the future Mapper/Indexer use for file and
  symbol technical IDs?
- Will test/artifact IDs be guaranteed globally unique, as required by their
  direct-primary-key mapping, or will a future accepted decision revise identity?
- How will pinned SQLAlchemy 2.0.25 and an isolated PostgreSQL fixture be supplied?

## 26. Compatibility and Rollback

The change is additive metadata/documentation and needs SQLAlchemy 2.x with
PostgreSQL dialect support. Rollback is the single containing Git commit. No
database/data rollback exists because no migration or DDL was executed. The
file/symbol technical ID and test/artifact global-ID assumptions must be
preserved by future mappers unless a later accepted contract supersedes them.

## 27. Scope Confirmation

Not implemented: ComponentReference ORM, ArchitectureDecisionReference ORM,
Limitation ORM, RecommendedTask ORM, Domain mappers, PostgreSQL Repository,
database schema creation, migration, Session, Unit of Work, Manifest
Parser/Indexer, Git consistency, API, UI, TDX, Dataset Snapshot, Factor DSL,
Optimization, Validation runtime, Factor Registry, LightGBM changes, and Qlib
changes. Factor Lab was not modified. A2a2b was not started.

## 28. Git State After

The task will create one commit named
`feat(qm2): map core ledger detail ORM models`. The immutable Manifest keeps
`result_commit = null` to avoid self-reference. Final verification must show
`master` at that new commit, clean QuantMind and Factor Lab worktrees, and no
push.

## 29. Recommended Next Task

Only `QM2-P0-002A2a2b — Ledger Reference and Annotation ORM Mapping` is
recommended. It was not implemented here.
