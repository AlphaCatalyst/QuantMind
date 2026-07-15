# Implementation Report: QM2-P0-002A2a2c2a

## 1. Task Result

Completed. Mapper foundation and ImplementationTask bidirectional conversion
are implemented; all 38 acceptance criteria pass. Generated Run status is
`completed_uncommitted`; work stopped before A2a2c2b.

## 2. Preflight State

Repository was clean on `master` at
`d128759188d4e255c6d58093bf59da78f722fe28`; unrelated dirty files: none.
Factor Lab was clean/read-only at
`c83192c2278767e03f008bc39197b1ba33bfb6a9`.

## 3. Context Read Confirmation

All required Project Memory, architecture, Domain/Repository/ORM/Mapper
contracts, ADR-0005/0007, previous Run, and real Domain/ORM source were read.
Domain construction remains semantic authority; Repository owns replay,
conflict, updates and transactions; Mapper is deterministic conversion.

## 4. Mapper Package Design

`mappers/` is under API persistence because it adapts Domain values to the
API-owned ORM shape; Domain remains persistence-independent. The package has
exactly errors, common conversions, and Task mapping. Explicit per-family
functions avoid a reflection mapper that could erase identity/invariant
boundaries. Only Task is implemented so the first real Mapper increment is
independently testable and reversible.

## 5. Mapper Error Model

- `LedgerMapperError`: stable safe metadata base.
- `RecordToDomainError`: expected stored-value/Domain reconstruction failure.
- `DomainToRecordError`: wrong Domain input or target-contract failure.
- `UnknownEnumValueError`: exact stored Enum mismatch, code `UNKNOWN_ENUM`.
- `InvalidMapperValueError`: common conversion shape/type failure.
- `MapperContractVersionError`: reserved unsupported contract version.

Errors include object type, optional safe identity/field, stable code, safe
message and underlying type. Expected `LedgerDomainError` is wrapped; import,
attribute and other programming defects are not swallowed. Full objective,
scope, non-goals, record repr, database URL and secret-like identity are absent.

## 6. Common Conversion Utilities

### Enum

`enum_to_storage` requires a string-valued Enum and returns `.value`.
`enum_from_storage` requires an exact string and constructs the requested Enum.
No arbitrary strings forward, trim, case repair, name persistence or fallback.

### Datetime

Both directions require aware datetime, normalize to UTC, preserve microseconds
and return datetime. Naive/non-datetime values fail; no timezone is guessed.

### JSON / Tuple

Domain tuple-of-string becomes a fresh list. Stored list/tuple-of-string becomes
a freshly allocated tuple. Order, duplicates and exact text are preserved;
invalid container/item shapes fail as `INVALID_JSON_SHAPE`.

## 7. ImplementationTask Domain-to-ORM

The function requires a real `ImplementationTask`, copies identifiers/text,
uses common conversions for scope/non-goals/status/time, creates a new
`ImplementationTaskRecord`, and sets `version=1`. It accepts no dict/duck type,
does not mutate Domain, query parent/current version, add/flush/commit, or reuse
a record instance.

## 8. ImplementationTask ORM-to-Domain

The function requires a real `ImplementationTaskRecord`, reads only already
loaded instance-state columns, validates positive non-bool version, converts
status/JSON/time, and calls the official `ImplementationTask(...)` constructor.
Missing/expired columns fail as `MISSING_REQUIRED_VALUE` rather than triggering
descriptor refresh. Domain failures are safely wrapped without rejected values.

## 9. Version Field Boundary

Version is ORM-only optimistic-concurrency state. Domain has no version.
Domain-to-new-record always uses 1; record-to-Domain validates version >=1 and
does not retain it. A version-9 record reconstructed then converted creates a
new version-1 record. This Mapper is not an existing-record update path. Future
Repository owns expected version, state transitions and record mutation.

## 10. Field Mapping Table

| Domain Field | ORM Column | Direction | Conversion | Notes |
| --- | --- | --- | --- | --- |
| task_id | task_id | both | exact | no generation |
| parent_task_id | parent_task_id | both | exact/None | Domain validates |
| title | title | both | pass-through | Mapper does not trim |
| objective | objective | both | pass-through | omitted from errors |
| scope | scope | both | tuple ↔ fresh list | ordered, duplicate-safe |
| explicit_non_goals | explicit_non_goals | both | tuple ↔ fresh list | ordered |
| status | status | both | Enum ↔ exact value | no fallback |
| created_at | created_at | both | aware UTC datetime | microseconds retained |
| none | version | ORM-only | validate/new value 1 | Repository update state |

## 11. Round-trip Semantics

Domain round trips compare equal with/without parent, non-UTC aware time and
duplicate scope. UTC normalization preserves instant/microseconds; lists return
to tuples. ORM value round trip preserves eight business fields. SQLAlchemy
instrumentation/object identity is irrelevant and version intentionally resets
to 1 for the new record.

## 12. Purity and Side-effect Boundary

AST/source guards exclude Engine, Session, Connection, SQL execution,
add/flush/refresh/commit/rollback, filesystem, Git, network, environment,
random IDs, upsert and merge. Stored columns are read without lazy descriptor
access. No database connection or service ran.

## 13. Files Added

- `mappers/{__init__,errors,common,task}.py`.
- `test_project_knowledge_ledger_task_mapper.py`.
- `LEDGER_TASK_MAPPER_V1.md`.
- This Run's Report and Manifest.

## 14. Files Modified

