# Market Data Reality Audit v1

## 1. Current production data sources

QuantMind does not currently have one authoritative market-data source. The
active and code-present paths are:

1. The OSS administration/data tasks describe official-server or remote
   PostgreSQL delivery into local Parquet and `stock_daily_latest`.
   `sync_stock_daily_latest_task` and its Baostock endpoint are explicitly
   deprecated. `sync_market_data_daily_task` calls
   `sync_parquets_from_remote_pg.py` and subsequent maintenance scripts.
2. Model training reads yearly files such as
   `db/feature_snapshots/model_features_YYYY.parquet`. The Docker orchestrator
   mounts that directory; `docker/training/train.py` requires local Parquet.
3. Qlib backtest initializes from `QLIB_DATA_PATH`, defaulting to
   `db/qlib_data`, and reads calendar/instruments/features through Qlib.
4. The v2 rebuild scripts read CSMAR files and local fundamental Parquet to
   produce silver and feature snapshots. These scripts are rebuild tooling,
   not a Dataset Snapshot authority.
5. Three legacy scripts call a proprietary `tqcenter.tq` wrapper and label it
   TongDaXin. The wrapper is absent from the repository and both inspected
   Python environments.

Production training and backtest therefore do not consume one source version.
PostgreSQL, local Parquet and Qlib binary can diverge.

## 2. Current data flow

Code-backed active/available flows are:

```text
official/remote PostgreSQL
-> sync_parquets_from_remote_pg.py
-> local Parquet / stock_daily_latest maintenance
-> feature snapshots
-> docker/training/train.py
-> LightGBM artifacts
```

```text
local Parquet or conversion scripts
-> db/qlib_data binary
-> Qlib Calendar/Instrument/Feature provider
-> QlibBacktestService
```

```text
CSMAR/local fundamental Parquet
-> build_silver_market.py
-> build_feature_snapshots.py
-> yearly model_features Parquet
```

The `full_update.py` TQ flow and corporate-action script exist as standalone
legacy scripts; no service/task wiring was found that makes them the current
production path. `scripts/市场数据到redis.py` is a separate quote-push script,
not the historical daily-bar authority.

## 3. Actual TongDaXin capability

The evidenced client is neither pytdx nor mootdx. Legacy scripts add their own
directory to `sys.path` and execute `from tqcenter import tq`. They call:

- `tq.initialize(source_file)` / `tq.close()`;
- `get_market_data(stock_list, period='1d', start_time, end_time,
  dividend_type, fill_data)`;
- `get_stock_list`, `get_trading_dates`, snapshots and dividend factors.

Observed daily response fields are `Open`, `High`, `Low`, `Close`, `Volume`,
`Amount`, and sometimes `ForwardFactor`. Observed adjustments are `none` and
`front`; backward adjustment is not evidenced. The scripts contain broad
exception handling and, in places, silent continuation. No contractual
timeout, rate limit, license text, retry policy for daily bars, or canonical
volume/amount unit declaration was found.

Current runtime probe is unavailable because:

- `tqcenter` is not installed or vendored;
- pytdx and mootdx are absent;
- no local TongDaXin `vipdoc`/client data root was found;
- canonical units have not been configured or evidenced.

The new adapter therefore reports unavailable safely. It requires an actual
`tqcenter` client plus explicit `share` and `CNY` unit assertions before fetch.
It does not print credentials or claim a successful connection.

## 4. Existing libraries and clients

Inspected project venv: pandas 2.3.3, pyarrow 24.0.0, qlib 0.9.7, Baostock and
AkShare are importable. `pytdx`, `mootdx`, `tqcenter`, `xtquant`, `polars` and
Tushare are unavailable. No dependency was installed by this task.

Baostock appears in deprecated synchronization paths. AkShare/Tushare appear
in configuration, AI IDE or placeholder/adaptor code and are not promoted to
the Dataset Snapshot source by this task.

## 5. Existing data directories

