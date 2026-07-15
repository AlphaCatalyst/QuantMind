# Ledger Complete Mapper Layer v1

## 1. Scope

This contract closes `QM2-P0-002A2a2c2c`. It covers deterministic, in-memory conversion between the eleven frozen Implementation Ledger Domain objects and their SQLAlchemy record shapes. It does not provide persistence behavior.

## 2. Completed Mapper Inventory

The complete inventory is `ImplementationTask`, `ImplementationRun`, `RunRelationship`, `ChangedFile`, `ChangedSymbol`, `TestExecution`, `ImplementationArtifact`, `ComponentReference`, `ArchitectureDecisionReference`, `Limitation`, and `RecommendedTask`. Every object has an explicit `to_record` and `from_record` function.

## 3. Package Layout

`task.py` and `run.py` retain their existing contracts. `relationship.py`, `details.py`, `references.py`, and `annotations.py` contain the remaining explicit conversions. `identity.py` contains only the two frozen technical-ID algorithms. `common.py` contains bounded value and loaded-column helpers.

## 4. Domain / Mapper / ORM Boundary

Domain constructors remain the authority for object legality. Mappers translate explicit fields and surface safe conversion errors. ORM classes define persistence shape only. Repository identity, replay, conflict, graph, append-only, and transaction semantics remain outside this layer.

## 5. Parent Run Context

Detail, reference, and annotation `to_record` functions accept an explicit parent Run ID. Current Domain objects also contain `implementation_run_id`; the Mapper validates that both values are legal and equal. No global current-Run state, inference, repository lookup, or execution path is accepted.

## 6. Stable Technical IDs

`ChangedFileRecord.changed_file_id` is `cf_` plus lowercase SHA-256 of the NFC/UTF-8/LF payload `changed-file-v1`, Run ID, repository-relative path, and exact `FileChangeType.value`. `ChangedSymbolRecord.changed_symbol_id` is `cs_` plus SHA-256 of `changed-symbol-v1`, Run ID, file path, and qualified name. There is no trailing LF or case folding. Stored IDs are recomputed and compared during reverse mapping.

## 7. RunRelationship Mapper

All six fields are mapped explicitly. Enum conversion is exact and `created_at` is normalized to UTC. Source/target existence, cycle detection, reverse edges, replay, update, and deletion are not Mapper responsibilities.

## 8. ChangedFile Mapper

The Mapper covers every file change type, nullable hashes, and previous path. Content hashes and previous path do not enter technical identity. The Domain constructor enforces each change-type shape.

## 9. ChangedSymbol Mapper

File path, qualified name, `SymbolType`, and `SymbolChangeType` are explicit. Symbol and change types do not enter technical identity. The Mapper does not parse source or ASTs.

## 10. TestExecution Mapper

The command, purpose, exact status, counts, nullable not-run reason, and nullable artifact reference are preserved. Mapping never executes commands or reads artifacts. Domain validation owns status/count/reason legality.

## 11. Artifact Mapper

The Mapper preserves the actual seven Domain fields. Location interpretation remains the Domain contract: a legal scheme prefix is a URI; otherwise the value must be a repository-relative path. Mapping performs no filesystem existence check or download.

## 12. Reference Mappers

Component and ADR references preserve their parent Run ID and exact Enum values. They do not query the Component Catalog, read ADR files, decide ADR status, or verify referenced entity existence.

## 13. Annotation Mappers

Limitation and RecommendedTask fields are explicit. Nullable component identity is preserved. Mappers neither mutate historical status nor create or execute future tasks.

## 14. Enum Conversion

Storage uses exact string Enum values. Reverse conversion rejects unknown, repaired, trimmed, or case-folded values. Tests enumerate the frozen Enum domains relevant to identity and detail mapping.

## 15. Datetime and Nullable Values

Aware datetimes are normalized to UTC without dropping microseconds. Naive values fail. `None` is preserved for optional hashes, paths, reasons, artifact metadata, and component references; empty strings do not stand in for unknown values.

## 16. Artifact Location

Location parsing is delegated to the official `ImplementationArtifact` constructor. The Mapper does not consult the host filesystem and never changes a URI into a local path.

## 17. Error Safety

Mapper failures expose stable error code, object type, safe identifier, field name, and underlying error type. Arbitrary records, commands, descriptions, reasons, and secret-like rejected values are never interpolated into Mapper messages.

## 18. Round-trip Semantics

For all eleven objects, Domain → ORM → Domain preserves Domain equality. ORM → Domain → ORM preserves every business column; Task and Run version reset to `1` per their existing contracts, datetime may normalize to UTC, and technical IDs are deterministically recomputed.

## 19. Mapper Drift Verification

Tests compare Domain dataclass fields and ORM columns against explicit allowlists, require the full public Mapper inventory, execute the frozen identity vectors, exercise Enum values and invalid records, and retain Task/Run regressions. This is test-time drift detection, not a runtime reflection Mapper.

## 20. Purity Boundary

The Mapper layer may instantiate records, read already-loaded columns, call Domain constructors, convert values, and calculate standard-library SHA-256. It may not open files, inspect Git, read environment variables, use randomness or networking, create an engine/session/connection, issue SQL, or control transactions.

## 21. Deferred Repository Semantics

Exact replay, same-identity conflict, append-only enforcement, relationship endpoint and DAG validation, query behavior, and transaction atomicity remain deferred to the PostgreSQL Repository implementation.

## 22. Deferred Manifest Binding

Manifest Parser / Indexer, repository identity resolution, Git consistency checks, and binding one manifest to these Domain objects are not implemented by this task.

## 23. Deferred Migration

No schema creation, DDL, migration execution, Session, Unit of Work, or real PostgreSQL connection is included. The next verification boundary is isolated migration and PostgreSQL testing.

## 24. Complete Mapper Acceptance State

The complete eleven-object Mapper inventory, stable ChangedFile/ChangedSymbol technical IDs, reverse identity validation, round trips, field drift guards, safe errors, and purity guards are implemented. The Mapper stage is complete.

## 25. Handoff to Migration

The only recommended next task is `QM2-P0-002A2b — Ledger Migration and Isolated PostgreSQL Verification`.
