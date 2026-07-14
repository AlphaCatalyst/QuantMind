# Implementation Report: QM2-P0-002A2a1

## 1. Task Summary

`QM2-P0-002A2a1 — Core Implementation Ledger ORM Mapping` implements only
SQLAlchemy persistence shapes for ImplementationTask, ImplementationRun, and
RunRelationship. It registers three schema-qualified tables on the selected API
Base and verifies PostgreSQL DDL by dialect compilation without a database.

## 2. Goal

Prove that the A1b1 core domain fields and the database-expressible part of the
A1b2 identity/version/relationship contract can be represented as stable
PostgreSQL metadata without implementing persistence execution.

## 3. Scope

- API-side Project Knowledge persistence package.
- Three ORM records and only three `quantmind2` table mappings.
- Domain-derived VARCHAR enum checks, keys, checks, indexes, and version columns.
- PostgreSQL-only JSONB and dialect DDL compilation.
- ORM contract document, targeted tests, Context validator adaptation, Project
  Memory updates, and one immutable Implementation Run.

## 4. Explicit Non-goals

No detail ORM tables, domain mappers, production Repository, Unit of Work,
Session, transaction orchestration, database connection, credentials, migration,
`CREATE SCHEMA`, executed DDL, `metadata.create_all`, Manifest Parser/Indexer,
Git consistency service, API, UI, TDX, Dataset Snapshot, DSL, Optimization,
Validation runtime, Registry, LightGBM change, Qlib change, or Factor Lab change.

