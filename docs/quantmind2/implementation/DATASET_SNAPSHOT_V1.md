# Dataset Snapshot v1

## 1. Authority model

Provider Raw Data, normalized Dataset Snapshot and Qlib Consumer View are
different artifacts. Dataset Snapshot is the authoritative immutable research
dataset version. Provider payload is lineage evidence; Qlib binary is a
rebuildable view.

## 2. Provider contract and daily request

`MarketDataProvider` exposes `probe()` and `fetch_daily_bars(request)` only. It
does not choose a universe, fill history, write a Snapshot or touch Qlib.
`DailyBarsRequest` requires explicit symbols, inclusive dates, `1d`, fixed v1
fields and adjustment mode. Unsupported frequency/schema/date/symbol inputs
fail before provider access.

## 3. Symbol convention

Internal identity is the repository-mandated uppercase prefix form:
`SH600000`, `SZ000001`, `BJ430001`. Suffix input may be normalized at the
boundary. TQ calls receive suffix form only inside the adapter.

## 4. Daily bar schema and units

Fixed order and logical types:

| Column | Type | Unit |
|---|---|---|
| symbol | string | uppercase-prefix-v1 |
| trade_date | date32 | civil date, no time |
| open/high/low/close | float64 | CNY/share |
| volume | float64 | share |
| amount | float64 | CNY |

`symbol + trade_date` is unique. Providers whose units are unknown cannot be
normalized. There is no silent conversion between hands/shares or currency
scales.

## 5. Adjustment

Mode is one of `none`, `forward`, `backward`, but a provider advertises only
evidenced support. The current TQ adapter advertises none/forward; backward
hard-fails. One Snapshot contains exactly one mode. No price-based inference or
hidden adjustment is allowed.

## 6. Raw capture

Layout:

```text
<root>/raw/<provider_id>/<ingest_id>/
  request.json
  provider_metadata.json
  raw_response.json
  raw_sha256.json
```

The ingest ID binds provider/version, normalized request and exact response
hash. Capture is assembled in a sibling staging directory and atomically
renamed. Existing identical capture is reused; conflicting content hard-fails.
Credentials, tokens, database URLs and absolute source paths are excluded.

## 7. Normalization

Normalization v1 is deterministic and offline. It validates exact provider
schema and units, normalizes symbols/dates/numbers, rejects NaN/Infinity and
duplicate keys, and stable-sorts by `symbol, trade_date`. It never fills prices,
creates suspension bars, drops invalid rows silently or infers adjustment.

## 8. Snapshot identity

ID is `ds_` plus SHA-256 of canonical identity JSON. Canonical JSON uses UTF-8,
sorted keys, compact separators, preserved array order and nulls, and rejects
NaN/Infinity. Request symbols are normalized/sorted before identity.

Identity includes Schema/provider versions, request/adjustment, symbol format,
field schema, units, normalization version, raw response hashes and final
Parquet hashes. It excludes Snapshot ID, created time and local absolute path.

## 9. Manifest and storage layout

```text
<root>/snapshots/<snapshot_id>/
  manifest.json
  schema.json
  quality.json
  partitions/daily_bars/part-00000.parquet
```

Manifest records provider, request, date range, calendar/universe IDs, units,
rows/symbols/partitions, raw lineage, file hashes, quality summary and identity
payload. No credentials are permitted.

## 10. Parquet and atomicity

Parquet uses pyarrow, fixed column order, no DataFrame index, zstd compression
and stable row ordering. All files are written and validated in a staging
directory, then atomically renamed. Failure removes staging. A completed
Snapshot has no update/append operation.

## 11. Quality

Errors include empty results, duplicate key, non-finite values, out-of-range
dates, invalid OHLC, negative volume/amount and missing requested symbols.
Errors block publication. Warnings include weekday gaps and weekend records
while calendar authority is unavailable. Every issue is written to
`quality.json` with severity and count.

## 12. Immutability, replay and validation

Same semantics and bytes produce the same ID and return `existing`. Different
request, adjustment, provider version, raw bytes or Parquet bytes produce a
different ID. Validation recomputes identity and file hashes, reads Parquet,
and reconciles row/symbol counts and quality.

## 13. Real vertical slice

The real TQ slice is not completed in QM2-P0-003 because `tqcenter` and explicit
source-unit evidence are unavailable. No Fake Snapshot is represented as real.
The deterministic Fake path completes all storage and validation behavior and
is always marked `provider_id=fake`.

## 14. Existing QuantMind seam

`load_daily_bars(output_root, snapshot_id, symbols=None, date_range=None)`
validates then reads Snapshot Parquet without contacting a Provider or mutating
the Snapshot. It returns the fixed DataFrame schema suitable for future Factor
DSL and Qlib adapter work. Existing LightGBM training and production backtests
have not been switched.

## 15. Deferred calendar/universe and other domains

Formal Calendar Snapshot, PIT Universe, listing/delisting, corporate actions,
ST, limits, suspension, industry, finance and index membership remain separate
future work. `weekday-only-unverified-v1` and `explicit-symbols-v1` make those
limitations visible.

## 16. Handoff

Because the real TQ environment is unavailable, the next bounded task is
`QM2-P0-003F — TongDaXin Environment Enablement and Real Snapshot Verification`.
Only after the real slice passes should production pipeline and Qlib consumer
view work proceed.
