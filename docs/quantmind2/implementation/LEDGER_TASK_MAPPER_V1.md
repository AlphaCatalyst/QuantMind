# Ledger ImplementationTask Mapper v1

## 1. Scope

QM2-P0-002A2a2c2a implements the common Mapper error/value foundation and only
the bidirectional ImplementationTask/ImplementationTaskRecord mapper. It adds
no Run, relationship, detail, reference, annotation, identity, Repository,
Session/UoW, migration, database, Parser/Indexer, API, or UI behavior.

## 2. Mapper Contract Version

`MAPPER_CONTRACT_VERSION = "1.0.0"`, conforming to
`LEDGER_DOMAIN_ORM_MAPPER_CONTRACT_V1.md`. The version is not stored in ORM;
future Indexer is responsible for recording it.

## 3. Domain / Mapper / ORM Boundary

Domain constructors remain semantic authority, ORM remains persistence shape,
and Repository remains replay/conflict/transaction/update authority. Mapper
converts values and calls the official `ImplementationTask` constructor. It
does not repair a record, query a parent, or return ORM objects as API models.

## 4. Package Layout

The API-owned persistence package contains exactly `mappers/__init__.py`,
`errors.py`, `common.py`, and `task.py`. This boundary belongs beside ORM
because it adapts persistence values. It is not placed in the persistence-free
Domain. Explicit per-family functions are used instead of reflection so each
identity and invariant boundary remains reviewable. Only Task is implemented
because this increment has one independently testable target.

## 5. Mapper Error Model

`LedgerMapperError` exposes stable code, object type, safe identity, field,
safe message, and optional underlying error type. `RecordToDomainError` and
`DomainToRecordError` mark direction. `UnknownEnumValueError` uses
`UNKNOWN_ENUM`; `InvalidMapperValueError` handles common value shape;
`MapperContractVersionError` reserves unsupported-version failure.

Errors are pure Python and independent of SQLAlchemy exceptions, FastAPI, and
HTTP. Expected stored/data conversion and Domain validation failures are
wrapped. Attribute/import/programming errors are not swallowed. Messages never
include full ORM repr, objective, scope, non-goals, database URL, or secret.

## 6. Enum Conversion

`enum_to_storage` accepts only a string-valued Enum instance and returns exact
`enum.value`; arbitrary string is rejected. `enum_from_storage` accepts only an
exact string and constructs the requested Enum. No trim, case conversion,
Enum-name persistence, or fallback occurs. Task uses
`ImplementationTaskStatus`; common functions are reusable by later explicit
mappers.

## 7. Datetime Conversion

`datetime_to_storage` and `datetime_from_storage` require timezone-aware
datetime, normalize to UTC with `astimezone(timezone.utc)`, and preserve
microseconds. They return datetime, never text. Naive/non-datetime values fail;
no local timezone is guessed or attached.

## 8. JSON and Tuple Conversion

`string_tuple_to_json_array` accepts only tuple-of-string and creates a fresh
list. `json_array_to_string_tuple` accepts only list/tuple-of-string and creates
a fresh tuple even when input is already tuple. Both preserve order,
duplicates, and exact strings without sort/dedup/trim. Invalid containers or
items fail with `INVALID_JSON_SHAPE`.

## 9. Domain-to-ORM Mapping

`implementation_task_to_record` requires a real `ImplementationTask`, copies
IDs/text, converts tuple fields to fresh lists, persists status value,
normalizes `created_at` to UTC, and creates a new `ImplementationTaskRecord`
with `version=1`. It accepts no dict/duck type, mutates no Domain value, and
performs no add/flush/query/commit.

## 10. ORM-to-Domain Mapping

`implementation_task_from_record` requires a real
`ImplementationTaskRecord`, derives only a safe task identity for diagnostics,
validates positive integer version, converts status/JSON/time, and invokes
`ImplementationTask(...)`. Mapper conversion errors pass through; expected
`LedgerDomainError` is safely wrapped as `RecordToDomainError` with the Domain
error code/type but without rejected content. Columns are read from already
loaded instance state; a missing/expired value fails as `MISSING_REQUIRED_VALUE`
instead of invoking a descriptor refresh or lazy database load.

## 11. Version Field Boundary

`version` is ORM-only optimistic-concurrency state and is absent from Domain.
New Domain-to-record conversion always creates version 1. ORM-to-Domain
requires a non-bool positive integer and otherwise ignores it. Mapping is not
an update API: an existing version 9 record round-trips through Domain to a new
version 1 record. Future Repository owns expected version, state update, and
existing-record mutation; no `apply`, `update`, `merge`, or overwrite exists.

## 12. Field Mapping Table

| Domain Field | ORM Column | Direction | Conversion | Notes |
| --- | --- | --- | --- | --- |
| task_id | task_id | both | exact copy | never regenerated |
| parent_task_id | parent_task_id | both | exact copy/None | Domain validates parent differs |
| title | title | both | pass to Domain | Mapper does not trim |
| objective | objective | both | pass to Domain | safe errors omit value |
| scope | scope | both | tuple ↔ fresh list | order/duplicates retained |
| explicit_non_goals | explicit_non_goals | both | tuple ↔ fresh list | order/duplicates retained |
| status | status | both | Enum ↔ exact value | no fallback/case repair |
| created_at | created_at | both | aware datetime → UTC | microseconds retained |
| none | version | record-only | positive int check/new value 1 | not in Domain equality |

## 13. Round-trip Semantics

Domain → record → Domain equals the original for Tasks with/without parent,
non-UTC aware time, and duplicate scope items. UTC normalization preserves the
same instant and microseconds; list returns to tuple. Record → Domain → new
record preserves all business fields. SQLAlchemy instrumentation/object
identity is irrelevant, and an original version other than 1 intentionally
resets to 1 because this creates a new record rather than updating one.

## 14. Error Safety

Normal valid task IDs may be diagnostic identities. Malformed or secret-like
IDs are withheld. Errors contain stable codes and bounded metadata only.
Unknown Enum, malformed JSON, naive datetime, invalid version, wrong input
type, and Domain constructor failures are tested without full value/record
disclosure.

## 15. Purity and Side-effect Boundary

Source guards exclude Engine, Session, Connection, database operations,
filesystem/Git/network/environment/random access, logging of input, parent
lookup, state transition, upsert, merge, and global mutable state. Allowed
operations are new ORM instance construction, loaded-column reads, common pure
conversion, and official Domain construction. No database was connected.

## 16. Deferred Run Mapper

ImplementationRun mapping, logical repository identity input, commit/hash/time
and state combinations remain QM2-P0-002A2a2c2b. No `run.py` or Run conversion
symbol exists here.

## 17. Deferred Relationship Mapper

RunRelationship conversion and graph/reason semantics remain a later bounded
task. No `relationships.py` or relationship conversion symbol exists.

## 18. Deferred Detail Mappers

ChangedFile/Symbol technical identity functions and all detail/reference/
annotation/artifact-location conversions remain deferred. There is no
`identity.py`, `details.py`, `references.py`, or `annotations.py`.

## 19. Deferred Repository and Migration

Replay, conflict, parent existence, optimistic updates, transactions, Session,
UoW, row locking, database error translation, schema/table creation, migration,
and Indexer are not Mapper responsibilities and are not implemented.

## 20. Handoff to QM2-P0-002A2a2c2b

The only recommended next task is `QM2-P0-002A2a2c2b — ImplementationRun
Mapper`. It must reuse these safe errors/common conversions and independently
resolve explicit logical repository identity input. This task did not begin it.
