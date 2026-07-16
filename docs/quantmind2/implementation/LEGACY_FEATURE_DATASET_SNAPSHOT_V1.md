# Legacy Feature Dataset Snapshot v1

## 1. Dataset kind

`legacy_feature_matrix_v1` is a feature-matrix Dataset Snapshot, not raw daily
bars. It reuses the Dataset Snapshot v1 authority rules while preserving the
existing Daily Bars semantics unchanged.

## 2. Snapshot identity

The ID is `ds_<sha256(canonical identity JSON)>`. The identity binds Snapshot,
provider and source schema versions; dataset kind; provider, logical source and
production loader IDs; exact source file hashes; full source schema and column
roles; request; symbol-selection rule and selected symbols; included features
and labels; pass-through normalization version; output Arrow schema; and
Parquet partition hashes. It excludes creation time, absolute paths, user name,
temporary directories, and randomness.

## 3. Source lineage

`source_inventory.json` contains only logical/source-relative evidence. Internal
validation never needs the legacy source. When an explicit binding is supplied,
lineage validation rechecks logical identities, size, and exact source hashes;
changed or missing source bytes fail.

## 4. Schema

The Snapshot preserves source column names and values. The only output selection
is `symbol`, `trade_date`, the ordered allowed research features, and labels
only when explicitly requested. `schema.json` records fixed Arrow types,
nullability, the full source-role map, and access policy. No irreversible key or
feature rename occurs.

## 5. Feature roles

The 2025 real Snapshot includes all 152 enabled catalog features. The source's
extra `ind_ret_60d` is recorded as unknown but not materialized. Keys are not
features. Metadata, sample weight, forbidden, and unknown columns are not
research terminals.

## 6. Label isolation

The default request sets `include_labels=false`; default consumer output is keys
plus research features. The 2025 annual Parquet contains no evidenced label, so
the real Snapshot reports `label_count=0`. The production loader creates labels
later; this task does not reproduce them. A label-bearing future Snapshot must
opt in and use the separate label reader.

## 7. Storage

Each immutable directory is:

```text
snapshots/<snapshot_id>/
  manifest.json
  schema.json
  quality.json
  source_inventory.json
  partitions/feature_matrix/part-00000.parquet
```

The real runtime artifact is intentionally outside Git; no large dataset is
committed.

## 8. Parquet

PyArrow writes a fixed ordered table without a DataFrame index, zstd compressed
as Parquet 2.6. Rows are stable `trade_date, symbol` order. Source null/NaN and
source numeric dtypes are preserved through Snapshot reload. The production
training reader's separate numeric `float32` cast is an explicit downstream
conversion, not a Snapshot conversion.

## 9. Quality

Publication blocks empty data, missing/invalid keys, duplicate keys, invalid or
out-of-range dates, missing/non-numeric features, unstable ordering, label
leakage, forbidden/unknown exposure, and infinities. It records all-null,
high-null, constant features, and unknown source roles as warnings. Schema/dtype
drift, source duplicate years, source hash drift, output hashes, row/symbol
counts, output schema, and identity are checked by Provider/Snapshot validation.
No row or column is silently repaired or deleted.

## 10. Immutability

Creation uses a unique staging directory, validates it, then atomically renames
it to its identity path. Failures remove staging. Published directories are
never updated, appended, or overwritten.

## 11. Exact existing

Recreating identical source/filter/output returns `existing` with the same ID.
If an existing directory at that ID has a different identity payload, creation
fails with a conflict instead of overwriting it.

## 12. Loader parity

The real integration compares the existing production `_load_local_parquet`
output, Provider selection, and Snapshot reload for the same 2025 slice. Row
count, keys, ordered representative features, values, NaN masks, date/symbol
bounds, and label isolation match. Provider-to-Snapshot comparison is exact at
source dtypes. The sole production-loader allowlist is numeric source
`double`/`int64` to `float32`, exactly as existing training code specifies;
after applying that cast explicitly, equality and NaN masks are exact. No broad
`allclose` tolerance is used.

## 13. Consumer interface

`load_feature_matrix(output_root, snapshot_id, symbols=None,
date_range=None, feature_columns=None)` validates first and returns only keys
plus allowed features in stable order. `load_labels` is separate and refuses a
Snapshot without explicitly included labels. Both readers use only published
Snapshot files; they do not instantiate a Provider or access the legacy root.

## 14. Factor DSL input contract

`FactorDSLInputContract v1` is:

| Property | Contract |
|---|---|
| dataset kind | `legacy_feature_matrix_v1` |
| keys | `symbol`, `trade_date` |
| terminals | the Snapshot's `included_feature_columns` (152 in the real v1 artifact) |
| prohibited | labels, weights, metadata, forbidden, and unknown columns |
| dtype | fixed by `output_schema`; operators must not assume all terminals share one physical dtype |
| nulls | preserved; no implicit fill, drop, or look-ahead repair |
| cross-section | group only by an observed `trade_date` |
| order | dates ascending, then symbols ascending within date |
| minimum real slice | at least 100 selected symbols and 60 observed dates |
| mutability | input Snapshot and source terminal values are immutable |

Factor DSL v1 first treats existing legal research-feature columns as base
terminal variables. It cannot access labels through its feature reader.

## 15. Future TDX replacement

When TDX becomes available, it adds a TDX Provider and new normalized Daily Bars
Snapshots (`open`, `high`, `low`, `close`, `volume`, `amount`). It does not
replace or rewrite this Legacy Snapshot or the validated consumer boundary.
Both sources use the common immutable identity, manifest, hashes, quality,
atomic publication, exact-existing, validation, and read-only consumer model.
TDX is not required to emulate the legacy 152 terminals.

## 16. Deferred production scaling

Production scheduling, multi-part partition policy, catalog/database version
binding, large artifact storage, PIT calendar/universe, corporate actions,
finance/industry authorities, training migration, Qlib migration, API, and UI
are deferred. The real v1 artifact is a deterministic bounded research slice,
not a production-wide switch.

## Real v1 runtime evidence

- Source: logical ID `quantmind-production-feature-snapshots-v1`, year 2025,
  exact source SHA-256
  `7fd0316e6f8d936688ef332357fb7589f64c0e127c5f64e3158c584baf28b00f`.
- Filter: 2025-01-02 through 2025-04-03, first 100 source symbols sorted
  lexicographically, all 152 allowed research features, labels excluded.
- Result: 5,931 rows, 100 symbols, 60 observed dates, 0 labels, 0 quality
  errors and 6 warnings.
- Snapshot: `ds_bc82e7bb2c63d2c47677b11cf0f4fc1e5aa11a0ed18ee0bb27e3c8ab667d2ee7`.
- Parquet SHA-256:
  `8b42dc29e3265e7bc127a921a76f772b3feec78cca1df2d298b3736ae8d04548`;
  manifest SHA-256:
  `cc7951aa5c777b74396bbcf90cb410e7cd0c2b5f21ea484609583e50f4ebed79`.
- Repeated creation returned `existing`; binding validation returned
  `source_lineage=valid`; source hash before and after was unchanged.

