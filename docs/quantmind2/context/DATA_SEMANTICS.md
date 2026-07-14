# Data Semantics

## Authority

Dataset Snapshot is the authoritative version consumed by research, training,
factor computation, and Qlib view generation. Qlib binary is not a source of
truth.

## Required lineage

Every derived dataset records source Snapshot ID, schema version, field catalog
version, universe version, adjustment policy, PIT policy, producer code hash,
artifact URI, and content hash.

## Time semantics

Event time and information-available time are distinct. A field may be used at
time T only if its configured availability timestamp is no later than T.

## Market semantics

- Internal stock codes use uppercase prefix format such as `SH600000`.
- Raw provider responses are immutable.
- Raw and adjusted prices have distinct fields and policies.
- Unknown ST, suspension, listing, delisting, or corporate-action values remain
  unknown; they are not silently filled with optimistic defaults.
- A partially updated dataset cannot be published or consumed by an Experiment.
