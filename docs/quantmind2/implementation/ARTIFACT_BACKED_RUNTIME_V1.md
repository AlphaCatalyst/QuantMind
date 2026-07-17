# Artifact-backed Research Runtime v1

Status: implemented by `QM2-P0-011`  
Authority: accepted implementation contract subordinate to ADR-0007 and ADR-0010

## 1. Authority Model

The formal research read path is:

```text
Domain Artifact ID
-> Store Descriptor lookup and verification
-> Blob verification
-> ephemeral descriptor-keyed materialization
-> Domain Validator
-> research consumer
```

The formal publication path is:

```text
local staging artifact
-> Domain Validator
-> immutable Store import
-> descriptor reload
-> StoreBackedArtifactRef
```

The Domain Artifact, Store reference, materialized directory and legacy source
directory are different objects. The Store is authoritative for large research
artifacts. A cache or historical `/private/tmp` tree is never authoritative.

## 2. Runtime Reality Audit

| Module | Previous top-level input | Absolute path accepted before cutover | Exact-existing before cutover | Previous publication | Source-path / hard-code finding | v1 formal switch | Retained low-level boundary |
|---|---|---:|---|---|---|---|---|
| Factor Values | dataset and output roots | yes | local manifest only | local directory | path supplied by caller | resolve/publish adapter | Parquet reader, DSL executor and validator keep explicit paths |
| Optimization | template, snapshot, spec and output roots | yes | local Study lookup | local Study and Factor Values | CLI required local roots | Store Study replay before trials | optimizer and Study validator keep explicit paths |
| Validation | Study, Factor Values, selection and result roots | yes | local result lookup | local Validation/Frozen directories | CLI required sibling roots | Store result/Frozen replay | metric computation and validators keep explicit paths |
| Registry | snapshot/output and evidence roots | yes | local snapshot lookup | local snapshot | CLI required evidence roots | canonical snapshot resolves by Domain ID | snapshot parser and validator keep explicit paths |
| Campaign | campaign/output and dependency roots | yes | local campaign lookup | local campaign | default execution assembled `/private/tmp` dependencies | Store campaign replay precedes Agent entry | campaign validator and builder keep explicit paths |
| Fresh Admission | admission/output and evidence roots | yes | local result lookup | local result | default evidence roots referenced `/private/tmp` | Store admission resolve/replay | admission validator keeps explicit paths |
| Fresh Validation | Git controls plus local research artifacts | yes | control-specific | local result where eligible | mutable evaluation path relied on local artifacts | Git controls remain Git; research artifacts resolve from Store | protocol/control readers keep explicit paths |

The cutover changes top-level orchestration and CLI authority. It intentionally
does not rewrite low-level deterministic functions. Those functions may receive
a verified materialization path from the runtime but may not discover fallback
paths or decide Store policy.

## 3. Store-backed Artifact Reference

`StoreBackedArtifactRef` records `artifact_kind`, Domain `artifact_id`, immutable
`descriptor_id`, Store format, Domain validator name, lineage summary and an
optional Inventory baseline. `reference_id` is the SHA-256 of canonical logical
fields. Physical Store roots, cache roots, legacy roots, usernames, timestamps
and secrets are excluded. The reference does not replace the Domain Artifact ID.

## 4. Runtime Policy

- `store_required` is the formal CLI default. Existing artifacts must resolve
  from the Store. A miss is a hard failure and never triggers recomputation.
- `store_preferred` first resolves the Store. A missing artifact may use an
  explicitly supplied local artifact only after Domain validation and mandatory
  Store import.
- `legacy_local` preserves explicit old path APIs for tests, diagnosis and an
  emergency rollback. It cannot produce a formal publication by itself.

CLI parameters override environment variables. Supported variables are
`QUANTMIND_ARTIFACT_RUNTIME_MODE`, `QUANTMIND_ARTIFACT_STORE_ROOT` and
`QUANTMIND_ARTIFACT_CACHE_ROOT`. Invalid modes fail closed.

## 5. Resolver

`resolve_artifact(context, artifact_kind, artifact_id)` performs descriptor
lookup, kind/ID checks, descriptor and blob verification, cache validation or
atomic materialization, and Domain validation. It returns `ResolvedArtifact`.
Its safe summary contains logical IDs, cache-hit state and validation status;
the materialized path remains process-local.

Dataset Snapshot and Factor Values dependency artifacts are recursively
materialized where their unchanged Domain Validators require the dependency.
Validation Result validation is self-contained after Store recovery and checks
its own manifest, payload hash and embedded selection identity.

## 6. Materialization Cache

The cache key is the descriptor ID. `CACHE.json` binds that descriptor to the
materialized file inventory and hashes. Warm reads revalidate the cache; corrupt
entries are discarded and rematerialized. Staging uses an atomic rename and
per-descriptor process locks serialize concurrent local resolution. No symlinks
stand in for artifact files. Deleting the complete cache is safe.

## 7. Publisher

`publish_domain_artifact(...)` validates staging, imports it, reloads and checks
the descriptor, then returns `PublishedArtifact`. Existing identical artifacts
return the same reference with `exact_existing=true`. Descriptor conflicts,
validation errors and Store failures are hard failures. Staging is not deleted
and no staging path enters the result.

## 8. Exact Replay and Domain Adapters

Adapters cover Factor Values, Optimization Study, Validation Result, Frozen
Result, Registry Snapshot, Campaign and Fresh Admission. A known Domain ID is
resolved before expensive work. Optimization replay performs zero trial calls;
Campaign replay performs zero Agent, Optimization and Registry-write calls.
Validation/Frozen replay never recomputes metrics or reopens Frozen data.

The unified `tools/quantmind2/artifact_runtime.py` entry point supports safe
resolve, publish, replay, recovery and exact-existing publication checks.
Domain CLIs share the three runtime parameters and default to `store_required`.
Their Store-mode output is limited to logical IDs, descriptor/reference IDs,
cache/exact-existing status and validation summaries.

## 9. No Legacy-path Default

In `store_required`, a user-supplied legacy artifact root is rejected with
`LEGACY_ARTIFACT_PATH_FORBIDDEN`. The guard is source-aware: runtime cache,
current staging, Git control files and test fixtures are legitimate local paths.
Legacy source trees are not searched and are not recorded in lineage.

## 10. Formal Scope

This runtime does not change research identities, factor values, Optimization,
Validation, Frozen policy, Registry state, Fresh controls, Qlib or LightGBM. It
does not add cloud storage, distributed locking, database catalogs, APIs or UI.

