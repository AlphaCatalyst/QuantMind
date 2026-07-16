# Legacy Feature Provider v1

## 1. Current production loader

The production entry is `docker/training/train.py`. `load_data` calls
`_load_local_parquet`, which resolves
`<local_dir>/model_features_<year>.parquet`. `LocalDockerOrchestrator` mounts
`TRAINING_LOCAL_DATA_PATH` read-only at `/tmp/feature_snapshots` and mounts the
current training script at `/app/train.py` before invoking it. A run loads each
year from `max(train_start_year - 1, 2016)` through the largest required end
year, so the loader is multi-year rather than single-year.

The loader requests `symbol`, `trade_date`, `open`, `close`, the configured
factor column and the allowed feature columns. It casts numeric source columns
to `float32`. `load_data` then constructs the tradable T+H return label and
sample weight, applies cross-sectional MAD plus Z-score, removes rows without a
label, and uses an explicit time split when present or the final `val_ratio`
fraction otherwise. Annual files do not contain the training label or weight.
The configured `label_formula` remains descriptive and does not drive that
calculation.

The feature allowlist is the 152 enabled keys in
`config/features/model_training_feature_catalog_v1.json` (or the active
administrative catalog in the production control path). This task did not
connect to PostgreSQL; the checked-in 152-key catalog is the provider's
explicit evidence source.

## 2. Source binding

`LegacyFeatureSourceBinding` separates the logical source identity
`quantmind-production-feature-snapshots-v1` from a machine-local `local_root`.
It also freezes loader identity
`docker-training-load-local-parquet-v1` and source schema version. The binding
is mandatory; no basename or current-directory inference is allowed. Local
absolute paths are execution inputs and are excluded from Snapshot identity and
metadata.

## 3. Source files

The bound source contains annual files for 2016 through 2026. Exact byte audit:

| File | Bytes | Rows | Columns | Dates | Symbols | SHA-256 |
|---|---:|---:|---:|---|---:|---|
| model_features_2016.parquet | 602,962,630 | 641,546 | 155 | 2016-01-04..2016-12-30 | 3,033 | `574f720a2b70626383859cfd727789a855d7a8b25267da4b785a3fc3cfe282f9` |
| model_features_2017.parquet | 723,001,808 | 743,239 | 155 | 2017-01-03..2017-12-29 | 3,465 | `388091237018283848400a9f753410a098d32576ff4a94c1f11fd2720ac4a59c` |
| model_features_2018.parquet | 797,045,553 | 816,988 | 155 | 2018-01-02..2018-12-28 | 3,570 | `00f0e217c7f1a903fde817ed343a7dfe8c3a6c562849e6bd14193e858fc54b0b` |
| model_features_2019.parquet | 856,970,945 | 884,867 | 155 | 2019-01-02..2019-12-31 | 3,767 | `b5b457af93a2711f7f2cfe90c95bf0fe2d94059b2a8c3c5745698a471cb07aef` |
| model_features_2020.parquet | 923,826,943 | 946,286 | 155 | 2020-01-02..2020-12-31 | 4,157 | `2b7a403fc86413d2a76bcb98a01a1bb987fca32d55480847260be61f263bd57f` |
| model_features_2021.parquet | 1,038,103,291 | 1,059,458 | 155 | 2021-01-04..2021-12-31 | 4,622 | `4da0fdb4ea004dc417fe0495beaaec2fdb4fb2b11bbb12b6540740ff564f6426` |
| model_features_2022.parquet | 1,070,040,417 | 1,146,263 | 155 | 2022-01-04..2022-12-30 | 4,947 | `c5f5764b30c95d315ffaef8642de53588f3da61abf6b75dacd5e7d3587abe830` |
| model_features_2023.parquet | 1,063,350,355 | 1,209,468 | 155 | 2023-01-03..2023-12-29 | 5,141 | `36da39e4f48c39de0172242e5f5b2635eff03a6acd9b3f0ebd84175f94efcf08` |
| model_features_2024.parquet | 1,140,597,454 | 1,233,202 | 155 | 2024-01-02..2024-12-31 | 5,170 | `769903540f5cc48ae469927ccff6f56e0d19f0599da5a1004d11e85a0ac5d40e` |
| model_features_2025.parquet | 1,160,044,834 | 1,248,108 | 155 | 2025-01-02..2025-12-31 | 5,212 | `7fd0316e6f8d936688ef332357fb7589f64c0e127c5f64e3158c584baf28b00f` |
| model_features_2026.parquet | 543,901,949 | 580,362 | 154 | 2026-01-05..2026-06-24 | 5,216 | `c2060c913dfdc7cc6a0723d19de53cc957c928a6ed490c163b1dceefde9269c1` |

