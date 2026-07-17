# Implementation Manifest v2

## 1. Why v2

Manifest v1 remains valid historical evidence, but it cannot independently
construct the eleven frozen Ledger Domain families. In particular, it lacks a
complete Task, stable child identities, typed references and annotations, a
general Run relationship, explicit artifact location kind, and versioned
Mapper identity rules. Manifest v2 (`schema_version: 2.0.0`) is the default
exchange protocol for new Implementation Runs and carries those facts without
reading report prose.

## 2. Authority model

Git is authoritative for committed bytes, containing commit, and immutable
history. The Manifest records producer-known pre-commit facts. A caller-owned
`RepositoryBinding` maps a trusted logical repository ID to a checkout. The
Indexer verifies Git and resolves committed status; it never trusts an absolute
execution path as a business identity and never invents a result commit.

## 3. v1 limitations and immutable compatibility

The v1 parser and hash algorithm are unchanged. Existing v1 files are never
upgraded, patched, or enriched from report prose. A v1 Run may parse and pass
Git consistency while retaining evidence gaps that prevent indexing. The
QM2-P0-001F result-commit mismatch remains a recorded failure.

## 4. Top-level structure

The strict top-level objects are `repository`, `task`, `run`, `relationships`,
`changed_files`, `changed_symbols`, `tests`, `artifacts`,
`component_references`, `adr_references`, `limitations`,
`recommended_tasks`, and `integrity`. The Schema disallows additional
properties on all protocol objects.

## 5. Repository identity

`repository.repository_id` is the logical identity. The producer receives it
as explicit structured input; the generic parser does not hard-code it.
`execution_repository_path` is environment evidence only. Branch and base
commit are repeated on the Run and must agree. The trusted Binding must match
the logical ID, while its checkout path may differ from the recorded execution
path.

## 6. Task and Run

Task contains ID, optional parent ID, title, objective, scope, non-goals,
formal status, and UTC creation time. Run contains every Manifest-known field
of `ImplementationRun`, including logical repository ID, source status,
verification, paths, hashes, consistency and canonical state. Before commit,
`result_commit` is null and source status is honestly uncommitted. Git analysis
resolves the containing commit and committed status without rewriting the Run.

## 7. Relationships

Every relationship has an explicit stable ID, source and target Run IDs, typed
relationship, reason, and UTC creation time. It is never inferred from array
position, recommendations, or Task parentage. Repository DAG enforcement is
unchanged.

## 8. Changed files and symbols

Changed files preserve path, change type, before/after hash and previous path.
Changed symbols preserve file path, qualified name, symbol type and change
type. Their technical IDs remain Mapper-derived using the declared
`changed-file-v1` and `changed-symbol-v1` algorithms; no array index or line
number participates.

The current Run's `run.manifest_path` is the protocol carrier and is not a
ChangedFile business object. Including it would require its `after_hash` to be
embedded in the same bytes being hashed, changing the hash again. Therefore it
must be absent from `changed_files`; placeholders and iterative hash attempts
are invalid. It remains in `integrity.git_changed_paths` and
`git_added_paths`, is discovered at its canonical path, and is protected by the
canonical payload hash plus immutable Git-blob checks. `report.md` has no such
self-reference and may remain a ChangedFile and an Artifact.

## 9. Tests and artifacts

Each test has an explicit execution ID, recorded command, purpose, typed
status/counts, optional non-run reason, and optional evidence artifact. Commands
are evidence only and are never executed by the parser. Artifacts have stable
IDs and explicit `repository_path` or `uri` location kind. Repository paths
must be safe relative POSIX paths; URIs require a scheme. The Manifest artifact
has null content hash and size because embedding its own byte hash is
self-referential; its payload hash is authoritative.

## 10. References, limitations, and recommendations

Component impact, ADR relation, limitation severity/status, and recommendation
priority are typed enums. Limitation and recommendation IDs are producer-owned
stable identities. Recommendations do not create or execute Tasks.

## 11. Integrity and versioning

`mapper_contract_version` is `1.0.0`; unknown Mapper or technical identity
versions fail closed. Payload canonicalization is
`implementation-manifest-v2-canonical-json-v1`: deep-copy the payload, remove
only `integrity.manifest_payload_sha256`, encode JSON as UTF-8 with sorted keys,
compact separators `,` and `:`, `ensure_ascii=false`, no trailing newline, and
reject NaN/Infinity. Nulls and array order are preserved. SHA-256 is then
computed over those bytes.

