# Implementation Report: QM2-P0-002A2a2c1

## 1. Task Result

Completed. Mapper identity/conversion contract v1 and recomputable identity
vectors are fixed; all 36 acceptance criteria pass. Generated Run status is
`completed_uncommitted`; implementation stopped before A2a2c2.

## 2. Preflight State

Repository was clean on `master` at
`1d5affbb3361c60286028e569bb391f6955dc216`; unrelated dirty files: none.
Official Factor Lab was clean/read-only at
`c83192c2278767e03f008bc39197b1ba33bfb6a9`.

## 3. Context Read Confirmation

All required Project Memory, architecture, Domain, Repository, six ORM
contracts, ADR-0005/0007, previous Run, Domain/ORM source, and in-memory
Repository source were read. Domain is semantic authority, Repository owns
behavior, ORM is shape, and Mapper must call Domain constructors.

## 4. Mapper Boundary Decision

Future flow is `Domain → pure Mapper → ORM record` and `ORM record → pure
Mapper → Domain constructor/validation → Domain`. Mapper performs no I/O,
query, commit, repair, parent lookup, replay/conflict decision, business
transition, or partial reconstruction. No Mapper Python exists in this task.

## 5. Repository Identity Decision

Frozen Domain/ORM `ImplementationRun.repository_root` means logical repository
identity. Manifest v1's same-named absolute path is Execution Context and is
not directly copied. A future Indexer must receive an explicit trusted
path/source-to-logical-ID binding; basename, username, path, environment, and
Git remote inference are forbidden. Historical Manifests remain immutable.
Manifest v2 should split `repository_id` and `execution_repository_path`; this
long-term cross-module distinction is a future ADR candidate, not an ADR or
model change here.

## 6. Stable Technical ID Contract

### ChangedFile

NFC-normalized strict UTF-8 payload without trailing LF:
`changed-file-v1\n<run>\n<POSIX path>\n<change_type.value>`. ID is `cf_` plus
64 lowercase SHA-256 hex. Hashes and `previous_path` are excluded; destination
path identifies rename. Same identity/different content is Repository conflict.

### ChangedSymbol

Payload: `changed-symbol-v1\n<run>\n<POSIX file_path>\n<qualified_name>`.
ID is `cs_` plus 64 lowercase hex. `symbol_type` and `change_type` are excluded.

Both preserve case, use LF separators, perform no path/filesystem resolution,
and treat a digest collision as a hard error without fallback.

## 7. Existing Domain Identity Mapping

Task, Run, relationship, test, artifact, limitation, and recommendation IDs are
copied unchanged. Component/ADR references use their existing Run/object
composite identities. Invalid stored values go through Domain constructors and
fail; Mapper does not regenerate, rename, trim, or clean them.

## 8. Enum Conversion Contract

Domain-to-ORM writes `enum.value`; ORM-to-Domain calls the exact Enum with the
stored string. All 16 frozen Enums are covered. Unknown, wrong-case,
whitespace-padded, null, or wrong-type values fail as `UNKNOWN_ENUM`; only a
real Domain member such as `SymbolType.UNKNOWN` is accepted.

## 9. Datetime Conversion Contract

Only timezone-aware datetime is accepted. Both directions normalize to UTC and
preserve microseconds. Naive datetime fails; Mapper never guesses local zone or
attaches UTC. `completed_at=None` passes unchanged to Domain state validation.

## 10. JSON / Tuple Conversion Contract

Task tuples become fresh JSON lists with order/duplicates/text unchanged.
Reverse conversion accepts only list/tuple of strings and creates a fresh
tuple. Arbitrary JSON, null items, numbers, mappings, sorting, deduplication,
trim, and shared mutable references are forbidden.

## 11. Path / URI Conversion Contract

Repository paths pass unchanged to Domain validation with no filesystem access.
Artifact `path_or_uri` follows existing Domain authority: scheme-prefix regex
means URI; otherwise repository-relative path. Mapper does not use `contains
://` or guess. Rejected/ambiguous values fail. Manifest v2 `location_kind` is
recommended but is not required to map current valid Domain values.

## 12. Nullable Value Contract

None and empty string are never conflated. Optional parent, commit, completion,
hash, previous path, test artifact, artifact metadata, and component values
retain None only where Domain permits it. Empty strings are not cleaned to None.

## 13. Mapper Error Contract

Future `RecordToDomainError` carries object type, safe identity, field, stable
code, safe message, and underlying Domain error type. Future
`DomainToRecordError` covers missing technical context, unsupported versions,
unrepresentable target values, unresolved repository identity, and ambiguous
artifact location. Neither exposes secrets, full commands/records/reasons,
descriptions, ORM repr, or database URL.

## 14. Round-trip Contract

All eleven Domain families must satisfy Domain equality after record round
trip. UTC normalization preserves instant/microseconds; JSON returns tuples;
technical IDs are excluded from Domain equality. ORM value round trips retain
all business columns and deterministically recompute the same technical IDs.

## 15. Mapper and Identity Versioning

