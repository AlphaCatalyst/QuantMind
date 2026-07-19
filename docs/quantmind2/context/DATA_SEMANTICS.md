# Data Semantics

## Authority

Dataset Snapshot is the authoritative version consumed by research, training,
factor computation, and Qlib view generation. Qlib binary is not a source of
truth.

The only active provider is `tushare-pro-v1`. The locked 500 universe is
selected from 2019's first 20 open sessions using only contemporaneously
observable eligibility and market-value data; the experiment 100 is its first
100 immutable ranks. `quantmind-production-feature-snapshots-v1` is retired,
purged, and forbidden as a formal runtime fallback.

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
- Adjusted OHLC is always raw OHLC multiplied by the contemporaneous Tushare
  `adj_factor`; no query-end dynamic rebasing is allowed.
- Rolling features are computed once on the continuous 2018-09-01..2026-06-23
  series before research-date slicing; no annual reset or value filling is
  allowed.
