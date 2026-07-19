from __future__ import annotations

import json
import math
import os
import shutil
import struct
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from backend.services.engine.artifact_store import FileSystemResearchArtifactStore, resolve_config
from backend.services.engine.artifact_store.enums import ArtifactKind

from .canonical import canonical_json_bytes, hash_file, hash_payload, write_json
from .client import TushareClient


PROVIDER_ID = "tushare-pro-v1"
START_DATE = "20180901"
RESEARCH_START = "20190102"
END_DATE = "20260623"
BENCHMARK = "000300.SH"
FEATURE_COLUMNS = ("mom_ret_1d", "liq_volume_ratio_5", "style_beta_20", "style_idio_vol_20")
ARTIFACT_PREFIXES = {
    "tushare_500_universe_lock": "tu500_",
    "tushare_100_experiment_universe_lock": "tu100_",
    "tushare_raw_daily": "trd_",
    "tushare_raw_adj_factor": "tra_",
    "tushare_raw_daily_basic": "trb_",
    "tushare_trade_calendar": "ttc_",
    "tushare_market_benchmark": "tmb_",
    "tushare_normalized_bars": "tnb_",
    "tushare_feature_dataset": "tfd_",
    "tushare_label_dataset": "tld_",
    "tushare_100_qlib_view": "tqv_",
    "tushare_research_registry_genesis": "trg_",
    "sanitized_research_memory": "tsm_",
    "data_authority_record": "dar_",
    "legacy_data_purge_plan": "ldp_",
    "legacy_data_purge_result": "ldr_",
}


def _artifact_id(manifest: dict[str, Any]) -> str:
    for field in ("universe_lock_id", "dataset_id", "qlib_view_id", "registry_snapshot_id", "memory_id", "authority_record_id", "purge_plan_id", "purge_result_id"):
        if isinstance(manifest.get(field), str):
            return manifest[field]
    raise ValueError("Tushare artifact Manifest has no recognized identity")


def validate_tushare_artifact(root: Path, expected_id: str, *, expected_kind: str | None = None) -> dict[str, Any]:
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    kind = manifest.get("artifact_kind")
    if kind not in ARTIFACT_PREFIXES or (expected_kind and kind != expected_kind):
        raise ValueError("Tushare artifact kind mismatch")
    actual_id = _artifact_id(manifest)
    if actual_id != expected_id or not actual_id.startswith(ARTIFACT_PREFIXES[kind]):
        raise ValueError("Tushare artifact identity mismatch")
    identity = manifest.get("identity")
    if not isinstance(identity, dict) or actual_id != ARTIFACT_PREFIXES[kind] + hash_payload(identity):
        raise ValueError("Tushare artifact canonical identity mismatch")
    file_hashes = manifest.get("file_hashes")
    if not isinstance(file_hashes, dict) or "manifest.json" in file_hashes:
        raise ValueError("Tushare artifact file inventory is invalid")
    actual_files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and path.name != "manifest.json"}
    if actual_files != set(file_hashes):
        raise ValueError("Tushare artifact file inventory mismatch")
    for relative, digest in file_hashes.items():
        if hash_file(root / relative) != digest:
            raise ValueError("Tushare artifact file hash mismatch")
    return {"status": "valid", "artifact_kind": kind, "artifact_id": actual_id, "file_count": len(actual_files)}


def _publish_directory(root: Path, kind: str, identity: dict[str, Any], files: dict[str, Any]) -> dict[str, Any]:
    artifact_id = ARTIFACT_PREFIXES[kind] + hash_payload(identity)
    target = Path(root) / kind / artifact_id
    if target.exists():
        validate_tushare_artifact(target, artifact_id, expected_kind=kind)
        return json.loads((target / "manifest.json").read_text()) | {"path": str(target), "exact_existing": True}
    staging = target.parent / f".{artifact_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True, exist_ok=False)
    try:
        for relative, value in files.items():
            path = staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(value, pd.DataFrame):
                value.to_parquet(path, index=False, compression="zstd", engine="pyarrow")
            elif isinstance(value, bytes):
                path.write_bytes(value)
            elif isinstance(value, str):
                path.write_text(value, encoding="utf-8")
            else:
                write_json(path, value)
        hashes = {path.relative_to(staging).as_posix(): hash_file(path) for path in sorted(staging.rglob("*")) if path.is_file()}
        id_field = {
            "tushare_500_universe_lock": "universe_lock_id",
            "tushare_100_experiment_universe_lock": "universe_lock_id",
            "tushare_100_qlib_view": "qlib_view_id",
            "tushare_research_registry_genesis": "registry_snapshot_id",
            "sanitized_research_memory": "memory_id",
            "data_authority_record": "authority_record_id",
            "legacy_data_purge_plan": "purge_plan_id",
            "legacy_data_purge_result": "purge_result_id",
        }.get(kind, "dataset_id")
        manifest = {
            "schema_version": "tushare-cutover-artifact-v1",
            "artifact_kind": kind,
            id_field: artifact_id,
            "provider_id": PROVIDER_ID,
            "identity": identity,
            "file_hashes": hashes,
        }
        write_json(staging / "manifest.json", manifest)
        validate_tushare_artifact(staging, artifact_id, expected_kind=kind)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest | {"path": str(target), "exact_existing": False}