- Mapper contract: `1.0.0`.
- ChangedFile identity: `changed-file-v1`.
- ChangedSymbol identity: `changed-symbol-v1`.

Semantic/algorithm changes require new versions. Old IDs are never rewritten;
future Indexer must record versions. Existing ORM lacks version columns.

## 16. Test Vectors

Nine JSON vectors cover added/renamed/hash-conflict/Unicode/case ChangedFiles
and module/method/Unicode/type-conflict ChangedSymbols. Standard-library tests
recompute canonical payload, SHA-256, prefix, exclusions, and case behavior.
Vectors contain no absolute path or secret.

## 17. Manifest v1 Compatibility

Most scalar/time/hash/path/test/artifact/reference/annotation fields can be
mapped through an Indexer vocabulary layer. Missing or insufficient fields:
logical repository ID, identity/Mapper versions, artifact location kind,
ChangedFile/Symbol technical IDs, and first-class general relationships/richer
domain vocabulary. Manifest v2 is recommended; historical v1 files are not
changed.

## 18. Files Added

- `LEDGER_DOMAIN_ORM_MAPPER_CONTRACT_V1.md`: normative 27-section contract.
- `ledger_mapper_identity_v1.json`: nine standard-library-recomputable vectors.
- This Run's Report and Manifest.

## 19. Files Modified

Context Bootstrap validator/test and the allowed Current State, Component
Catalog, Known Issues, Roadmap, Handoff, Terminology, Database Schema Index and
machine-readable peers. No Domain, ORM, Repository, ADR, dependency, lockfile,
configuration, or Factor Lab file changed.

## 20. Validation and Tests

| Scope | Passed | Failed | Skipped | Not run |
| --- | ---: | ---: | ---: | ---: |
| 11-table ORM regression | 108 | 0 | 0 | 0 |
| Domain + Repository + Context | 155 | 0 | 0 | 0 |
| Context Bootstrap | 30 | 0 | 0 | 0 |
| targeted py_compile | 2 | 0 | 0 | 0 |
| JSON parse before this Run | 26 | 0 | 0 | 0 |
| Manifest schema/report/payload hashes | 3 | 0 | 0 | 0 |
| diff/scope guards | 3 | 0 | 0 | 0 |
| Factor Lab identity/cleanliness | 2 | 0 | 0 | 0 |
| real database | 0 | 0 | 0 | 1 |

## 21. Expected vs Actual

| Requirement | Expected | Actual | Evidence | Status |
| --- | --- | --- | --- | --- |
| contract | all 11 families | all named and bounded | validator | passed |
| identity | versioned deterministic | 9 recomputed vectors | tests | passed |
| repository identity | logical/path split | explicit binding required | contract | passed |
| conversions | enum/time/JSON/path/null | exact rules | contract markers | passed |
| errors | safe structured failure | two directions/codes | contract | passed |
| round trip | all families | normative equality | contract | passed |
| Mapper implementation | absent | no directory/functions | source guard | passed |
| regressions | Domain/Repo/ORM/Context | 263 tests | unittest | passed |
| Factor Lab | unchanged | clean expected HEAD | Git | passed |

## 22. Implementation Run

Run ID `QM2-P0-002A2a2c1-20260714T181338Z-1d5affb`; base
`1d5affbb3361c60286028e569bb391f6955dc216`; result commit null in immutable
pre-commit Manifest; status `completed_uncommitted`; verification targeted.

## 23. Project Memory Updates

Memory records Contract v1 as complete but every Mapper implementation as
absent, identifies the Manifest/Domain repository-field mismatch and artifact
location limitation, and hands off only to A2a2c2. Machine task arrays retain
legal parent IDs under context schema v1.

## 24. Known Limitations

No Mapper implementation or live database evidence; misleading frozen
`repository_root` name remains; Manifest v1 has no logical repository ID,
identity/Mapper versions, or artifact location kind; current ORM has no
identity-version columns; no migration exists.

## 25. Unresolved Questions

Future approval is needed for the repository identity ADR/field rename,
Manifest v2 fields, identity-version persistence, and explicit artifact
location kind. Pinned SQLAlchemy/real PostgreSQL evidence also remains absent.

## 26. Compatibility and Rollback

The contract is additive documentation/validation and does not reinterpret
historical files in place. Rollback is the containing Git commit; no database,
data, migration, dependency, or runtime rollback is necessary.

## 27. Scope Confirmation

Not implemented: Core, Detail, Reference, or Annotation mappers; PostgreSQL
Repository; Session/UoW; migration; Manifest Parser/Indexer; API/UI; TDX;
Dataset Snapshot; Factor DSL/Optimization/Validation/Registry; LightGBM/Qlib
changes. No ORM or Domain model was modified.

## 28. Git State After

One commit will use `docs(qm2): define ledger mapper identity contract`.
Manifest remains truthfully pre-commit with null result commit. No push.

## 29. Recommended Next Task

Only `QM2-P0-002A2a2c2 — Core Task, Run and Relationship Mappers`. It must be
independent because it introduces the first real conversion code and safe error
objects. This task did not begin it.