2025 is the latest complete year and is the v1 real-Snapshot source. 2026 is
partial and has a different column count. The adjacent 2025 sidecar describes
older bytes and is not authoritative: the Provider hashes the current Parquet
itself.

## 4. Provider contract

`LegacyFeatureProvider.probe` checks the explicit binding without data access.
`discover` emits exact file inventory and one evidenced schema. `read` accepts
only a `LegacyFeatureRequest` and returns a typed `LegacyFeatureBatch`. Key scans
and data reads use bounded PyArrow batches; output is stably sorted by
`trade_date, symbol`.

## 5. Read-only boundary

The Provider opens source files only for metadata, hashes, and reads. It never
writes, sorts in place, fills nulls, computes a feature, constructs a label,
normalizes, invokes training/Qlib, or accesses the network. Tests hash source
bytes before and after a real Snapshot run.

## 6. Schema discovery

PyArrow supplies exact source column order and physical dtypes. Every requested
annual file must have the same ordered `(column, dtype)` signature; drift is a
hard error. 2025 has 155 columns: the two keys, 152 catalog features, and the
unproven `ind_ret_60d` column. Source feature values are precomputed but not the
training-time MAD/Z-score representation.

## 7. Column roles

Roles are `key`, `feature`, `label`, `metadata`, `weight`, `forbidden`, and
`unknown`. `symbol` and `trade_date` are keys. Catalog membership proves the
152 research features. `label`, `weight`, `split`, and `year` are recognized
only when present because the production training contract evidences those
roles. Reserved target/future-return names are forbidden. Everything else,
including 2025 `ind_ret_60d`, is unknown and inaccessible.

## 8. Label/leakage boundary

`FeatureAccessPolicy` makes keys plus `research_features` the default view.
Labels require both `include_labels=true` at materialization and the explicit
`load_labels` reader. Weight, forbidden, metadata, and unknown columns cannot be
requested as features. The real 2025 source contains zero evidenced label
columns, so the real Snapshot contains zero labels.

## 9. Request

`LegacyFeatureRequest` binds source ID, ordered unique years, inclusive dates,
explicit symbols or a deterministic symbol limit, feature columns, and an
explicit label flag that defaults false. Empty columns means the catalog
allowlist, never all source columns. Symbols and symbol limit are mutually
exclusive.

## 10. Inventory

`LegacyFeatureInventory` records source and loader identity, schema version,
relative filename, year, size, exact SHA-256, row count, ordered column names,
dtypes, date bounds, and symbol count. It never records the binding's absolute
root.

## 11. Error handling

Missing roots/files produce safe provider-unavailable errors. Invalid logical
identities, source mismatch, duplicate years, symlink/path escape, denied
columns, empty results, schema drift, quality errors, identity mismatch, file
corruption, and source-byte drift are explicit failures. No error falls back to
Fake data or another directory.

## 12. Limitations

The catalog is file-backed in this offline task; the active database allowlist
was not queried. Only annual files with identical ordered schemas can be read in
one request. Industry/style semantics are not evidenced in the 2025 source.
Large-scale scheduling and partitioning are deferred. Existing training still
reads the legacy annual files directly, and Qlib still reads its binary view.

