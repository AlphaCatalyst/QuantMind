# Implementation Report: QM2-P0-003L — Legacy Feature Parquet Provider and Real Dataset Snapshot

## Task Summary

Completed the read-only legacy feature source binding, schema/role audit,
deterministic real-data filtering, immutable Snapshot publication, safe consumer
interfaces, production-loader parity, CLI, documentation, tests, and project
handoff. A real 2025 feature Snapshot was created outside Git and validated.

## Goal

Establish the real path `production annual feature Parquet -> explicit read-only
binding -> LegacyFeatureProvider -> quality gate -> immutable Dataset Snapshot
-> safe feature reader -> Factor DSL input boundary` without changing existing
training, LightGBM, Qlib, or Factor Lab behavior.

## Scope

- Audit the actual production training loader and annual feature files.
- Add typed binding/request/schema/inventory/batch and leakage policy objects.
- Add read-only Provider, deterministic selection, quality, Snapshot and readers.
- Add CLI, fixture/real tests, production-loader parity and source-drift checks.
- Add Provider/Snapshot contracts, Project Memory, and this Manifest v2 Run.

## Explicit Non-goals

- No Factor DSL, optimization, Registry, model, signal, backtest, API, or UI.
- No LightGBM, training or Qlib consumer switch and no feature/label recompute.
- No TDX installation/access, production database, dependency, lock or config.
- No Ledger domain/persistence/migration/repository or Factor Lab modification.

## Preflight State

