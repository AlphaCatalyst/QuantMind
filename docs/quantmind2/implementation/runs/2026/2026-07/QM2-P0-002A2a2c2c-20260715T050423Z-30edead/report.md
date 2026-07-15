# Implementation Report: QM2-P0-002A2a2c2c

## 1. Task Result

Completed. The remaining nine Mapper families, two frozen technical-ID
functions, complete eleven-object round trips, and Mapper drift verification
are implemented. The pre-commit Run is `completed_uncommitted`.

## 2. Preflight State

QuantMind was clean on `master` at
`30edead1d4b8eeece2be2978d6d42c94576122cc`; unrelated dirty files: none.
Factor Lab was clean and read-only at
`c83192c2278767e03f008bc39197b1ba33bfb6a9`.

## 3. Context Read Confirmation

The mandated Context, architecture, Domain/Repository/ORM/Mapper contracts,
ADR-0005/0007, c1/c2a/c2b Runs, and real Domain/ORM/Mapper sources were read.
Domain remains value authority, Repository remains persistence-semantics
authority, Mapper remains a deterministic conversion boundary.

## 4. Consolidated Mapper Architecture

The package now has explicit Task, Run, Relationship, Detail, Reference, and
Annotation modules plus bounded common/error/identity helpers. No reflective
Mapper, runtime registry, database adapter, or automatic field traversal was
introduced.

## 5. Stable Technical ID Implementation

### ChangedFile

`changed_file_record_id` hashes the frozen NFC/UTF-8/LF/no-trailing-LF payload
of identity version, Run ID, path, and exact file change value. Hash content and
previous path are excluded. Output is `cf_` plus lowercase SHA-256.

### ChangedSymbol

`changed_symbol_record_id` hashes identity version, Run ID, file path, and
qualified name under the same canonical rules. Symbol and change types are
excluded. Output is `cs_` plus lowercase SHA-256.

## 6. RunRelationship Mapper

All six fields map explicitly. Enum values are exact and aware datetimes become
UTC. The Mapper performs no endpoint lookup, reverse-edge creation, cycle
check, replay decision, update, or delete.

## 7. Detail Mappers

### ChangedFile

The Mapper generates and reverse-validates the technical ID and preserves all
change types, hashes, previous path, Unicode, and case. Domain construction
owns legal change-shape enforcement.

### ChangedSymbol

The Mapper generates and reverse-validates technical identity and converts both
Enums exactly. It does not read source or parse ASTs.

### TestExecution

Command, purpose, exact status, counts, nullable reason, URI, and hash map
without executing or reading artifacts. Invalid combinations fail in Domain.

### ImplementationArtifact

All seven actual fields map explicitly. The Domain constructor remains the
authority for scheme-prefix URI versus repository-relative path semantics.
No filesystem or network access occurs.

## 8. Reference Mappers

Component and ADR references map explicit parent Run IDs and exact Enums. They
do not query Component Catalog, inspect ADR files, or validate external entity
existence.

## 9. Annotation Mappers

Limitation and RecommendedTask preserve all fields, including nullable
component identity. They do not mutate history, create Tasks, or execute a
recommendation; rejected description/reason values are absent from errors.

## 10. Parent Run Context Boundary

Every Detail/Reference/Annotation `to_record` accepts an explicit Run ID,
validates it with the common Domain identifier rule, and requires it to equal
the Domain object's Run ID. No global, repository, path, or inferred context is
accepted.

## 11. Common Conversion and Error Handling

`common.py` adds safe diagnostic identity, already-loaded-column access, and
parent Run validation without changing Task/Run public behavior. Unknown Enums,
missing values, bad technical IDs, and Domain failures use stable safe Mapper
errors and never include full records, commands, descriptions, or reasons.

## 12. Complete Mapper Inventory

| Domain Object | ORM Record | To Record | From Record | Identity |
| --- | --- | --- | --- | --- |
| ImplementationTask | ImplementationTaskRecord | implementation_task_to_record | implementation_task_from_record | task_id |
| ImplementationRun | ImplementationRunRecord | implementation_run_to_record | implementation_run_from_record | implementation_run_id |
| RunRelationship | RunRelationshipRecord | run_relationship_to_record | run_relationship_from_record | relationship_id |
| ChangedFile | ChangedFileRecord | changed_file_to_record | changed_file_from_record | changed-file-v1 technical ID |
| ChangedSymbol | ChangedSymbolRecord | changed_symbol_to_record | changed_symbol_from_record | changed-symbol-v1 technical ID |
| TestExecution | TestExecutionRecord | test_execution_to_record | test_execution_from_record | test_execution_id |
| ImplementationArtifact | ImplementationArtifactRecord | implementation_artifact_to_record | implementation_artifact_from_record | artifact_id |
| ComponentReference | ComponentReferenceRecord | component_reference_to_record | component_reference_from_record | Run/component composite |
| ArchitectureDecisionReference | ArchitectureDecisionReferenceRecord | architecture_decision_reference_to_record | architecture_decision_reference_from_record | Run/ADR composite |
| Limitation | LimitationRecord | limitation_to_record | limitation_from_record | limitation_id |
| RecommendedTask | RecommendedTaskRecord | recommended_task_to_record | recommended_task_from_record | recommendation_id |