The repository checkout contains an effectively empty `db/` and no local
`db/qlib_data` or `db/feature_snapshots` dataset. Production model artifacts
exist under `models/production`, including Alpha158 binaries and prediction
files, but these are model artifacts rather than authoritative raw data.

No local TongDaXin data directory was identified. Home-level application data
was inspected only by aggregate path/count/size, never by large-file content.

## 6. Data domains

| Domain | Current evidence |
|---|---|
| Daily OHLCV/amount | Multiple scripts/tables/Parquet/Qlib paths exist |
| Adjustment factor | CSMAR/fundamental and TQ legacy code exist; authority differs |
| Suspension | Some CSMAR trade-status fields; no unified contract |
| Price limits | Training derives board thresholds heuristically; no authoritative daily field |
| Turnover | CSMAR/rebuild and feature paths exist |
| Stock basic/listing/delisting | Partial source/config/scripts; no PIT authority |
| Trading calendar | Qlib calendar and TQ legacy method; no Dataset Calendar Snapshot |
| Industry/financial | CSMAR/feature inputs exist; not unified |
| Index constituents | Local files/fields and Qlib instruments; version authority absent |
| ST status | Latest-table/feature usage exists; PIT authority absent |

## 7. Adjustment semantics

Training expects raw `open`/`close` plus `factor` and constructs adjusted
future prices. CSMAR silver code emits raw and adjusted fields. Legacy TQ code
requests both front-adjusted and none data. These semantics are not one shared
contract. Dataset Snapshot v1 requires an explicit adjustment mode and never
infers it. The TQ adapter exposes only `none` and `forward` as evidenced.

## 8. Calendar

Qlib owns a consumer calendar inside its binary view. It is not a Dataset
Snapshot authority. Snapshot v1 records `weekday-only-unverified-v1`; weekday
gaps and weekend rows are warnings until a formal Calendar Snapshot exists.

## 9. Universe

The first slice accepts only explicit symbols and records
`explicit-symbols-v1`. It does not auto-select all A-shares or use today's
listing set as a historical universe.

## 10. Qlib input

`QlibBacktestService` defaults to `db/qlib_data`, calls `qlib.init`, then uses
`D.features`. Conversion scripts can delete/recreate that destination and are
not atomic. Qlib binary remains a derived consumer view, not the new authority.

## 11. Known duplication and gaps

- Remote PostgreSQL, `stock_daily_latest`, Parquet, CSMAR silver, feature
  snapshots, model-local loaders and Qlib binary overlap.
- Daily task/admin code refers to a Qlib synchronization script not present at
  the referenced location.
- Training and Qlib backtest are not bound to one immutable input identity.
- Units, PIT listing/universe, corporate actions, ST and calendar versioning
  are incomplete.

## 12. Chosen v1 path

The implemented path is explicit Provider request -> immutable Raw Capture ->
deterministic normalization -> quality gate -> immutable Parquet Dataset
Snapshot -> read-only consumer seam. Prefix symbols (`SH600000`) follow the
repository's mandatory internal convention. A future Qlib adapter must derive
from a Snapshot.

## 13. Rejected alternatives

- Qlib binary as authority: rejected because it is a rebuildable consumer view.
- Existing feature snapshots as raw authority: rejected because they mix
  feature/materialization semantics and lack raw lineage.
- pytdx/mootdx implementation: rejected because neither is installed or
  evidenced as the current client.
- CSV final Snapshot fallback: rejected because pyarrow is available and the
  contract requires Parquet.
- Fake data as real TDX proof: rejected; Fake is marked and test-only.

## 14. Evidence

Principal evidence paths include `docker/training/train.py`,
`local_docker_orchestrator.py`, `QlibBacktestService`, daily Celery tasks,
remote-PG maintenance scripts, CSMAR rebuild scripts, `full_update.py`,
`fetch_corporate_actions.py`, `市场数据到redis.py`, existing requirements,
installed-module probes and aggregate local-data directory checks.
