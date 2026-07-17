# Research Artifact Recovery v1

Materialization resolves a Descriptor, verifies every referenced Blob, writes
real files under a unique staging tree, fsyncs and hashes them, runs the formal
Domain Validator, and atomically renames the validated artifact into a missing
or empty destination. A non-empty destination is rejected. Corrupt or missing
Blob evidence fails closed and is not automatically repaired or deleted.

## Recovery drill

The default persistent Store independently restored a Dataset Snapshot context,
the Study's two supporting Factor Values, Optimization Study
`fos_fdd33e...0046ba9`, canonical Registry `frs_c2ef67...50237b5`, and Campaign
`rc_4970d1...19cd5f`. The acceptance sample Factor Values was
`fv_609cfa...115c07f`.

For Factor Values, Optimization, Registry and Campaign, repository-relative
file paths, sizes and SHA-256 digests exactly matched the preserved sources.
Each restored artifact passed its existing formal Domain Validator using only
the restored Dataset/Factor Values context. The recovery copies were then
removed and all sampled Store artifacts still passed verify-on-read. No source
artifact was modified or removed.

Operationally: initialize/validate the Store, run `verify`, materialize the
required dependency graph into its conventional collection layout, pass the
appropriate restored Snapshot/Factor Values validation contexts, compare the
Descriptor inventory, then consume the restored artifact. Keep failed copies
for diagnosis; never mutate Store Blobs.
