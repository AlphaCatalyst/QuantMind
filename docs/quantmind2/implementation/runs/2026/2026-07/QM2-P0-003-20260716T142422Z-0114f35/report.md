# Implementation Report: QM2-P0-003 — TongDaXin Provider Reality Audit and Dataset Snapshot Entry

## Task Summary

Completed the code-backed market-data reality audit and implemented the first
immutable Dataset Snapshot vertical slice. The result is partial because the
authorized proprietary TongDaXin client and explicit source-unit contract are
not available, so no real TongDaXin data was fetched or represented as tested.

## Goal

Establish the bounded path `Explicit Request -> Provider -> immutable Raw
Capture -> deterministic Normalization -> Quality Gate -> immutable Parquet
Dataset Snapshot -> Validation -> read-only Consumer` without switching any
existing production consumer.

## Scope

- Audit existing market-data, feature-training, Alpha158 and Qlib paths.
- Add daily-bar request/provider contracts, TQ adapter and deterministic Fake.
- Add raw evidence, normalization, quality, Snapshot identity/publication,
  validation, filtered reader and CLI.
- Add bounded tests, documentation, Project Memory and this Manifest v2 Run.

## Explicit Non-goals

- No dependency installation, lockfile/config change or production database.
- No production ingestion, Qlib binary generation or training/backtest switch.
- No Factor DSL, optimization, validation, Registry, LightGBM or Qlib redesign.
- No calendar/universe/finance/industry domain implementation.
- No modification to Factor Lab or existing Ledger domain/persistence/indexing.

## Preflight State