Repository/Context scope regressions, Context Bootstrap validator/test, and
allowed Current State, Component Catalog, Known Issues, Roadmap, Handoff,
Terminology, Database Schema Index plus machine peers. No Domain, ORM model,
Repository implementation, accepted ADR, dependency, lockfile or Factor Lab
source changed.

## 15. Core Functions and Classes

| File | Symbol | Responsibility | Future Consumer |
| --- | --- | --- | --- |
| errors.py | six safe errors | direction/value/version failures | all mappers |
| common.py | `MAPPER_CONTRACT_VERSION` | contract identity | Indexer/mappers |
| common.py | Enum functions | exact Enum/VARCHAR conversion | later mappers |
| common.py | datetime functions | aware UTC conversion | Run/relationship mappers |
| common.py | tuple/JSON functions | immutable/mutable copy | later JSON fields |
| task.py | `implementation_task_to_record` | new version-1 record | future Repository |
| task.py | `implementation_task_from_record` | validated Domain Task | query/API layer |

## 16. Boundary and Error Handling

Unknown/wrong-case/space Enum, malformed JSON, naive time, invalid/unloaded
version/column, non-Task, non-Record and Domain parent-ID failure are rejected.
Errors expose stable safe metadata only. Run, relationship, detail, reference,
annotation, identity and artifact-location mapping symbols are absent.

## 17. Tests Executed

| Scope | Passed | Failed | Skipped | Not run |
| --- | ---: | ---: | ---: | ---: |
| final Task Mapper suite | 25 | 0 | 0 | 0 |
| all 11 ORM mappings | 108 | 0 | 0 | 0 |
| Domain + Repository + Context | 155 | 0 | 0 | 0 |
| combined final unittest | 288 | 0 | 0 | 0 |
| Context Bootstrap | 31 | 0 | 0 | 0 |
| targeted py_compile | 7 | 0 | 0 | 0 |
| JSON parse before this Run | 27 | 0 | 0 | 0 |
| Manifest/report/artifact hashes | 3 | 0 | 0 | 0 |
| diff/scope guards | 3 | 0 | 0 | 0 |
| Factor Lab identity/status | 2 | 0 | 0 | 0 |
| real database | 0 | 0 | 0 | 1 |

Early evidence retained: first Task suite had 2 failures (fresh-tuple allocation
and a non-triggering safety fixture), both fixed; first broad regression had 1
failure because the prior exact-file guard had not authorized the four bounded
Mapper files, then was narrowly updated. During the final staging audit, one
launcher attempt failed before collection because `python` was unavailable, and
one system-Python attempt collected 157 tests but produced 2 import errors
(missing SQLAlchemy and an incorrect aggregate module name). Neither changed
files; the command was corrected to the existing SQLAlchemy-capable Python and
the exact test modules. The final 288-test rerun, Bootstrap and compile checks
all pass.

## 18. Expected vs Actual

| Requirement | Expected | Actual | Evidence | Status |
| --- | --- | --- | --- | --- |
| error foundation | stable/safe | six pure errors | tests/source | passed |
| common conversion | Enum/time/JSON | exact reusable functions | 25 tests | passed |
| Task directions | both | explicit functions | round trips | passed |
| Domain validation | mandatory | official constructor | failure tests | passed |
| version | new=1/stored positive | exact boundary | tests/doc | passed |
| purity | no I/O/DB | AST and loaded-state guard | tests | passed |
| scope | Task only | exact four-file package | Bootstrap | passed |
| regressions | all relevant | 288 tests | unittest | passed |
| Factor Lab | unchanged | clean expected HEAD | Git | passed |

## 19. Implementation Run

Run `QM2-P0-002A2a2c2a-20260715T040847Z-d128759`; base
`d128759188d4e255c6d58093bf59da78f722fe28`; pre-commit result null; status
`completed_uncommitted`; verification `targeted_tests`.

## 20. Project Memory Updates

Memory records Mapper foundation and Task conversion as implemented, all other
Mapper families/runtime persistence as absent, Task version boundary, and exact
human handoff to A2a2c2b. Machine task lists retain legal parent IDs.

## 21. Known Limitations

No Run/Relationship/detail/reference/annotation Mapper; no technical ID or
artifact location function; no Repository integration, Session/UoW, database,
migration, Indexer, API or UI. Existing-record version update path is absent.

## 22. Unresolved Questions

Run Mapper still needs explicit trusted logical repository identity input.
Repository error translation/update ownership, version persistence for Mapper
algorithms, and real PostgreSQL/pinned SQLAlchemy verification remain future.

## 23. Compatibility and Rollback

Additive Python/API-persistence code under Mapper contract 1.0.0. Rollback is
the containing Git commit. No database/data/migration/config rollback needed.

## 24. Scope Confirmation

Not implemented: ImplementationRun, RunRelationship, ChangedFile/Symbol ID,
Detail, Reference or Annotation mappers; Repository; Session/UoW; migration;
Parser/Indexer; API/UI; TDX; Dataset Snapshot; Factor DSL/Optimization/
Validation/Registry; LightGBM/Qlib changes.

## 25. Git State After

One commit will use `feat(qm2): implement ledger task mapper`. Manifest remains
truthfully pre-commit with null result commit. No push.

## 26. Recommended Next Task

Only `QM2-P0-002A2a2c2b — ImplementationRun Mapper`. It must independently
handle Run state/hash/time fields and explicit logical repository identity.
This task did not begin it.