## 5. Preflight State

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`
- Base: `6a624a1dbaa8ba02073f3a5fc5b41805fc7481f0`
- Dirty before: no
- Unrelated dirty files: none
- Factor Lab: clean and read-only at
  `c83192c2278767e03f008bc39197b1ba33bfb6a9`.

All mandatory context, persistence audit, A1b1/A1b2 contracts, ADRs, and prior
Reports/Manifests were read. The requested ADR-0009 description was resolved to
the indexed filename `ADR-0009-decision-control-execution-separation.md`.

## 6. Existing ORM Convention Review

`backend/services/api/models/base.py` exposes legacy `declarative_base()` and
is already used by API user/community models. The repository mixes legacy
`Column` and SQLAlchemy 2 typed mappings; it also has multiple unrelated Bases.
A1a selected the API Base for Project Knowledge, so this task imports that exact
object and creates no second Base. Production requirements pin SQLAlchemy
2.0.25. The system `python3` has no SQLAlchemy; an already-installed, read-only
QuantMind virtual environment supplied 2.0.51 for static tests. No package or
lockfile was changed.

Existing naming is inconsistent, so this bounded package uses explicit stable
names for every PK/FK/UQ/check/index. Time columns use
`DateTime(timezone=True)`. JSON arrays use PostgreSQL JSONB. No model registry
automatically imports all API models; importing this package is the explicit
future registration boundary.

## 7. ORM Package Placement

Models live under
`backend/services/api/project_knowledge/persistence/`. This matches the A1a
API control-plane ownership while keeping framework persistence out of the pure
domain package. `persistence.__init__` exports the three records. A thin module
under `api/models` is unnecessary because the selected Base is imported
directly and tests/future migration code can explicitly import the package.

## 8. Persistence Design Decisions

- Base: existing `backend.services.api.models.base.Base`.
- Schema: explicit `quantmind2` on all tables; no `search_path` dependency.
- Enum: `VARCHAR(32)` plus named CHECK derived from A1b1 Enum values.
- IDs: `VARCHAR(255)`, matching the domain maximum rather than the shorter
  task suggestion.
- Git/SHA: `CHAR(40)` commits and nullable `CHAR(64)` SHA-256 values with hex
  checks.
- Delete: explicit `ON DELETE RESTRICT`; no cascade or soft delete.
- Naming: explicit globally unique names at most 63 characters.
- Relationships: not configured; table structure is the task focus and avoiding
  ORM collections prevents implied domain ownership/cascade behavior.

## 9. ORM Models

### ImplementationTaskRecord

Nine columns map Task fields plus persistence version. `task_id` is the named
primary key; `parent_task_id` is a nullable, restrictive, schema-qualified self
FK. Title/objective are non-null TEXT and checked after `btrim`. Scope and
non-goals are non-null JSONB checked as arrays. Status is enum-checked.
`created_at` is timestamptz. Version is non-null, positive, server-default 1.

### ImplementationRunRecord

Twenty-four columns map every A1b1 Run field plus version. The named primary
key is `implementation_run_id`; `task_id` has a restrictive FK. Required text,
flags, enum states, timestamptz values, commit/hash fields, Manifest/Report
paths, and version have explicit types/nullability. Checks cover enum values,
hex format, time order and presence, committed/uncommitted result rules,
completed/partial levels, canonical gating, failure-state exclusion, and
positive version. No event changes state or promotes canonical status.

### RunRelationshipRecord

Six columns map identity, source, target, type, reason, and creation time.
Source/target are restrictive schema-qualified FKs. Checks reject self-links,
unsupported types, and blank reasons. The natural tuple `(source, target,
type)` is uniquely constrained. No cycle trigger is defined.

## 10. Constraints and Indexes

| Table | Constraint/index groups | Purpose | Domain rule represented |
| --- | --- | --- | --- |
| tasks | named PK, parent FK, 7 checks, 3 indexes | identity, parent, status/text/JSON/version, lookup | basic Task validity and storage version |
| runs | named PK, Task FK, 20 checks, 7 indexes | identity, enum/format/state gates, common queries | database-expressible Run combinations |
| relationships | named PK, 2 Run FKs, UQ, 3 checks, 5 indexes | immutable edge shape and traversal lookup | no self-edge and natural-key uniqueness |

All 53 constraint/index names are explicit, globally unique, type-prefixed, and
within PostgreSQL's identifier limit. All four FKs compile with RESTRICT.

## 11. Domain-to-ORM Boundary

Domain objects remain immutable semantic values. ORM records are mutable row
shapes and are not returned as domain truth. Path traversal checks, secret-like
rejection, UTC normalization, Git object/hash verification, state-transition
authorization, exact replay, content conflicts, DAG cycles, and atomic batches
remain in Domain/Repository/future services. Version columns support a future
adapter but do not implement compare-and-swap alone.

## 12. Enum Drift Protection

`orm_types.enum_values()` reads values directly from each domain Enum;
`enum_check_sql()` creates the CHECK expression. Exported value tuples and the
actual table CHECK SQL are both compared with all seven relevant Enums in
tests. VARCHAR plus CHECK was retained because it is easier to evolve through
versioned SQL than native PostgreSQL Enum and the repository has no native-enum
governance.

## 13. PostgreSQL DDL Compilation

Tests use `CreateTable(table).compile(dialect=postgresql.dialect())` and
`CreateIndex` for every index. Key compiled evidence includes:

```text
CREATE TABLE quantmind2.implementation_tasks (... scope JSONB NOT NULL ...)
CREATE TABLE quantmind2.implementation_runs (... TIMESTAMP WITH TIME ZONE ...)
CREATE TABLE quantmind2.implementation_run_relationships (...)
FOREIGN KEY (...) REFERENCES quantmind2... ON DELETE RESTRICT
```

The compile path constructs strings only. It uses no Engine, Connection,
Session, URL, credentials, execute, commit, rollback, `create_all`, or DDL
runner. SQLAlchemy 2.0.51 emitted expected schema qualification, JSONB,
timestamptz, named checks, and RESTRICT clauses; pinned 2.0.25 and a real
PostgreSQL server were not available in this checkout and remain unverified.

## 14. Files Added

- `backend/services/api/project_knowledge/__init__.py`: API-side boundary.
- `backend/services/api/project_knowledge/persistence/__init__.py`: record exports.
- `backend/services/api/project_knowledge/persistence/orm_types.py`: lengths,
  domain enum values, and CHECK helper.
- `backend/services/api/project_knowledge/persistence/orm_models.py`: three mappings.
- `backend/services/tests/test_project_knowledge_ledger_core_orm.py`: static contract suite.
- `docs/quantmind2/implementation/LEDGER_CORE_ORM_MAPPING_V1.md`: 23-section contract.
- This Run's `report.md` and `manifest.json`.

## 15. Files Modified

Context Current State, Component Catalog, Known Issues, Roadmap, Handoff,
Terminology, Database Schema Index, five machine-readable context files, the
Context unittest, and the bounded Context Bootstrap validator were updated to
recognize the exact A2a1 boundary without claiming database deployment.

## 16. Core Classes and Symbols

| File | Symbol | Responsibility | Future consumer |
| --- | --- | --- | --- |
| `orm_models.py` | `ImplementationTaskRecord` | Task row/table shape | mapper/migration/Repository |
| `orm_models.py` | `ImplementationRunRecord` | Run row/table shape | mapper/migration/Repository |
| `orm_models.py` | `RunRelationshipRecord` | edge row/table shape | mapper/migration/Repository |
| `orm_types.py` | `enum_values` | authoritative Enum value extraction | checks/tests/migration |
| `orm_types.py` | `enum_check_sql` | stable VARCHAR CHECK expression | ORM metadata |

## 17. Runtime / Registration Flow

```text
API Declarative Base
→ explicit import of Project Knowledge persistence package
→ Base.metadata contains three quantmind2 core table targets
→ future migration may consume the mapping contract
```

No database runtime starts in this flow. There is no automatic application-main
import, schema creation, engine, session, or migration invocation.

## 18. Boundary and Edge-case Handling

- Multiple-Base risk is controlled by importing the selected API Base exactly.
- Model registration is explicit and side-effect-free apart from metadata.
- IDs use 255 rather than the suggested 128 to avoid narrowing domain values.
- JSON arrays use PostgreSQL JSONB and are intentionally not SQLite-compatible.
- All names are checked globally for uniqueness and the 63-character limit.
- No relationship loading/cascade is configured.
- No recursive cycle trigger is claimed; A1b2 DFS remains test-double contract
  evidence only.
- Existing SQLAlchemy 2.0.51 static verification is not represented as pinned
  production or live PostgreSQL verification.

## 19. Tests Executed and Results

Final acceptance verification records:

- Core ORM static suite: 34 passed.
- A1b1 domain regression: 76 passed.
- A1b2 Repository contract regression: 60 passed.
- Context regression: 18 passed.
- Context Bootstrap: 21 named checks passed.
- Python compilation/import, all QuantMind 2.0 JSON parse, actual Manifest
  schema/hash checks, forbidden-scope checks, DDL compilation, Git diff checks,
  and Factor Lab read-only checks passed.
- No database, service, Electron, Factor Lab campaign, LightGBM, Qlib, or
  unrelated suite was run.

## 20. Expected vs Actual

| Requirement | Expected | Actual | Evidence | Status |
| --- | --- | --- | --- | --- |
| selected Base | API Base only | exact Base metadata | identity tests | passed |
| three tables | Task/Run/Relationship only | exact three registered | metadata tests | passed |
| schema | explicit quantmind2 | all table schemas exact | metadata/DDL | passed |
| constraints/indexes | named and bounded | all explicit/unique/<=63 | naming tests | passed |
| enums | VARCHAR + CHECK aligned | seven domain-derived checks | drift tests | passed |
| state gates | minimum DB-expressible rules | time/result/level/canonical checks | SQL/metadata tests | passed |
| deletion | RESTRICT, no cascade | four restrictive FKs | DDL tests | passed |
| DDL | compile, never execute | PostgreSQL dialect strings only | static suite | passed |
| regression | A1b1/A1b2/Context clean | all targeted suites clean | final commands | passed |
| no expansion | no details/mapper/repo/session/migration/API | absent | scope checks/diff | passed |
| production DB | must not be claimed | not connected or verified | source/tests | passed |

## 21. Implementation Run

- Run ID: `QM2-P0-002A2a1-20260714T161550Z-6a624a1`
- Base commit: `6a624a1dbaa8ba02073f3a5fc5b41805fc7481f0`
- Result commit: null in the immutable Manifest because the containing commit
  cannot self-reference.
- Generated status: `completed_uncommitted`.
- Verification: targeted tests plus static PostgreSQL DDL compilation.

## 22. Project Memory Updates

Project Memory now distinguishes implemented core ORM metadata from absent
detail mapping, mappers, migration, deployed schema/tables, PostgreSQL
integration, production Repository, Session/UoW, API, and UI. It records the
only next task as A2a2 and retains legal parent `QM2-P0-002` in machine next-task
fields constrained by context schema v1.

## 23. Known Limitations and Unresolved Questions

- Detail tables and Domain/ORM mappers are absent.
- No migration, schema creation, live PostgreSQL, Repository adapter, UoW, or
  transaction code exists.
- Version columns do not implement locking or compare-and-swap alone.
- No database cycle prevention or race handling exists.
- Exact replay, identity/content conflicts, transitions, and atomic batch need
  Repository/Application behavior beyond ORM metadata.
- Static compilation used SQLAlchemy 2.0.51, not the production-pinned 2.0.25.
- Which relationship types may coexist for one source/target pair and how
  concurrent DAG admission will be enforced remain unresolved.

## 24. Compatibility and Rollback

The change is additive and targets SQLAlchemy 2.x/PostgreSQL. JSONB and regex
checks are intentionally PostgreSQL-specific and SQLite is not a valid
integration substitute. Rollback is the single containing Git commit; no
database or data rollback exists because nothing was deployed or executed.

## 25. Scope Confirmation

This task did not implement detail ORM tables, domain mappers, PostgreSQL
Repository, database schema creation, migration, Session, Unit of Work,
transaction code, Manifest Parser/Indexer, Git consistency, API, UI, TDX,
Dataset Snapshot, DSL, Optimization, Validation runtime, Factor Registry,
LightGBM changes, Qlib changes, or Factor Lab changes.

## 26. Recommended Next Task

The only recommendation is `QM2-P0-002A2a2 — Ledger Detail ORM Mapping and
Domain Mappers`. It must be independent because child identities/conversion
semantics require their own bounded review and must not imply migration or
production persistence. A2a2 was not started here.
