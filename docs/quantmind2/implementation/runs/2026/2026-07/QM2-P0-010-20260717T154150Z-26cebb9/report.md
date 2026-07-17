# QM2-P0-010 Implementation Report

## Task Summary

Implemented Persistent Research Artifact Store v1, migrated the complete
current reachable research graph, published an immutable Store Inventory and
completed source-independent recovery. No research was rerun and no Fresh,
model, signal, Qlib or backtest result was created.

## Goal, Scope and Non-goals

Scope is Store configuration/format, content-addressed Blobs, strict
Descriptors, formal Domain validation, immutable import, exact-existing and
conflict behavior, readers, materialization, reachability, inventory,
integrity, CLI, migration/recovery evidence, tests and Project Memory. Cloud
storage, distributed locking, DB/API/UI, background sync, deletion GC, runtime
cutover and new research are explicit non-goals.

## Preflight

- Repository/branch: `quantmind-main` / `master`
- Base commit: `26cebb9a9dfa95a295a57d66db193d9629844b90`
- Dirty before: false; unrelated dirty files: none
- Factor Lab remained read-only.

## Implementation

`FileSystemResearchArtifactStore` implements the `ResearchArtifactStore`
Protocol. Root precedence is CLI, environment, then the user-local v1 default.
FORMAT and all identities omit physical paths and usernames. Source scanning
rejects links, special files, traversal, collisions and limits. Files are
streamed, hashed, fsynced and exclusively published into SHA-256 Blob paths.
Descriptors atomically bind unchanged Domain IDs to sorted Blob inventories,
lineage and Domain Validator evidence. Existing bytes are verified/deduplicated;
logical conflicts fail closed.

Readers verify by default. Materialization recreates real files in a staged
conventional Domain layout, verifies every hash, invokes the formal Validator,
then atomically publishes to an empty destination. Integrity reports
healthy/degraded/corrupt and only lists unreferenced Blobs; no delete operation
exists. The CLI covers init, inspect-source, import, plan/migrate current, list,
verify, materialize, inventory and safe inspect.

## Migration and Recovery Evidence

- Plan: `rap_f3aca751ad751c976888fd9b464f9f56dd4913339b226786c0c3a7ef65ccc247`
- Migrated/reachable/missing: 65 / 65 / 0
- Logical/unique/deduplicated bytes: 107,663,971 / 107,518,972 / 144,999
- Unique Blobs: 280
- Inventory: `sai_a0b9e6183a7bed95d9dbcce918a19c9e2f63a67ffbc7617a2091b7a37955d312`
- Integrity: healthy, zero issues/unreferenced Blobs

Recovery independently restored the Validation Dataset Snapshot context, two
supporting Factor Values, Optimization `fos_fdd33e...`, canonical Registry
`frs_c2ef67...` and Campaign `rc_4970d1...`. Formal Validators and full
path/size/SHA-256 source parity passed. Recovery copies were removed; Store and
original sources remained verified and unchanged.

## Architecture, Security and Data Lineage Impact

Git remains authority for code, governance and small Fresh controls; the Store
becomes local authority for large immutable research artifacts. Existing Domain
Artifact IDs and formal Validators are reused, not replaced. The current
Registry-to-Campaign/Optimization/Validation/Dataset lineage is now durable.
No secrets, labels, Factor Value contents or user paths enter portable
identities. No dependency, lockfile, runtime configuration, API or database
schema changed.

## Tests and Results

Focused Store tests cover Blob publication/conflict/concurrency, security,
import/replay/conflict, materialization, inventory, integrity, reachability and
all 65 real artifacts. Existing relevant Dataset/DSL/Optimization/Validation/
Registry/Campaign/Fresh/Manifest/Context suites, JSON parsing, py_compile,
Context Bootstrap, diff checks and Factor Lab digest are executed before
commit. Exact commands and counts are in the Manifest.

## Limitations, Compatibility and Rollback

v1 is local-filesystem only and does not promise NFS or multi-node
transactions. Runtime producers and consumers still use their existing paths
until QM2-P0-011. Cloud storage, metadata API/UI, automatic synchronization,
quarantine repair and deletion GC are absent. Fresh dates remain 0/60.

Rollback is a revert of the additive commit plus optional operator retirement
of the user-local Store after verifying no consumer depends on it. Existing
temporary sources are preserved, so code rollback does not require research
recomputation.

## Git and Recommended Next Task

One independent commit is created with `feat(qm2): add persistent research
artifact store`; no amend or push. The only next task is `QM2-P0-011 —
Artifact-backed Research Runtime Cutover and Recovery Drill`. `QM2-FV-001`
remains conditional on at least 60 mature post-lock trading dates.
