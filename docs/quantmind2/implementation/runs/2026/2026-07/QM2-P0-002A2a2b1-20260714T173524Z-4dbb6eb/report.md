# Implementation Report: QM2-P0-002A2a2b1

## 1. Task Result

- Result: completed.
- Generated status: `completed_uncommitted`; the immutable Run is generated
  before its containing commit, so `result_commit` is null.
- Completion level: complete.
- Acceptance: all 45 criteria passed; implementation stopped before A2a2b2.

## 2. Preflight State

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`.
- Branch: `master`; base `4dbb6eb4aa5a3c9f22d8a590cb6c9539f411330a`.
- QuantMind dirty before: no; unrelated dirty files: none.
- Factor Lab: clean/read-only at
  `c83192c2278767e03f008bc39197b1ba33bfb6a9`.
- No reset, stash, clean, amend, rebase, install, lockfile change, database
  access, credential access, or push occurred.

## 3. Context Read Confirmation

The mandated documents were read in order, including A1b1 Domain, A1b2
Repository, A2a1 core ORM, A2a2a detail ORM, ADR-0005/0007, and the complete
A2a2a Run. Domain remains semantic authority; Repository remains identity,
replay, conflict, append-only, and behavior authority; ORM is static shape.

## 4. ORM Boundary Confirmation

Both records use `backend.services.api.models.base.Base` and explicit schema
`quantmind2`. They register on the same metadata as the existing seven Ledger
records. There is no new Base, Engine, Session, relationship collection,
runtime DDL, database operation, Mapper, Repository, or migration.

## 5. Composite Key Decision

Neither domain object has a reference ID. The primary keys are exactly A1b2's
natural identities: Run/component and Run/ADR. This lets a Repository locate
exact replay without inventing a technical ID. Impact and relation are
immutable content; adding them to identity would incorrectly turn a conflict
into a second record. No technical ID, natural-key UQ duplicate, sequence,
UUID, or autoincrement is present.

## 6. ComponentReference ORM

`quantmind2.implementation_component_references` contains three non-null
columns: Run ID and component ID as `VARCHAR(255)`, plus impact as
`VARCHAR(32)`. `pk_qm2_component_refs(run, component)` is the composite primary
key. The only FK targets the schema-qualified Run primary key with RESTRICT.
Checks reject blank component IDs and values outside domain `ImpactType`.

Indexes cover component, impact, and component/impact for cross-Run queries.
No separate Run index is added because the primary key already has Run as its
leading column; no index duplicates the complete primary key.

## 7. ArchitectureDecisionReference ORM

`quantmind2.implementation_adr_references` contains three non-null columns:
Run ID `VARCHAR(255)`, ADR ID `VARCHAR(32)`, and relation `VARCHAR(32)`.
`pk_qm2_adr_refs(run, adr)` is the composite primary key. The only FK targets
Run with RESTRICT. A PostgreSQL regex enforces `^ADR-[0-9]{4}$`; relation is
checked from domain `ADRReferenceRelation`.

Indexes cover ADR, relation, and ADR/relation. The Run-leading primary key
already supports Run-scoped queries, so it is not duplicated.

## 8. Constraints and Indexes

| Table | Constraint / index | Purpose | Domain / Repository rule |
| --- | --- | --- | --- |
| component refs | `pk_qm2_component_refs` | natural identity | Run + component |
| component refs | `fk_qm2_component_refs_run` | parent existence floor | Run parent, RESTRICT |
| component refs | two `ck_qm2_component_refs_*` | nonblank ID and impact values | Domain validity subset |
| component refs | three `ix_qm2_component_refs_*` | cross-Run component/impact queries | A1b2 filtering |
| ADR refs | `pk_qm2_adr_refs` | natural identity | Run + ADR |
| ADR refs | `fk_qm2_adr_refs_run` | parent existence floor | Run parent, RESTRICT |
| ADR refs | two `ck_qm2_adr_refs_*` | ADR format and relation values | Domain validity subset |
| ADR refs | three `ix_qm2_adr_refs_*` | cross-Run ADR/relation queries | A1b2 filtering |

All constraint/index names are explicit, globally unique in shared metadata,
kind-prefixed, and no longer than 63 characters.

## 9. Fact-source Boundary

Component Catalog is a Git/Project Memory-derived catalog, and ADR Index is a
Git-derived index of accepted documents. Neither has a stable authoritative
database entity table. Therefore component and ADR IDs receive no external FK.
Only parent Run has an FK. PostgreSQL remains a rebuildable query projection;
Git code, ADR documents, Reports, and Manifests remain authoritative.

## 10. Enum Drift Protection

`orm_types` minimally adds value tuples derived directly from A1b1
`ImpactType` and `ADRReferenceRelation`. `enum_check_sql` creates the CHECK
expressions. Tests compare both exported tuples and actual constraint SQL to
the domain Enums. No handwritten duplicate list or PostgreSQL native Enum is
used.

## 11. Repository Contract Alignment

A1b2 exact replay remains `same primary identity + equal frozen object →
existing object`. Different impact/relation at the same primary identity is an
immutable conflict. Append-only and no-overwrite behavior remain Repository
authorization. ORM defines no upsert, merge, `ON CONFLICT DO UPDATE`, update,
delete, or conflict translation. Direct privileged SQL UPDATE is not prevented
by static metadata and will require future role governance.

## 12. PostgreSQL DDL Compilation

Static tests use an existing environment at
`/Users/yj/Documents/Codex/2026-06-30/nih/work/QuantMind/.venv/bin/python` with
SQLAlchemy 2.0.51; production requirements pin 2.0.25. `CreateTable` and
`CreateIndex` compile through `postgresql.dialect()` only. AST/source tests
exclude Engine, Session, execute, commit, rollback, `create_all`, `drop_all`,
Mapper, and upsert behavior.

Compilation confirms schema, composite PKs, Run FK RESTRICT, regex/enum checks,
indexes, and absence of cascade, trigger, external entity FK, URL, or secret.
It does not prove pinned-version output, schema privileges, server execution,
transactions, concurrency, migration ordering, or performance.

## 13. Files Added

- `backend/services/api/project_knowledge/persistence/orm_reference_models.py`:
  two static mappings.
- `backend/services/tests/test_project_knowledge_ledger_reference_orm.py`:
  bounded reference ORM/DDL tests.
- `docs/quantmind2/implementation/LEDGER_REFERENCE_ORM_MAPPING_V1.md`:
  21-section contract.
- This Run's adjacent Report and Manifest.

## 14. Files Modified

- Persistence package exports and two domain-derived enum constants.
- Core/detail/Repository scope regressions to allow exactly one reference module.
- Context Bootstrap validator and Context unittest for the contract/source and
  exact A2a2b2 handoff.
- Human and machine Current State, Handoff, Component Catalog, Known Issues,
  Roadmap, Terminology, and Database Schema Index. No accepted ADR changed.

## 15. Core Classes and Symbols

| File | Symbol | Responsibility | Future consumer |
| --- | --- | --- | --- |
| `orm_reference_models.py` | `ComponentReferenceRecord` | component reference shape | mapper/migration/Repository |
| `orm_reference_models.py` | `ArchitectureDecisionReferenceRecord` | ADR reference shape | mapper/migration/Repository |
| `orm_types.py` | `IMPACT_TYPE_VALUES` | persisted impact values | checks/tests/migration |
| `orm_types.py` | `ADR_REFERENCE_RELATION_VALUES` | persisted ADR relation values | checks/tests/migration |
| validator | reference contract/source checks | prevent state and scope drift | future Codex tasks |

## 16. Runtime / Registration Flow

```text
API Base
→ Core Ledger ORM
→ Detail ORM
→ Reference ORM
→ Shared Metadata with nine quantmind2 targets
→ Future Migration
```

The future migration step does not exist. No database runtime was started.

## 17. Boundary and Edge-case Handling

- Same Run/component with another impact remains immutable conflict.
- Same Run/ADR with another relation remains immutable conflict.
- Missing Component Catalog or ADR document does not invalidate static DB
  shape; a future Indexer/Application Service must report source inconsistency.
- Database does not validate ADR acceptance, actual file modification, or
  business approval semantics.
- No Mapper, migration, schema/table, Repository, Session, Indexer, API, or UI.

## 18. Tests Executed

| Command | Purpose | Passed | Failed | Skipped | Not run | Key output |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| external Python `-m unittest reference_orm detail_orm core_orm` | reference mapping and prior ORM regression | 86 | 0 | 0 | 0 | 20 reference + 32 detail + 34 core |
| system Python `-m unittest domain repository_contract context_bootstrap` | A1b1/A1b2/Context regression | 154 | 0 | 0 | 0 | OK |
| `python3 tools/quantmind2/validate_context_bootstrap.py` | context/contracts/scope/runs | 25 | 0 | 0 | 0 | passed, 25 checks |
| external Python `-m py_compile` on 8 files | targeted syntax | 8 | 0 | 0 | 0 | no output |
| JSON parse over `docs/quantmind2` | machine documents before new Run | 23 | 0 | 0 | 0 | parsed_json=23 |
| actual Manifest schema/report/payload hashes | immutable Run contract | 3 | 0 | 0 | 0 | passed after generation |
| diff/dependency/migration/business scope guards | whitespace and scope | 3 | 0 | 0 | 0 | clean |
| Factor Lab HEAD/status | read-only donor | 2 | 0 | 0 | 0 | expected HEAD, clean |
| real PostgreSQL | prohibited/deferred | 0 | 0 | 0 | 1 | not run |

No service, database, Electron, TDX, Qlib, LightGBM, or Factor Lab Campaign ran.

## 19. Expected vs Actual

| Requirement | Expected | Actual | Evidence | Status |
| --- | --- | --- | --- | --- |
| scope | exactly two tables | component + ADR only | metadata tests | passed |
| identity | natural composite PKs | exact A1b2 keys | PK tests | passed |
| no technical IDs | none | three columns/table only | column tests | passed |
| parent FK | Run only, RESTRICT | one FK/table | FK/DDL tests | passed |
| no entity FK | none | none | FK count/DDL | passed |
| checks | ID/format/enums | exact named checks | constraint tests | passed |
| indexes | useful, nonduplicate | three/table | index tests | passed |
| enum drift | domain-derived | tuples and SQL compared | enum tests | passed |
| no relationship/upsert | absent | absent | mapper/source tests | passed |
| DDL | static compile only | PostgreSQL strings | DDL tests | passed |
| regressions | all prior contracts | 240 ORM/domain/repo/context tests | commands | passed |
| Project Memory | truthful partial state | nine metadata targets | Bootstrap | passed |
| Factor Lab | unchanged | clean expected HEAD | Git | passed |

## 20. Implementation Run

- Run ID: `QM2-P0-002A2a2b1-20260714T173524Z-4dbb6eb`.
- Report: this file; Manifest: adjacent `manifest.json`.
- Base commit: `4dbb6eb4aa5a3c9f22d8a590cb6c9539f411330a`.
- Result commit: null in the immutable pre-commit Manifest.
- Generated status: `completed_uncommitted`.
- Verification: targeted tests and dialect-only PostgreSQL DDL compilation.

## 21. Project Memory Updates

Project Memory now records nine static ORM targets, implemented Component/ADR
reference mappings, absent annotation mappings and all undeployed runtime
layers, and exact human handoff to A2a2b2. Machine recommended-task fields keep
their legal parent values because schema v1 cannot encode the fine-grained ID.

## 22. Known Limitations

- Limitation and RecommendedTask ORM mappings remain absent.
- No Mapper, migration, real PostgreSQL, Repository connection, Session/UoW,
  Indexer, Git consistency service, API, or UI exists.
- Component and ADR truth/membership are not database-validated.
- Static compilation used SQLAlchemy 2.0.51, not production-pinned 2.0.25.
- ORM metadata alone cannot enforce append authorization or replay equality.

## 23. Unresolved Questions

- How should a future Indexer surface a reference to a missing Catalog entry or
  ADR document without making PostgreSQL authoritative?
- How will the future Repository translate a composite-key uniqueness failure
  into exact replay versus immutable conflict without an unsafe upsert?
- How will pinned SQLAlchemy and isolated PostgreSQL verification be supplied?

## 24. Compatibility and Rollback

The additive metadata requires SQLAlchemy 2.x/PostgreSQL dialect semantics.
Rollback is the single containing Git commit. No database or data rollback is
needed because no migration or DDL executed. Future consumers must preserve
the composite natural identities unless a later accepted contract supersedes
them.

## 25. Scope Confirmation

Not implemented: Limitation ORM, RecommendedTask ORM, Domain mappers,
PostgreSQL Repository, schema creation, migration, Session, Unit of Work,
Manifest Parser/Indexer, Git consistency, API, UI, TDX, Dataset Snapshot,
Factor DSL, Optimization, Validation runtime, Factor Registry, LightGBM
changes, or Qlib changes. A2a2b2 was not started.

## 26. Git State After

The task will create one commit named `feat(qm2): map ledger reference ORM
models`. The immutable Manifest remains pre-commit with null result commit.
Final checks must show QuantMind and Factor Lab clean and no push.

## 27. Recommended Next Task

Only `QM2-P0-002A2a2b2 — Ledger Limitation and Recommended Task ORM Mapping`
is recommended. It must be independent because its ID, severity/status,
priority/reason, nullable component, and indexing semantics require their own
bounded review. It was not started here.