`report_sha256` is the exact report byte hash. Artifact hashes cover all
hashable artifacts. Source-bundle hash is canonical JSON over sorted changed
paths and their current bytes, with explicit deleted entries and a special
null-hash Manifest-payload entry. Git-diff hash is canonical JSON over exact
changed/added/deleted inventories plus structured Domain changed-file facts.
The Run mirrors source-bundle and Git-diff hashes. Historical v1 uses its own
unchanged top-level payload-hash rule.

## 12. Producer workflow

New Runs must use:

```text
python tools/quantmind2/create_implementation_manifest.py new \
  --input structured-input.json --output manifest.json
python tools/quantmind2/create_implementation_manifest.py finalize-payload \
  --manifest manifest.json --report report.md --repository-root "$PWD"
python tools/quantmind2/create_implementation_manifest.py validate \
  --manifest manifest.json --repository-id quantmind-main \
  --repository-path "$PWD"
```

`new` adds only protocol constants/placeholders and does not infer business
semantics. `finalize-payload` computes pre-commit integrity and refuses a
result commit or committed source status. `validate` applies Schema, version,
cross-object, Binding, and Domain construction checks. The input must supply
all structured Task, Run, children, references, annotations, and exact Git path
inventories.

All three producer/validator boundaries reject
`changed_files[*].path == run.manifest_path` with stable code
`MANIFEST_SELF_REFERENCE`. This is a semantic path rule because JSON Schema
cannot compare two instance paths.

### Post-commit completion gate

A Run is not complete merely because its Manifest validates before commit.
After the containing commit exists, the exact base-to-containing Git diff must
be reconstructed and all of the following must hold:

- `integrity.git_changed_paths` equals the complete committed changed-path
  inventory and includes the current Run Manifest;
- `integrity.git_added_paths` equals the complete committed added-path
  inventory and includes the Manifest when that Manifest was newly added;
- business `changed_files` equals the committed changed-path inventory with
  only the current Run Manifest removed, and still contains the Report;
- Planner reports `validated=true`, `indexable=true`, zero evidence gaps and
  zero warnings for a new v2 Run.

The producer does not guess late paths or silently patch a finalized payload.
A post-commit mismatch keeps the original Run immutable and non-indexable; any
correction is a new independently validated Run with explicit correction
evidence and a `corrects` relationship.

## 13. Parser routing and Indexer workflow

The parser routes `1.0.0` to the unchanged v1 contract, `2.0.0` to v2, and
rejects every other version. For v2, Git consistency verifies Binding, report
and payload hashes, exact committed path inventory, Domain changed-file bytes,
artifact bytes, source bundle and diff hash, containing commit, and immutable
Run files. A successful v2 plan constructs a complete, gap-free Domain Bundle.
The existing two-pass Indexer writes Task/Run/children first and relationships
second inside the existing Unit of Work; exact replay and immutable conflict
semantics remain Repository-owned.

Business ChangedFile comparison removes only the current Run's Manifest from
the actual base-to-containing Git diff. It does not remove the Report, another
Run's Manifest, an arbitrary JSON file, or any other changed path. The complete
protocol Git inventory, including the current Manifest, is still checked
separately against the real diff.

Committed v2 payloads created before this rule may contain exactly the same
path in `changed_files` and `run.manifest_path`. The committed parser preserves
those bytes, Git evidence emits
`LEGACY_V2_MANIFEST_SELF_REFERENCE_IGNORED`, skips only that item's before/after
hash, and the Domain mapper does not construct a ChangedFile for it. Every
other path, status, hash, artifact, payload, report, diff and immutable-history
check remains mandatory. This rule is structural and contains no Run-ID
special case. New producer and standalone validation remain strict.

## 14. End-to-end verification and historical policy

The forward-indexability suite creates a real temporary Git repository,
generates and commits a v2 Run, resolves its committed status, and verifies all
eleven Domain families without prose fallback. The isolated PostgreSQL suite
applies migration 0001, indexes the bundle, verifies every family and
relationship, replays exactly, injects an immutable conflict, and verifies no
partial write before container cleanup. No production database is accessed.

Historical v1 statistics remain separately measured and are not improved by
v2 defaults. Manifest v2 closes only the future evidence-production gap.

## 15. Ledger closure and handoff to Factor DSL

With forward self-reference handling fixed, Ledger infrastructure remains
closed. This does not deploy the Ledger, add an API/UI, backfill unrelated
history, or add watchers. The sole next task is `QM2-P0-004 — Factor DSL v1 on
Real Legacy Feature Dataset Snapshot`.