- Repository ID: `quantmind-main`
- Root: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`
- Base: `7d29df7b45b6a49d2526e182c6b2d36e8c2d2f34`
- Dirty before: no; unrelated dirty files: none.
- Factor Lab digest before: `f8986f2787f330b4af02d0ea1bd8e944c3f847230c69ec8979d900f07a4f2635`.
- System Python 3.9.6 had pandas 2.3.3 but no pyarrow/polars/qlib.
  An existing allowed QuantMind environment supplied pandas 2.3.3, pyarrow
  24.0.0 and qlib 0.9.7. No dependency was installed.

## Production Training Loader Reality

`backend/services/engine/training/local_docker_orchestrator.py` read-only mounts
the configured feature root at `/tmp/feature_snapshots` and invokes the mounted
`docker/training/train.py`. `_load_local_parquet` resolves
`model_features_<year>.parquet`; `load_data` loads all years from the year before
training start (bounded at 2016) through the largest end year. Keys are
`symbol, trade_date`; features come from the configured allowlist. The annual
files contain neither the training label nor sample weight. `load_data` creates
the T+H tradable-return label and soft weight, applies cross-sectional MAD and
Z-score, drops missing-label rows and uses explicit time splits or `val_ratio`.
The declared `label_formula` is not executable authority.

The default bound source has 2016–2026 annual files. 2025 is the latest complete
year: 1,160,044,834 bytes, 1,248,108 rows, 5,212 symbols, 243 dates, 155 columns,
SHA-256 `7fd0316e6f8d936688ef332357fb7589f64c0e127c5f64e3158c584baf28b00f`.
2026 is partial through 2026-06-24 and has 154 columns. The adjacent 2025
sidecar describes older bytes; direct Parquet hashing is authoritative.

## What Changed

- Added `LegacyFeatureSourceBinding`, `LegacyFeatureRequest`, column roles,
  schema, inventory, probe, batch and access policy.
- Added a read-only PyArrow Provider with exact annual discovery/hash, bounded
  batch scans, path confinement, allowlist enforcement and stable filtering.
- Added blocking/warning feature quality evidence without repairs.
- Added immutable atomic zstd Parquet Snapshot creation, deterministic identity,
  exact-existing, internal/source-lineage validation and safe readers.
- Added `legacy-audit`, `legacy-probe`, `legacy-snapshot`, `legacy-validate` and
  `legacy-inspect` commands with an optional explicit catalog path.
- Added fixture and opt-in real integration tests, documentation and current
  Project Memory. Context schemas now permit the exact QM2-P0-004 handoff.

## Important Classes and Functions

- `ColumnRole`, `FeatureAccessPolicy`, `LegacyFeatureSourceBinding`
- `LegacyFeatureRequest`, `LegacyFeatureSchema`, `LegacyFeatureInventory`
- `LegacyFeatureProvider.probe`, `.discover`, `.read`
- `evaluate_feature_matrix`
- `LegacyFeatureSnapshotService.create`, `.validate`
- `load_feature_matrix`, `load_labels`
- `tools/quantmind2/market_data.py:main`

## Runtime Flow

```text
explicit logical binding + year/date/symbol/column request
-> probe and exact source inventory
-> allowlist/role gate
-> bounded read and stable row selection
-> blocking quality gate
-> staged fixed-schema zstd Parquet and metadata
-> canonical identity validation
-> atomic publish or exact-existing
-> validated feature-only or explicit-label reader
```

## Real Snapshot Evidence

- Logical source: `quantmind-production-feature-snapshots-v1`
- Loader: `docker-training-load-local-parquet-v1`
- Source: year 2025, dates 2025-01-02..2025-12-31, 5,212 symbols,
  source SHA-256 `7fd0316e6f8d936688ef332357fb7589f64c0e127c5f64e3158c584baf28b00f`.
- Filter: 2025-01-02..2025-04-03, first 100 lexicographically sorted available
  symbols, all 152 catalog research features, labels excluded.
- Snapshot ID: `ds_bc82e7bb2c63d2c47677b11cf0f4fc1e5aa11a0ed18ee0bb27e3c8ab667d2ee7`.
- Result: 5,931 rows, 100 symbols, 60 observed dates, 152 features, 0 labels,
  0 quality errors, 6 warnings.
- Parquet: 6,364,318 bytes, SHA-256
  `8b42dc29e3265e7bc127a921a76f772b3feec78cca1df2d298b3736ae8d04548`.
- Manifest: 90,231 bytes, SHA-256
  `cc7951aa5c777b74396bbcf90cb410e7cd0c2b5f21ea484609583e50f4ebed79`.
- Repeated creation returned `existing`; source-lineage validation passed; no
  absolute source root appeared in manifest identity or metadata.
- Source hash before and after was identical. Runtime Snapshot remains under
  `/tmp` and was not added to Git.

## Loader Parity

The opt-in real test calls the unchanged production `_load_local_parquet`, the
Provider and the Snapshot reader on the same slice. Row counts, keys, column
order, representative values, NaN masks, date/symbol bounds and label isolation
match. Provider-to-Snapshot comparison is exact at source dtype. Production
loader comparison explicitly casts source numeric columns to float32 because
that loader does so; equality and NaN masks are then exact. No broad tolerance
or silent difference exists.

## Architecture Impact

This advances `quantmind.feature_snapshots` and `quantmind2.data_foundation`
within their existing `partial` state. It supplies a real Factor DSL input
without making annual feature Parquet raw bars or changing ADRs. Dataset
Snapshot remains authority; Qlib remains a downstream view. Future TDX adds a
Provider and Daily Bars Snapshot under the same immutable contract.

## API, Database and Configuration Changes

No endpoint, database table/migration, production configuration, environment
contract, dependency, or lockfile changed. The CLI is a local offline tool.

## Security and Leakage Impact

Manifest identity excludes absolute roots. Errors are safe. Ordinary readers
cannot expose label, weight, metadata, forbidden, or unknown columns. No secret,
credential, database URL, feature values, or large source artifact entered Git.

## Data Lineage Impact

The Snapshot binds exact source bytes, logical source/loader, full ordered source
schema/dtypes/roles, filter and selected symbols, access policy, included
features/labels, output schema, Parquet hash, quality and identity. Training,
model, signal and Qlib backtest lineage are unchanged and not claimed.

## Tests Executed and Results

- Full market-data regression: 55 passed and 1 real-TDX test skipped because
  the proprietary runtime and explicit units remain unavailable.
- Opt-in real 2025 source and production-loader parity: 1 passed.
- Context/Project Knowledge regression: 363 passed, 7 opt-in PostgreSQL tests
  skipped, and 247 subtests passed.
- Context bootstrap: 38 checks passed. Manifest v2 production validation built
  all 11 Domain families. JSON, py_compile, diff, scope, source hash and Factor
  Lab digest checks passed.

## Known Limitations

- Real TDX remains unavailable; no real TDX Daily Bars Snapshot exists.
- The file catalog, not the unqueried active PostgreSQL catalog, supplies the
  152-feature allowlist in this offline task.
- Multi-year requests require identical ordered schema/dtypes; 2026 differs.
- The 2025 source sidecar is stale relative to the current Parquet bytes.
- The bounded Snapshot is runtime evidence, not committed/production storage.
- Existing training and Qlib have not switched to this Snapshot.
- Calendar/PIT universe, production partitioning/scheduling, API and UI remain
  deferred.

## Compatibility and Rollback

Daily Bars Snapshot behavior remains unchanged. Existing training and Qlib
paths are untouched. Rollback is the single task commit; the runtime `/tmp`
Snapshot may be removed independently because it is evidence, not a consumer
dependency. Source annual Parquet is read-only and unchanged.

## Remaining Work and Recommended Next Task

Only `QM2-P0-004 — Factor DSL v1 on Real Legacy Feature Dataset Snapshot` is
recommended. It must consume the documented feature-only Snapshot contract.

## Git / Workspace State

One independent commit is required with message
`feat(qm2): add legacy feature snapshot provider`; no amend or push. Final
post-commit verification must leave the worktree clean.

## Artifact Index

- `docs/quantmind2/implementation/LEGACY_FEATURE_PROVIDER_V1.md`
- `docs/quantmind2/implementation/LEGACY_FEATURE_DATASET_SNAPSHOT_V1.md`
- this report and sibling Manifest v2
- runtime real Snapshot URI represented only as test evidence in the Manifest