## 13. Round-trip and Drift Verification

All eleven Domain objects round-trip through ORM. All remaining ORM business
columns round-trip back to new records. Drift guards compare dataclass fields,
ORM columns, public Mapper inventory, Enum coverage, technical vectors, safe
errors, and AST purity. Task and Run regressions remain green.

## 14. Purity and Side-effect Boundary

Source guards exclude Engine, Session, Connection, SQL, transactions,
filesystem, Git, network, environment, random identity, Repository, Manifest
Parser, and migration behavior. Only record construction, loaded-value reads,
Domain construction, conversion, and standard-library SHA-256 are used.

## 15. Files Added

- Five Mapper modules: identity, relationship, details, references, annotations.
- Complete remaining-Mapper test suite.
- Complete Mapper layer contract.
- This Run's Report and Manifest.

## 16. Files Modified

Mapper exports/common helpers; Task/Run/Repository/Context regression guards;
Bootstrap validator; Run Mapper historical handoff note; Context State,
Catalog, Issues, Roadmap, Handoff, Terminology, Database Index and JSON peers;
Current State/Handoff schemas only to admit exact next task `QM2-P0-002A2b`.
No Domain, ORM table, accepted ADR, dependency, lockfile, runtime configuration,
business module, or Factor Lab source changed.

## 17. Core Functions and Classes

The core additions are the eighteen new directional Mapper functions,
`changed_file_record_id`, `changed_symbol_record_id`, `safe_record_identity`,
`loaded_column`, and `validate_parent_run_id`. The eleven Domain constructors
and eleven existing ORM record types remain authoritative and unchanged.

## 18. Tests Executed

| Scope | Passed | Failed | Skipped | Not run |
| --- | ---: | ---: | ---: | ---: |
| Mapper-focused suite | 120 | 0 | 0 | 0 |
| Full relevant Domain/Repository/ORM/Mapper/Context suite | 323 | 0 | 0 | 0 |
| Mapper subtests in full suite | 247 | 0 | 0 | 0 |
| Context Bootstrap | 33 | 0 | 0 | 0 |
| Real PostgreSQL | 0 | 0 | 0 | 1 |

The first compatibility run exposed six expected stale scope guards and one
test used the valid `SymbolType.UNKNOWN` value as a negative case. The guards
were updated for the approved complete scope, the negative vector was corrected
to an unsupported value, and final runs passed. One initial zsh array invocation
passed all paths to `py_compile` as a single filename and failed before source
compilation; the corrected `xargs` invocation compiled all 13 files.

## 19. Expected vs Actual

| Requirement | Expected | Actual | Status |
| --- | --- | --- | --- |
| complete inventory | 11 bidirectional families | 22 exported conversions | passed |
| identities | frozen 9 vectors | exact recomputation | passed |
| reverse integrity | reject wrong technical ID | stable hard failure | passed |
| legality | official Domain constructors | used by every reverse Mapper | passed |
| round trip | Domain and ORM values | all explicit fields preserved | passed |
| drift | field/Enum/inventory guards | dedicated verification | passed |
| purity | no I/O or DB | source/AST guards | passed |

## 20. Implementation Run

Run `QM2-P0-002A2a2c2c-20260715T050423Z-30edead`; base commit
`30edead1d4b8eeece2be2978d6d42c94576122cc`; result commit null at artifact
generation; status `completed_uncommitted`; verification `targeted_tests`
(the full task-relevant suite, not the whole product suite).

## 21. Project Memory Updates

Current State, Component Catalog, Known Issues, Roadmap, Handoff, Terminology,
Database Schema Index, and machine peers now state that the Mapper stage is
complete and persistence/migration work is not. Exact handoff is A2b.

## 22. Known Limitations

No Manifest Parser/Indexer or logical-repository binding; no production
PostgreSQL Repository, Session/UoW, migration, schema/table, or real database
verification. Identity/Mapper versions are not persisted as ORM columns.
Artifact location retains the frozen Domain scheme-prefix contract.

## 23. Unresolved Questions

Migration invocation/order/checksum/rollback, schema privileges/search path,
isolated PostgreSQL fixture/CI capability, Repository conflict translation,
and durable Mapper/identity version binding remain for later bounded tasks.

## 24. Compatibility and Rollback

Task and Run public conversions remain compatible. New modules are additive
under Mapper Contract 1.0.0. Rollback is the single containing commit; no
database, migration, data, config, dependency, or Factor Lab rollback exists.

## 25. Scope Confirmation

Not implemented: PostgreSQL Repository; Session/Unit of Work; database schema
creation; migration execution; real PostgreSQL verification; Manifest
Parser/Indexer; repository identity resolver; Git consistency service; API/UI;
TDX; Dataset Snapshot; Factor DSL; Optimization; Validation runtime; Factor
Registry; LightGBM changes; Qlib changes.

## 26. Git State After

One commit is planned with `feat(qm2): complete ledger mapper layer`. The
Manifest records true pre-commit dirty state and null result commit. No amend,
push, dependency installation, lockfile change, or Factor Lab mutation occurs.

## 27. Recommended Next Task

Only `QM2-P0-002A2b — Ledger Migration and Isolated PostgreSQL Verification`.
The Mapper stage is complete.