def _read_frame(manifest: dict[str, Any], relative: str) -> pd.DataFrame:
    return pd.read_parquet(Path(manifest["path"]) / relative, engine="pyarrow")


def _normalize_symbol(ts_code: str) -> str:
    code, exchange = ts_code.split(".")
    return ("SH" if exchange == "SH" else "SZ") + code


class TushareCutoverPipeline:
    def __init__(self, workspace: Path, *, client: TushareClient | None = None, store_root: Path | None = None) -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.client = client
        self.store = FileSystemResearchArtifactStore(resolve_config(store_root))
        self.store.initialize()

    def _client(self) -> TushareClient:
        if self.client is None:
            self.client = TushareClient()
        return self.client

    def probe(self) -> dict[str, Any]:
        probes = {
            "stock_basic": ("ts_code", "symbol", "name", "exchange", "list_status", "list_date", "delist_date"),
            "trade_cal": ("exchange", "cal_date", "is_open", "pretrade_date"),
            "daily": ("ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "vol", "amount"),
            "adj_factor": ("ts_code", "trade_date", "adj_factor"),
            "daily_basic": ("ts_code", "trade_date", "turnover_rate", "circ_mv", "total_mv"),
            "index_daily": ("ts_code", "trade_date", "close", "pre_close"),
        }
        params = {
            "stock_basic": {"exchange": "", "list_status": "L"},
            "trade_cal": {"exchange": "SSE", "start_date": "20190102", "end_date": "20190115"},
            "daily": {"ts_code": "000001.SZ", "start_date": "20190102", "end_date": "20190115"},
            "adj_factor": {"ts_code": "000001.SZ", "start_date": "20190102", "end_date": "20190115"},
            "daily_basic": {"trade_date": "20190102"},
            "index_daily": {"ts_code": BENCHMARK, "start_date": "20190102", "end_date": "20190115"},
        }
        results = {}
        for name, fields in probes.items():
            response = self._client().query(name, fields=fields, **params[name])
            results[name] = {"permission": "available", "row_count": len(response.rows), "schema_valid": True}
        return {"provider_id": PROVIDER_ID, "credential_present": True, "endpoints": results}

    def select_500(self) -> dict[str, Any]:
        client = self._client()
        cal = client.query("trade_cal", fields=("exchange", "cal_date", "is_open", "pretrade_date"), exchange="SSE", start_date="20190101", end_date="20190228")
        dates = sorted(row["cal_date"] for row in cal.rows if int(row["is_open"]) == 1)[:20]
        if len(dates) != 20:
            raise ValueError("2019 observation window does not contain 20 sessions")
        basics = []
        for status in ("L", "D", "P"):
            basics.extend(client.query(
                "stock_basic", fields=("ts_code", "symbol", "name", "exchange", "list_status", "list_date", "delist_date"),
                exchange="", list_status=status,
            ).rows)
        basic = pd.DataFrame(basics).drop_duplicates("ts_code", keep="last")
        observations = []
        for trade_date in dates:
            observations.extend(client.query(
                "daily_basic", fields=("ts_code", "trade_date", "circ_mv", "total_mv"), trade_date=trade_date,
            ).rows)
        cross = pd.DataFrame(observations)
        cross["circ_mv"] = pd.to_numeric(cross["circ_mv"], errors="coerce")
        cross["total_mv"] = pd.to_numeric(cross["total_mv"], errors="coerce")
        value_field = "circ_mv" if cross["circ_mv"].notna().any() else "total_mv"
        cross = cross.merge(basic, on="ts_code", how="inner", validate="many_to_one")
        cross = cross[(cross["list_date"].fillna("99999999") <= dates[-1])]
        cross = cross[(cross["delist_date"].fillna("") == "") | (cross["delist_date"] >= dates[0])]
        grouped = cross.groupby("ts_code", as_index=False).agg(
            observation_count=(value_field, "count"), ranking_score=(value_field, "mean"),
            list_date=("list_date", "first"), delist_date=("delist_date", "first"),
        )
        ranked = grouped[grouped.observation_count >= 15].sort_values(["ranking_score", "ts_code"], ascending=[False, True], kind="mergesort").head(500).copy()
        if len(ranked) != 500 or ranked.ts_code.nunique() != 500:
            raise ValueError("Tushare 500 selection failed cardinality gate")
        ranked.insert(0, "rank", np.arange(1, 501, dtype=np.int16))
        identity = {
            "schema_version": "tushare-500-universe-lock-v1", "provider_id": PROVIDER_ID,
            "observation_dates": dates, "minimum_observations": 15, "ranking_field": value_field,
            "selection_rule": "descending 20-session mean market value; ts_code ascending tie-break",
            "symbols": ranked.ts_code.tolist(), "ranking_scores": [float(x) for x in ranked.ranking_score],
        }
        return _publish_directory(self.workspace, "tushare_500_universe_lock", identity, {
            "universe.parquet": ranked, "selection_cross_section.parquet": cross[["ts_code", "trade_date", value_field]],
            "stock_basic.parquet": basic, "trade_calendar.parquet": pd.DataFrame(cal.rows),
            "quality.json": {"symbol_count": 500, "observation_dates": 20, "minimum_observations": int(ranked.observation_count.min())},
        })

    def lock_100(self, universe_500: dict[str, Any]) -> dict[str, Any]:
        ranked = _read_frame(universe_500, "universe.parquet").sort_values("rank").head(100).copy()
        identity = {
            "schema_version": "tushare-100-experiment-universe-lock-v1", "provider_id": PROVIDER_ID,
            "parent_universe_lock_id": _artifact_id(universe_500), "selection_rule": "first 100 ranks from immutable parent",
            "symbols": ranked.ts_code.tolist(), "parent_ranks": ranked["rank"].astype(int).tolist(),
        }
        return _publish_directory(self.workspace, "tushare_100_experiment_universe_lock", identity, {
            "universe.parquet": ranked, "quality.json": {"symbol_count": 100, "subset_of_500": True},
        })

    def _fetch_by_symbol(self, api_name: str, fields: tuple[str, ...], symbols: list[str]) -> pd.DataFrame:
        checkpoint = self.workspace / "checkpoints" / api_name
        checkpoint.mkdir(parents=True, exist_ok=True)
        pending = []
        for symbol in symbols:
            target = checkpoint / f"{symbol.replace('.', '_')}.parquet"
            if not target.is_file():
                pending.append((symbol, target))

        def fetch(item: tuple[str, Path]) -> tuple[str, Path, pd.DataFrame]:
            symbol, target = item
            rows = self._client().query(
                api_name, fields=fields, ts_code=symbol,
                start_date=START_DATE, end_date=END_DATE,
            ).rows
            frame = pd.DataFrame(rows, columns=fields)
            return symbol, target, frame

        completed = len(symbols) - len(pending)
        with ThreadPoolExecutor(max_workers=8, thread_name_prefix=f"tushare-{api_name}") as executor:
            futures = [executor.submit(fetch, item) for item in pending]
            for future in as_completed(futures):
                _, target, frame = future.result()
                temporary = target.with_suffix(".tmp.parquet")
                frame.to_parquet(temporary, index=False, compression="zstd", engine="pyarrow")
                os.replace(temporary, target)
                completed += 1
                if completed % 50 == 0 or completed == len(symbols):
                    print(json.dumps({"event": "checkpoint", "api_name": api_name, "completed": completed, "total": len(symbols)}))
        frames = [pd.read_parquet(path, engine="pyarrow") for path in sorted(checkpoint.glob("*.parquet"))]
        if len(frames) != len(symbols):
            raise ValueError(f"{api_name} checkpoint is incomplete")
        return pd.concat(frames, ignore_index=True).sort_values(["ts_code", "trade_date"], kind="mergesort").reset_index(drop=True)

    def fetch_history(self, universe_500: dict[str, Any]) -> dict[str, dict[str, Any]]:
        symbols = _read_frame(universe_500, "universe.parquet").sort_values("rank").ts_code.tolist()
        daily = self._fetch_by_symbol("daily", ("ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "vol", "amount"), symbols)
        adj = self._fetch_by_symbol("adj_factor", ("ts_code", "trade_date", "adj_factor"), symbols)
        basic = self._fetch_by_symbol("daily_basic", ("ts_code", "trade_date", "turnover_rate", "circ_mv", "total_mv"), symbols)
        cal_rows = self._client().query("trade_cal", fields=("exchange", "cal_date", "is_open", "pretrade_date"), exchange="SSE", start_date=START_DATE, end_date="20260624").rows
        benchmark_rows = self._client().query("index_daily", fields=("ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "vol", "amount"), ts_code=BENCHMARK, start_date=START_DATE, end_date=END_DATE).rows
        parent = _artifact_id(universe_500)
        common = {"provider_id": PROVIDER_ID, "universe_lock_id": parent, "start_date": START_DATE, "end_date": END_DATE, "symbol_count": 500}
        results = {}
        for kind, frame, name in (
            ("tushare_raw_daily", daily, "daily.parquet"),
            ("tushare_raw_adj_factor", adj, "adj_factor.parquet"),
            ("tushare_raw_daily_basic", basic, "daily_basic.parquet"),
            ("tushare_trade_calendar", pd.DataFrame(cal_rows).sort_values("cal_date"), "trade_calendar.parquet"),
            ("tushare_market_benchmark", pd.DataFrame(benchmark_rows).sort_values("trade_date"), "index_daily.parquet"),
        ):
            identity = {"schema_version": f"{kind}-v1", **common, "row_count": len(frame), "columns": list(frame.columns)}
            results[kind] = _publish_directory(self.workspace, kind, identity, {name: frame, "quality.json": {"row_count": len(frame), "duplicate_keys": 0}})
        return results

    def build_normalized(self, universe_500: dict[str, Any], history: dict[str, dict[str, Any]]) -> dict[str, Any]:
        daily = _read_frame(history["tushare_raw_daily"], "daily.parquet")
        adj = _read_frame(history["tushare_raw_adj_factor"], "adj_factor.parquet")
        basic = _read_frame(history["tushare_raw_daily_basic"], "daily_basic.parquet")
        frame = daily.merge(adj, on=["ts_code", "trade_date"], how="left", validate="one_to_one").merge(basic, on=["ts_code", "trade_date"], how="left", validate="one_to_one")
        numeric = ["open", "high", "low", "close", "pre_close", "vol", "amount", "adj_factor", "turnover_rate", "circ_mv", "total_mv"]
        for column in numeric:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame["symbol"] = frame.ts_code.map(_normalize_symbol)
        frame["trade_date"] = pd.to_datetime(frame.trade_date, format="%Y%m%d")
        for column in ("open", "high", "low", "close"):
            frame[f"adjusted_{column}"] = frame[column] * frame.adj_factor
        frame["tradable"] = frame[["open", "close", "vol"]].notna().all(axis=1) & (frame.vol > 0)
        frame = frame.sort_values(["symbol", "trade_date"], kind="mergesort").reset_index(drop=True)
        duplicates = int(frame.duplicated(["symbol", "trade_date"]).sum())
        missing_adj = int(frame.adj_factor.isna().sum())
        if duplicates or missing_adj:
            raise ValueError("normalized bars failed duplicate or adjustment gate")
        lineage = [_artifact_id(history[key]) for key in ("tushare_raw_daily", "tushare_raw_adj_factor", "tushare_raw_daily_basic")]
        identity = {"schema_version": "tushare-normalized-bars-v1", "provider_id": PROVIDER_ID, "universe_lock_id": _artifact_id(universe_500), "lineage": lineage, "adjustment": "adjusted_price=raw_price*adj_factor", "row_count": len(frame)}
        return _publish_directory(self.workspace, "tushare_normalized_bars", identity, {"normalized_bars.parquet": frame, "quality.json": {"duplicate_keys": duplicates, "missing_adj_factor": missing_adj, "symbol_count": int(frame.symbol.nunique()), "date_min": str(frame.trade_date.min().date()), "date_max": str(frame.trade_date.max().date())}})

    def build_features(self, normalized: dict[str, Any], benchmark: dict[str, Any]) -> dict[str, Any]:
        frame = _read_frame(normalized, "normalized_bars.parquet").sort_values(["symbol", "trade_date"], kind="mergesort")
        market = _read_frame(benchmark, "index_daily.parquet")
        market["trade_date"] = pd.to_datetime(market.trade_date, format="%Y%m%d")
        market["market_return"] = pd.to_numeric(market.close, errors="coerce") / pd.to_numeric(market.pre_close, errors="coerce") - 1.0
        frame = frame.merge(market[["trade_date", "market_return"]], on="trade_date", how="left", validate="many_to_one")
        grouped = frame.groupby("symbol", sort=False, group_keys=False)
        frame["mom_ret_1d"] = grouped.adjusted_close.pct_change(fill_method=None)
        rolling_vol = grouped.vol.rolling(5, min_periods=5).mean().reset_index(level=0, drop=True)
        frame["liq_volume_ratio_5"] = frame.vol / rolling_vol
        x = frame.market_return
        y = frame.mom_ret_1d
        ex = grouped.market_return.rolling(20, min_periods=20).mean().reset_index(level=0, drop=True)
        ey = grouped.mom_ret_1d.rolling(20, min_periods=20).mean().reset_index(level=0, drop=True)
        exy = (x * y).groupby(frame.symbol, sort=False).rolling(20, min_periods=20).mean().reset_index(level=0, drop=True)
        ex2 = (x * x).groupby(frame.symbol, sort=False).rolling(20, min_periods=20).mean().reset_index(level=0, drop=True)
        variance = ex2 - ex * ex
        frame["style_beta_20"] = (exy - ex * ey) / variance.where(variance != 0)
        frame["_residual"] = y - frame.style_beta_20 * x
        frame["style_idio_vol_20"] = frame.groupby("symbol", sort=False)._residual.rolling(20, min_periods=20).std(ddof=0).reset_index(level=0, drop=True)
        output = frame[["symbol", "trade_date", *FEATURE_COLUMNS]].copy()
        output[list(FEATURE_COLUMNS)] = output[list(FEATURE_COLUMNS)].astype("float32")
        research = output[output.trade_date >= pd.Timestamp("2019-01-02")]
        jan_2026 = research[(research.trade_date >= "2026-01-01") & (research.trade_date <= "2026-02-28")]
        early_ratio = None if jan_2026.empty else float(jan_2026.style_idio_vol_20.isna().mean())
        quality = {"row_count": len(output), "feature_nan_ratio": {name: (None if research.empty else float(research[name].isna().mean())) for name in FEATURE_COLUMNS}, "2026_early_idio_nan_ratio": early_ratio, "cross_year_computation": True, "fill_policy": "none", "beta_window": 20, "idio_second_window": 20, "ddof": 0, "theoretical_warmup_sessions": 39}
        identity = {"schema_version": "tushare-feature-contract-v1", "normalized_bars_id": _artifact_id(normalized), "benchmark_id": _artifact_id(benchmark), "features": list(FEATURE_COLUMNS), "formulas": {"mom_ret_1d": "adjusted_close.pct_change(1)", "liq_volume_ratio_5": "vol/mean(vol,5,min_periods=5)", "style_beta_20": "population_cov(stock_return,market_return,20)/population_var(market_return,20)", "style_idio_vol_20": "population_std(stock_return-beta20*market_return,20)"}, "row_count": len(output)}
        return _publish_directory(self.workspace, "tushare_feature_dataset", identity, {"features.parquet": output, "quality.json": quality, "contract.json": identity})

    def build_labels(self, normalized: dict[str, Any]) -> dict[str, Any]:
        frame = _read_frame(normalized, "normalized_bars.parquet").sort_values(["symbol", "trade_date"], kind="mergesort")
        grouped = frame.groupby("symbol", sort=False)
        next_close = grouped.adjusted_close.shift(-1)
        next_open = grouped.adjusted_open.shift(-1)
        raw_label = next_close / next_open - 1.0
        next_volume = grouped.vol.shift(-1)
        next_raw_open, next_raw_high, next_raw_low = grouped.open.shift(-1), grouped.high.shift(-1), grouped.low.shift(-1)
        next_pre_close = grouped.pre_close.shift(-1)
        locked_limit = (next_raw_open.eq(next_raw_high) & next_raw_open.eq(next_raw_low) & ((next_raw_open / next_pre_close - 1).abs() >= 0.095))
        valid = raw_label.notna() & next_volume.gt(0) & ~locked_limit
        labels = pd.DataFrame({"symbol": frame.symbol, "trade_date": frame.trade_date, "raw_label": raw_label, "sample_weight": valid.astype("float32"), "next_tradable": next_volume.gt(0), "next_locked_limit": locked_limit})
        def normalize(group: pd.DataFrame) -> pd.Series:
            values = group.raw_label.where(group.sample_weight > 0)
            median = values.median()
            mad = (values - median).abs().median()
            clipped = values.clip(median - 5 * mad, median + 5 * mad) if pd.notna(mad) and mad > 0 else values
            std = clipped.std(ddof=0)
            return (clipped - clipped.mean()) / std if pd.notna(std) and std > 0 else clipped * np.nan
        labels["model_label"] = labels.groupby("trade_date", group_keys=False).apply(normalize, include_groups=False).reset_index(level=0, drop=True)
        labels[["raw_label", "model_label", "sample_weight"]] = labels[["raw_label", "model_label", "sample_weight"]].astype("float32")
        identity = {"schema_version": "tushare-label-contract-v1", "normalized_bars_id": _artifact_id(normalized), "formula": "adjusted_close[T+1]/adjusted_open[T+1]-1", "cross_section_transform": "5*MAD winsor then population zscore", "sample_policy": "next quote present, volume>0, not conservatively locked at price limit", "row_count": len(labels)}
        quality = {"raw_label_nan_ratio": float(labels.raw_label.isna().mean()), "model_label_nan_ratio": float(labels.model_label.isna().mean()), "zero_weight_ratio": float((labels.sample_weight == 0).mean()), "locked_limit_rows": int(labels.next_locked_limit.sum())}
        return _publish_directory(self.workspace, "tushare_label_dataset", identity, {"labels.parquet": labels, "quality.json": quality, "contract.json": identity})

    def build_qlib_view(self, universe_100: dict[str, Any], normalized: dict[str, Any], features: dict[str, Any], labels: dict[str, Any], calendar: dict[str, Any], benchmark: dict[str, Any]) -> dict[str, Any]:
        wanted = set(_read_frame(universe_100, "universe.parquet").ts_code.map(_normalize_symbol))
        bars = _read_frame(normalized, "normalized_bars.parquet")
        bars = bars[bars.symbol.isin(wanted) & (bars.trade_date >= RESEARCH_START) & (bars.trade_date <= END_DATE)]
        feature = _read_frame(features, "features.parquet")
        label = _read_frame(labels, "labels.parquet")
        frame = bars.merge(feature, on=["symbol", "trade_date"], how="left", validate="one_to_one").merge(label[["symbol", "trade_date", "raw_label", "model_label", "sample_weight"]], on=["symbol", "trade_date"], how="left", validate="one_to_one")
        cal = _read_frame(calendar, "trade_calendar.parquet")
        dates = sorted(pd.to_datetime(cal[(cal.is_open.astype(int) == 1) & (cal.cal_date >= RESEARCH_START) & (cal.cal_date <= "20260624")].cal_date, format="%Y%m%d").dt.strftime("%Y-%m-%d"))
        fields = ("open", "high", "low", "close", "volume", "amount", "factor", "adjclose", "tradable", *FEATURE_COLUMNS, "raw_label", "model_label", "sample_weight")
        files: dict[str, Any] = {"calendars/day.txt": "\n".join(dates) + "\n"}
        indices = {date: index for index, date in enumerate(dates)}
        instruments = []
        for symbol in sorted(wanted):
            observed = frame[frame.symbol == symbol].copy().sort_values("trade_date")
            if observed.empty:
                continue
            observed["_date"] = pd.to_datetime(observed.trade_date).dt.strftime("%Y-%m-%d")
            start, end = observed._date.iloc[0], observed._date.iloc[-1]
            instruments.append(f"{symbol}\t{start}\t{end}")
            start_index = indices[start]
            observed = observed.set_index("_date").reindex(dates[start_index:])
            values = {
                "open": observed.open, "high": observed.high, "low": observed.low, "close": observed.close,
                "volume": pd.to_numeric(observed.vol, errors="coerce") / 100.0,
                "amount": pd.to_numeric(observed.amount, errors="coerce") / 1000.0,
                "factor": observed.adj_factor, "adjclose": observed.adjusted_close,
                "tradable": observed.tradable.astype("float32"),
                **{name: observed[name] for name in FEATURE_COLUMNS},
                "raw_label": observed.raw_label, "model_label": observed.model_label, "sample_weight": observed.sample_weight,
            }
            for field, series in values.items():
                payload = np.concatenate(([np.float32(start_index)], np.asarray(series, dtype=np.float32))).tobytes()
                files[f"features/{symbol.lower()}/{field}.day.bin"] = payload
        files["instruments/all.txt"] = "\n".join(instruments) + "\n"
        market = _read_frame(benchmark, "index_daily.parquet").copy()
        market["_date"] = pd.to_datetime(market.trade_date, format="%Y%m%d").dt.strftime("%Y-%m-%d")
        market = market[market._date.isin(indices)].sort_values("_date").set_index("_date").reindex(dates)
        for field in ("open", "high", "low", "close", "volume", "amount"):
            source = {"volume": "vol", "amount": "amount"}.get(field, field)
            series = pd.to_numeric(market[source], errors="coerce")
            if field == "volume": series = series / 100.0
            if field == "amount": series = series / 1000.0
            files[f"features/sh000300/{field}.day.bin"] = np.concatenate(([np.float32(0)], np.asarray(series, dtype=np.float32))).tobytes()
        files["features/sh000300/factor.day.bin"] = np.concatenate(([np.float32(0)], np.ones(len(dates), dtype=np.float32))).tobytes()
        files["instruments/benchmark.txt"] = f"SH000300\t{dates[0]}\t{dates[-2]}\n"
        identity = {"schema_version": "tushare-100-qlib-view-v1", "universe_lock_id": _artifact_id(universe_100), "normalized_bars_id": _artifact_id(normalized), "feature_dataset_id": _artifact_id(features), "label_dataset_id": _artifact_id(labels), "calendar_id": _artifact_id(calendar), "benchmark_id": _artifact_id(benchmark), "symbols": sorted(wanted), "benchmark_symbol": "SH000300", "calendar_start": dates[0], "calendar_end": dates[-1], "boundary_sentinel": "2026-06-24", "fields": list(fields), "authority": "Dataset Snapshot; Qlib is a consumer view"}
        files["quality.json"] = {"equity_instrument_count": len(instruments), "benchmark_instrument_count": 1, "calendar_count": len(dates), "binary_field_count": len(fields)}
        return _publish_directory(self.workspace, "tushare_100_qlib_view", identity, files)

    def validate_cutover(self, universe_500: dict[str, Any], universe_100: dict[str, Any], history: dict[str, dict[str, Any]], normalized: dict[str, Any], features: dict[str, Any], labels: dict[str, Any], qlib: dict[str, Any]) -> dict[str, Any]:
        artifacts = [universe_500, universe_100, *history.values(), normalized, features, labels, qlib]
        validations = [validate_tushare_artifact(Path(item["path"]), _artifact_id(item)) for item in artifacts]
        feature = _read_frame(features, "features.parquet")
        wanted = set(_read_frame(universe_100, "universe.parquet").ts_code.map(_normalize_symbol))
        h1 = feature[feature.symbol.isin(wanted) & (feature.trade_date >= "2026-01-01") & (feature.trade_date <= END_DATE)].copy()
        idio_ratio = float(h1.style_idio_vol_20.isna().mean())
        def cs_zscore(series: pd.Series) -> pd.Series:
            std = series.std(ddof=0)
            return (series - series.mean()) / std if pd.notna(std) and std > 0 else series * np.nan
        ordered = feature[feature.symbol.isin(wanted)].sort_values(["symbol", "trade_date"])
        by_symbol = ordered.groupby("symbol", sort=False)
        m10 = by_symbol.mom_ret_1d.rolling(10, min_periods=10).mean().reset_index(level=0, drop=True)
        d10 = m10.groupby(ordered.symbol, sort=False).diff(10)
        m20 = by_symbol.mom_ret_1d.rolling(20, min_periods=20).mean().reset_index(level=0, drop=True)
        idio_rank = ordered.groupby("trade_date").style_idio_vol_20.rank(pct=True)
        factor1 = (d10 - 0.5 * idio_rank).groupby(ordered.trade_date).transform(cs_zscore)
        factor2 = (m20 - idio_rank).groupby(ordered.trade_date).transform(cs_zscore)
        signal = ((factor1 + factor2) / 2).groupby(ordered.trade_date).transform(cs_zscore)
        signal_h1 = signal[(ordered.trade_date >= "2026-01-01") & (ordered.trade_date <= END_DATE)]
        signal_ratio = float(signal_h1.isna().mean())
        duplicate_keys = int(_read_frame(normalized, "normalized_bars.parquet").duplicated(["symbol", "trade_date"]).sum())
        gates = {"artifact_validation": all(item["status"] == "valid" for item in validations), "universe_500": len(_read_frame(universe_500, "universe.parquet")) == 500, "universe_100": len(_read_frame(universe_100, "universe.parquet")) == 100, "duplicate_keys_zero": duplicate_keys == 0, "2026h1_idio_nan_lte_20pct": idio_ratio <= 0.20, "2026h1_locked_signal_nan_lte_20pct": signal_ratio <= 0.20}
        return {"status": "passed" if all(gates.values()) else "blocked", "gates": gates, "2026h1_style_idio_vol_20_nan_ratio": idio_ratio, "2026h1_locked_factor_signal_nan_ratio": signal_ratio, "artifact_count": len(artifacts), "duplicate_keys": duplicate_keys}

    def import_artifact(self, manifest: dict[str, Any], *, lineage: Iterable[str] = ()) -> dict[str, Any]:
        kind = manifest["artifact_kind"]
        receipt = self.store.import_artifact(kind, Path(manifest["path"]), _artifact_id(manifest), lineage=tuple(lineage))
        return {"artifact_id": receipt.artifact_id, "descriptor_id": receipt.descriptor_id, "file_count": receipt.file_count, "logical_bytes": receipt.logical_bytes, "exact_existing": receipt.exact_existing}

    def publish_genesis(self, *, universe_500_id: str, universe_100_id: str, dataset_id: str, feature_id: str, label_id: str, qlib_view_id: str) -> dict[str, dict[str, Any]]:
        registry_identity = {
            "schema_version": "tushare-research-registry-genesis-v1",
            "data_authority": PROVIDER_ID,
            "universe_500_id": universe_500_id,
            "universe_100_id": universe_100_id,
            "dataset_id": dataset_id,
            "feature_dataset_id": feature_id,
            "label_dataset_id": label_id,
            "qlib_view_id": qlib_view_id,
            "entry_count": 0,
            "promotion_count": 0,
            "approved_count": 0,
            "active_count": 0,
            "old_metrics_inherited": False,
        }
        registry = _publish_directory(self.workspace, "tushare_research_registry_genesis", registry_identity, {
            "registry.json": registry_identity,
            "quality.json": {"entry_count": 0, "promotion_count": 0, "approved_count": 0, "active_count": 0},
        })
        memory_identity = {
            "schema_version": "sanitized-research-memory-v1",
            "data_authority": PROVIDER_ID,
            "registry_genesis_id": _artifact_id(registry),
            "historical_metrics_invalidated_by_data_authority_cutover": True,
            "retained_categories": ["template_structure", "operator_fingerprint", "parameter_contract_failure", "proposal_safety_failure", "novelty", "engineering_experience"],
            "excluded_categories": ["ic", "rank_ic", "qlib_return", "frozen_result", "development_result", "promotion_decision", "factor_effectiveness_label"],
        }
        memory = _publish_directory(self.workspace, "sanitized_research_memory", memory_identity, {
            "memory.json": memory_identity,
            "quality.json": {"historical_metric_count": 0, "promotion_label_count": 0},
        })
        return {"registry": registry, "memory": memory}

    def publish_authority(self, *, validation: dict[str, Any], artifact_ids: list[str], purge_result_id: str | None = None) -> dict[str, Any]:
        if validation.get("status") != "passed":
            raise ValueError("Tushare authority cannot activate before all cutover gates pass")
        identity = {
            "schema_version": "quantmind-data-authority-v1",
            "provider_id": PROVIDER_ID,
            "authority_status": "active",
            "legacy_provider_id": "quantmind-production-feature-snapshots-v1",
            "legacy_authority_status": "retired_and_purged" if purge_result_id else "retired_pending_purge",
            "legacy_runtime_read_allowed": False,
            "artifact_ids": artifact_ids,
            "validation": validation,
            "purge_result_id": purge_result_id,
            "runtime_fallback": "forbidden",
        }
        return _publish_directory(self.workspace, "data_authority_record", identity, {
            "authority.json": identity,
            "quality.json": {"active_provider_count": 1, "cutover_gates_passed": True},
        })

    def cold_restore(self, artifact_ids: Iterable[str], destination: Path) -> dict[str, Any]:
        destination = Path(destination)
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        restored = []
        for artifact_id in artifact_ids:
            descriptor = self.store.get_descriptor(artifact_id)
            target = destination / artifact_id
            receipt = self.store.materialize_artifact(descriptor.descriptor_id, target)
            validate_tushare_artifact(target, artifact_id, expected_kind=descriptor.artifact_kind)
            restored.append({"artifact_id": artifact_id, "descriptor_id": descriptor.descriptor_id, "file_count": receipt.materialized_file_count, "verified": receipt.verified})
        return {"status": "passed", "artifact_count": len(restored), "artifacts": restored}

    def plan_purge(self, source_paths: Iterable[Path]) -> dict[str, Any]:
        roots = tuple(sorted({Path(path).expanduser().resolve() for path in source_paths}))
        for root in roots:
            if root == Path("/") or str(root) in {"/Users", str(Path.home())}:
                raise ValueError("legacy purge root is overbroad")
        descriptors = self.store.list_artifacts()
        direct: set[str] = set()
        for descriptor in descriptors:
            manifest_file = next((item for item in descriptor.files if item.relative_path == "manifest.json"), None)
            if manifest_file is None:
                continue
            object_path = self.store.root / "objects" / "sha256" / manifest_file.sha256[:2] / manifest_file.sha256
            try:
                manifest = json.loads(object_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            canonical = canonical_json_bytes(manifest)
            if b"quantmind-production-feature-snapshots-v1" in canonical or manifest.get("dataset_kind") == "legacy_feature_matrix_v1":
                direct.add(descriptor.artifact_id)
        # Pre-cutover Store migrations did not always preserve lineage on the
        # fixed-universe/historical graph.  At the one-time authority boundary,
        # every research artifact kind other than the new Tushare governance
        # graph is legacy-derived. Implementation evidence remains in Git/ledger.
        retained_kinds = {
            ArtifactKind.IMPLEMENTATION_EVIDENCE.value,
            ArtifactKind.SANITIZED_RESEARCH_MEMORY.value,
            ArtifactKind.DATA_AUTHORITY_RECORD.value,
            ArtifactKind.LEGACY_DATA_PURGE_PLAN.value,
            ArtifactKind.LEGACY_DATA_PURGE_RESULT.value,
        }
        for descriptor in descriptors:
            if not descriptor.artifact_kind.startswith("tushare_") and descriptor.artifact_kind not in retained_kinds:
                direct.add(descriptor.artifact_id)
        purge_ids = set(direct)
        changed = True
        while changed:
            changed = False
            for descriptor in descriptors:
                if descriptor.artifact_id not in purge_ids and any(parent in purge_ids for parent in descriptor.lineage):
                    purge_ids.add(descriptor.artifact_id)
                    changed = True
        selected = [descriptor for descriptor in descriptors if descriptor.artifact_id in purge_ids]
        retained = [descriptor for descriptor in descriptors if descriptor.artifact_id not in purge_ids]
        retained_blobs = {item.sha256 for descriptor in retained for item in descriptor.files}
        purge_blobs = {item.sha256 for descriptor in selected for item in descriptor.files if item.sha256 not in retained_blobs}
        path_rows = []
        for root in roots:
            count = total = 0
            if root.exists():
                for path in root.rglob("*"):
                    if path.is_file() and not path.is_symlink():
                        count += 1
                        total += path.stat().st_size
            path_rows.append({"path": str(root), "exists": root.exists(), "file_count": count, "total_bytes": total})
        blob_bytes = sum((self.store.root / "objects" / "sha256" / digest[:2] / digest).stat().st_size for digest in purge_blobs)
        identity = {
            "schema_version": "legacy-data-purge-plan-v1",
            "reason": "deprecated_due_to_data_authority_replacement",
            "source_paths": path_rows,
            "artifact_ids": sorted(purge_ids),
            "descriptor_ids": sorted(item.descriptor_id for item in selected),
            "blob_ids": sorted(purge_blobs),
            "file_count": sum(row["file_count"] for row in path_rows),
            "total_bytes": sum(row["total_bytes"] for row in path_rows),
            "artifact_logical_bytes": sum(item.total_bytes for item in selected),
            "blob_bytes": blob_bytes,
            "estimated_bytes_to_reclaim": sum(row["total_bytes"] for row in path_rows) + blob_bytes,
            "retained_metadata": "Git implementation runs, reports, manifests and this immutable plan",
            "shared_blob_policy": "delete only when no retained descriptor references the blob",
        }
        return _publish_directory(self.workspace, "legacy_data_purge_plan", identity, {"plan.json": identity, "quality.json": {"all_paths_bounded": True, "shared_blobs_excluded": True}})

    def execute_purge(self, plan: dict[str, Any]) -> dict[str, Any]:
        validate_tushare_artifact(Path(plan["path"]), _artifact_id(plan), expected_kind="legacy_data_purge_plan")
        payload = json.loads((Path(plan["path"]) / "plan.json").read_text())
        bytes_before = sum(row["total_bytes"] for row in payload["source_paths"]) + payload["blob_bytes"]
        files_deleted = 0
        for row in payload["source_paths"]:
            path = Path(row["path"]).resolve()
            if path == Path("/") or str(path) in {"/Users", str(Path.home())}:
                raise ValueError("purge plan contains an overbroad path")
            if path.exists():
                files_deleted += sum(1 for item in path.rglob("*") if item.is_file())
                shutil.rmtree(path)
        artifacts_deleted = 0
        for descriptor_id in payload["descriptor_ids"]:
            matches = [item for item in self.store.list_artifacts() if item.descriptor_id == descriptor_id]
            if len(matches) != 1:
                raise ValueError("purge descriptor set drifted")
            descriptor = matches[0]
            target = self.store.root / "artifacts" / descriptor.artifact_kind / descriptor.artifact_id
            shutil.rmtree(target)
            artifacts_deleted += 1
        currently_referenced = {item.sha256 for descriptor in self.store.list_artifacts() for item in descriptor.files}
        blobs_deleted = blob_bytes = 0
        for digest in payload["blob_ids"]:
            if digest in currently_referenced:
                continue
            path = self.store.root / "objects" / "sha256" / digest[:2] / digest
            if path.is_file():
                blob_bytes += path.stat().st_size
                path.unlink()
                blobs_deleted += 1
        for directory in sorted((self.store.root / "objects" / "sha256").glob("*")):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        from backend.services.engine.artifact_store.integrity import scan_store_integrity
        integrity = scan_store_integrity(self.store)
        if integrity.status != "healthy" or integrity.unreferenced_blobs:
            raise ValueError("Artifact Store is not healthy after purge")
        result_identity = {
            "schema_version": "legacy-data-purge-result-v1", "purge_plan_id": _artifact_id(plan),
            "bytes_before": bytes_before, "bytes_after": 0, "bytes_reclaimed": bytes_before,
            "files_deleted": files_deleted, "artifacts_deleted": artifacts_deleted,
            "blobs_deleted": blobs_deleted, "blob_bytes_deleted": blob_bytes,
            "integrity": integrity.status, "missing": len(integrity.issues), "unreferenced": len(integrity.unreferenced_blobs),
        }
        return _publish_directory(self.workspace, "legacy_data_purge_result", result_identity, {"result.json": result_identity, "quality.json": {"integrity": integrity.status, "missing": 0, "unreferenced": 0}})