- Repository ID: `quantmind-main`
- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`
- Base commit: `0114f35332073cab00928f753af83c9ba8d83b6a`
- Dirty before: no
- Unrelated dirty files: none
- Factor Lab source digest before: `f8986f2787f330b4af02d0ea1bd8e944c3f847230c69ec8979d900f07a4f2635`
- Existing reusable Python environment supplied pandas 2.3.3, pyarrow 24.0.0
  and qlib 0.9.7. No package was installed.

## Existing Data Reality

There is no single current authority. Administrative tasks describe remote
PostgreSQL-to-local-Parquet maintenance; training reads yearly
`db/feature_snapshots/model_features_YYYY.parquet`; Qlib backtest independently
initializes from `QLIB_DATA_PATH`/`db/qlib_data`; rebuild scripts use CSMAR and
local fundamental Parquet. Legacy scripts call an absent proprietary
`tqcenter.tq` wrapper. Training and official backtest are therefore not bound
to one immutable source identity.

## TongDaXin Reality

Repository evidence supports only the third-party/proprietary `tqcenter.tq`
wrapper, not pytdx or mootdx. Legacy calls evidence daily fields Open, High,
Low, Close, Volume and Amount, plus none/front adjustment. They do not evidence
backward adjustment, canonical volume/amount units, timeout, retry, rate limit
or license behavior. The probe safely reports unavailable because `tqcenter`
and explicit `share`/`CNY` assertions are absent. Required real-provider tests
were not run.

## What Changed

- Added explicit immutable daily request and provider/probe result models.
- Added repository-prefix symbols and a TQ-only suffix boundary adapter.
- Added deterministic Fake Provider with five injectable fault modes.
- Added atomic immutable Raw Capture and canonical response hashing.
- Added strict offline normalization and blocking/warning quality evidence.
- Added pyarrow/zstd Snapshot staging, deterministic identity, exact-existing,
  collision refusal, metadata/file validation and filtered read-only loading.
- Added audit/probe/snapshot/validate/inspect CLI commands.
- Added audit/contract docs and updated Context, Catalog, Issues, Roadmap and
  Handoff without claiming a production consumer migration.

## Why It Changed

The existing training, maintenance and Qlib paths can diverge and do not expose
one authoritative data identity. This slice establishes a provider-independent
authority boundary while preserving Qlib as a downstream consumer view.

## Important Classes and Functions

- `DailyBarsRequest`, `ProviderProbeResult`, `DailyBarsBatch`
- `MarketDataProvider`
- `TongDaXinProvider`, `FakeMarketDataProvider`
- `normalize_symbol`, `normalize_daily_bars`, `evaluate_daily_bars`
- `capture_raw`, `DatasetSnapshotService.create`,
  `DatasetSnapshotService.validate`, `load_daily_bars`
- `tools/quantmind2/market_data.py:main`

## Runtime Flow

```text
explicit symbols/date/adjustment
-> provider probe/fetch
-> atomic immutable raw response + hashes
-> exact-schema/unit normalization
-> blocking quality gate
-> staged fixed-schema Parquet + metadata
-> canonical identity and validation
-> atomic Snapshot publish or exact-existing
-> validated read-only DataFrame
```

## Dataset Snapshot Identity and Storage

The ID is `ds_` plus SHA-256 of canonical UTF-8 JSON with sorted keys and
compact separators. It binds Schema/provider versions, normalized request,
adjustment, symbol format, field schema, units, normalization version, raw hash
and final Parquet hash; it excludes time and local paths. Publication uses
`<root>/snapshots/<snapshot_id>/` with manifest, schema, quality and zstd
Parquet. Existing content is never appended or updated.

## Fake Runtime Artifact

The bounded runtime slice used provider `fake`, symbols `SH600000` and
`SZ000001`, dates 2026-01-05 through 2026-02-05, adjustment `none`, 48 rows and
zero quality warnings/errors. It produced Snapshot
`ds_ba104a6fb37e452032fac35ead6cd1c6ad223c0d9f76fafb99ac0e3aa0c8cd3f`.
Manifest SHA-256 is
`66205f7b2c125f6e956d6e5d39809b3f5fae129073a20f61a686199a80d19e28`;
Parquet SHA-256 is
`2733b0d5e107beb1d9ba587142142c5c6f80594704fdb7ec836d23ab87890eff`.
The second run returned `existing`. These are Fake-only runtime artifacts, not
real market-data evidence and not committed dataset files.

## Architecture Impact

`quantmind2.data_foundation` moves from planned to partial. Dataset Snapshot is
now the implemented v1 authority contract; existing feature snapshots, model
training and Qlib remain separate consumers. This conforms to ADR-0003 and
does not modify accepted architecture or accepted ADRs.

## API, Database and Configuration Changes

No API endpoint, database table/migration, runtime configuration, dependency
or lockfile changed. The CLI is an offline/local tool. No production service,
Electron, database, Qlib, LightGBM or Factor Lab process was started.

## Security Impact

Probe/fetch errors are safe and do not reveal credentials. Raw/Manifest files
contain explicit provider metadata and hashes but no token, password, database
URL or user-home path. Fake cannot be selected implicitly. No external data or
secret was written to Git.

## Data Lineage Impact

The new lineage binds request, provider/version, raw response hash,
normalization version, field/unit semantics, Parquet hash, quality evidence and
Snapshot ID. It does not yet bind a production Feature Snapshot, model, signal
or Qlib backtest.

## Tests Executed and Results

1. Initial market suite with repository coverage defaults: 30 tests passed and
   1 real-provider test skipped, but command status failed because whole-repo
   coverage was 0.54% below the unrelated 5% threshold. Re-run used `--no-cov`.
2. Final market suite with `--no-cov`: 31 passed, 1 skipped.
3. Fake CLI audit/snapshot/validate/inspect/exact-existing slice: passed.
4. TQ CLI probe: passed as an unavailable safe probe; real fetch/snapshot
   checks remain not-run.
5. Context Bootstrap, Project Knowledge regression, Manifest v2 validation,
   JSON parsing, py_compile, Git diff checks and final Factor Lab digest are
   recorded in the Manifest test entries.

## Expected vs Actual

- Expected provider/Snapshot/Fake vertical contracts: implemented and tested.
- Expected real TDX slice when environment exists: environment absent; not run.
- Expected Snapshot authority without consumer switch: achieved.
- Expected one commit, no push and clean final worktree: verified after commit
  in the final task response; source Run correctly remains pre-commit.

## Known Limitations and Unresolved Questions

- The sole completion blocker is the absent authorized `tqcenter` runtime plus
  unconfirmed volume/amount semantics; no real Snapshot exists.
- Endpoint authorization, timeout, retry, rate-limit and license constraints
  are unconfirmed.
- Formal Calendar Snapshot and point-in-time Universe are absent; weekday gap
  checks are warnings only.
- Suspension, limits, corporate actions, ST, industry, finance and index
  membership are outside this slice.
- Existing feature-training and Qlib consumers have not migrated.
- Storage lifecycle, retention and multi-process publication coordination for
  large production Snapshots remain future concerns.

## Compatibility and Rollback

No current consumer imports this module, so existing LightGBM, inference and
Qlib behavior is unchanged. Roll back the single QM2-P0-003 commit; remove any
non-repository Fake runtime directory if desired. No database, dependency,
configuration, Qlib data or Factor Lab rollback is required.

## Remaining Work and Recommended Next Task

Only `QM2-P0-003F — TongDaXin Environment Enablement and Real Snapshot
Verification` is recommended. It must provide the authorized client and unit
contract, then run the bounded real SH/SZ slice. This task does not start it.

## Git and Workspace State

Manifest v2 records the true source state as `partial_uncommitted`,
`result_commit=null`, dirty after yes and noncanonical. The containing commit
is resolved from Git after the required single commit. No amend or push is
performed.

## Artifact Index

- This Implementation Report and Manifest v2.
- `MARKET_DATA_REALITY_AUDIT_V1.md`
- `DATASET_SNAPSHOT_V1.md`
- Fake Snapshot manifest and Parquet as runtime URI artifacts with exact hashes.
- TestExecution records in the Manifest, including explicit real-TDX not-run.
