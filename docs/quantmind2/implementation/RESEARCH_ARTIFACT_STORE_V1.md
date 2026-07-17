# Research Artifact Store v1

## Scope and authority

The v1 Store is the local durable authority for large immutable research
artifacts. Git remains authoritative for implementation, Project Memory,
governance contracts, candidate locks, protocols, ledgers and watermarks. The
Store is not a Git replacement and Git is not a large-artifact store.

Root resolution is CLI `--store-root`, then
`QUANTMIND_ARTIFACT_STORE_ROOT`, then `~/.quantmind2/artifact-store/v1`.
The physical root never participates in an artifact identity.

## Format and identities

`FORMAT.json` freezes format `1.0.0`, SHA-256 and descriptor schema `1.0.0`.
Blobs live at `objects/sha256/<prefix>/<digest>`; descriptors at
`artifacts/<kind>/<domain-id>/descriptor.json`; immutable inventories and
receipts have their own directories. Domain Artifact ID, `sad_` Descriptor ID,
Blob SHA-256 and `sai_` Inventory ID are distinct.

Descriptor identity binds kind, unchanged Domain ID, source Manifest hash,
stable file path/hash/size/role inventory, lineage and Validator version.
`created_at`, username and absolute source/store paths are excluded.

## Publication and deduplication

Files are streamed into unique in-store staging files, hashed and sized,
flushed and fsynced, then published with exclusive hard-link semantics. The
parent directory is fsynced. Existing bytes are fully verified and reused;
inconsistent bytes fail with `BLOB_CONTENT_CONFLICT`. Descriptors use staged
directory rename and never overwrite an existing logical identity.

## Security and validation

Import accepts only real directories and regular single-link files. It rejects
symlinks, hard-link ambiguity, special files, traversal, absolute paths,
case/Unicode collisions and configured count/byte limit violations. It never
executes imported code or loads pickle. Every known artifact kind passes its
existing formal Domain Validator before publication; generic bundles still
require a Manifest and declared hashes.

## Reader, inventory and integrity

The reader exposes descriptor lookup/listing, verify-on-read and verified
materialization without returning writable Blob paths. Inventory identity
binds the complete descriptor/artifact/Blob view and integrity state.
Integrity scanning checks descriptors, unique Domain IDs and Blob existence,
size and hash, and reports unreferenced Blobs as `degraded`; it never repairs or
deletes data. No delete, purge, vacuum or GC operation exists.

## Concurrency and deferred scope

v1 supports concurrent publication on one local filesystem and atomic
same-filesystem publication. It does not promise NFS/distributed transactions.
Cloud backends, distributed locks, metadata DB/API/UI, background sync and
deletion GC are deferred.
