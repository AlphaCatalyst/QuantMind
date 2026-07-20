from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.factor_dsl.compiler import compile_template
from backend.services.engine.factor_dsl.executor import _evaluate
from backend.services.engine.factor_dsl.models import SnapshotContract
from backend.services.engine.factor_validation.metrics import (
    calculate_split_metrics,
    metrics_payload,
)
from backend.services.engine.tushare_cutover.canonical import hash_payload


YEAR_WINDOWS = {
    "2019": ("2019-01-02", "2019-12-31"),
    "2020": ("2020-01-02", "2020-12-31"),
    "2021": ("2021-01-04", "2021-12-31"),
    "2022": ("2022-01-04", "2022-12-30"),
    "2023": ("2023-01-03", "2023-12-29"),
    "2024": ("2024-01-02", "2024-12-31"),
    "2025": ("2025-01-02", "2025-12-30"),
    "2026H1": ("2026-01-05", "2026-06-23"),
}


def snapshot_contract(feature_dataset_id: str, date_count: int) -> SnapshotContract:
    return SnapshotContract(
        feature_dataset_id,
        "tushare_feature_matrix_v1",
        {
            "symbol": "key",
            "trade_date": "key",
            "mom_ret_1d": "feature",
            "liq_volume_ratio_5": "feature",
            "style_beta_20": "feature",
            "style_idio_vol_20": "feature",
        },
        date_count,
        {
            "symbol": "string",
            "trade_date": "timestamp[ns]",
            "mom_ret_1d": "float32",
            "liq_volume_ratio_5": "float32",
            "style_beta_20": "float32",
            "style_idio_vol_20": "float32",
        },
    )


def factor_values(template, contract, parameters: dict, matrix: pd.DataFrame) -> tuple[Any, pd.DataFrame]:
    compiled = compile_template(template, contract, parameters)
    values = _evaluate(compiled.template.expression, matrix, compiled.bound_parameters)
    frame = matrix[["symbol", "trade_date"]].copy()
    frame["factor_value"] = pd.to_numeric(values, errors="coerce")
    return compiled, frame


def split_metrics(values: pd.DataFrame, matrix: pd.DataFrame, start: str, end: str, orientation: int) -> dict:
    mask = matrix["trade_date"].between(start, end)
    labels = matrix.loc[mask, ["symbol", "trade_date", "model_label"]]
    return metrics_payload(calculate_split_metrics(values, labels, orientation=orientation))


def group_diagnostics(values: pd.DataFrame, matrix: pd.DataFrame, start: str, end: str, orientation: int) -> dict:
    mask = matrix["trade_date"].between(start, end)
    labels = matrix.loc[mask, ["symbol", "trade_date", "raw_label"]]
    merged = labels.merge(values, on=["symbol", "trade_date"], how="left", validate="one_to_one")
    merged["factor_value"] *= orientation
    rows = []
    for _, group in merged.groupby("trade_date", sort=True):
        valid = group.dropna(subset=["factor_value", "raw_label"]).copy()
        if len(valid) < 20 or valid["factor_value"].nunique() < 5:
            continue
        valid["bucket"] = pd.qcut(valid["factor_value"].rank(method="first"), 5, labels=False)
        rows.append(valid.groupby("bucket")["raw_label"].mean())
    if not rows:
        return {"group_returns": [], "group_monotonicity": None, "top_bottom_return": None}
    means = pd.concat(rows, axis=1).mean(axis=1).reindex(range(5))
    correlation = means.corr(pd.Series(range(5), index=range(5)), method="spearman")
    return {
        "group_returns": [None if pd.isna(value) else float(value) for value in means],
        "group_monotonicity": None if pd.isna(correlation) else float(correlation),
        "top_bottom_return": None if means.isna().any() else float(means.iloc[-1] - means.iloc[0]),
    }


def oriented_signal(values: pd.DataFrame, orientation: int, path: Path) -> Path:
    output = values.rename(columns={"factor_value": "pred"}).copy()
    output["pred"] = pd.to_numeric(output["pred"], errors="coerce") * orientation
    path.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(path, index=False, compression="zstd", engine="pyarrow")
    return path


def equal_weight_signal(parts: dict[str, Path], path: Path) -> Path:
    merged = None
    for name, source in sorted(parts.items()):
        frame = pd.read_parquet(source).rename(columns={"pred": name})
        merged = frame if merged is None else merged.merge(
            frame, on=["symbol", "trade_date"], how="outer", validate="one_to_one"
        )
    assert merged is not None
    for name in parts:
        merged[name] = merged.groupby("trade_date")[name].transform(
            lambda values: (values - values.mean()) / values.std(ddof=0)
            if values.notna().sum() > 1 and values.std(ddof=0) > 0
            else np.nan
        )
    merged["pred"] = merged[list(parts)].mean(axis=1, skipna=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    merged[["symbol", "trade_date", "pred"]].to_parquet(path, index=False, compression="zstd")
    return path


def fixed100_benchmark(normalized: pd.DataFrame) -> pd.Series:
    frame = normalized[["symbol", "trade_date", "adjusted_close"]].copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame["return"] = frame.sort_values(["symbol", "trade_date"]).groupby("symbol")["adjusted_close"].pct_change(fill_method=None)
    # Missing observations are structurally absent from that day's equal-weight
    # denominator.  They must never be converted to zero-return constituents.
    return frame.groupby("trade_date")["return"].mean().sort_index()


def _runtime_compatibility() -> None:
    import setuptools  # noqa: F401

    module = types.ModuleType("pkg_resources")
    module.resource_filename = lambda package, name: str(Path(importlib.util.find_spec(package).origin).parent / name)
    module.iter_entry_points = lambda *args, **kwargs: []
    module.working_set = []
    sys.modules.setdefault("pkg_resources", module)


class _NullRedis:
    def _ensure_connection(self):
        return True

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


class FormalQlibRunner:
    def __init__(self, qlib_view: Path, normalized: pd.DataFrame, cache_root: Path):
        _runtime_compatibility()
        import backend.shared.redis_sentinel_client as redis_sentinel

        redis_sentinel.get_redis_sentinel_client = lambda: _NullRedis()
        from backend.services.engine.qlib_app.services.backtest_service import QlibBacktestService
        import backend.services.engine.qlib_app.utils.cn_exchange as cn_exchange

        cn_exchange.get_redis_sentinel_client = lambda: _NullRedis()
        self.service = QlibBacktestService(str(qlib_view))
        async def noop(*args, **kwargs):
            return None
        self.service._notify_progress = noop
        self.cn_exchange = cn_exchange
        self.cache_root = Path(cache_root)
        self.benchmark = fixed100_benchmark(normalized)
        self.calls = 0

    def run(
        self,
        signal_path: Path,
        start: str,
        end: str,
        *,
        topk: int = 20,
        n_drop: int = 5,
        rebalance_days: int = 5,
        cost_multiplier: float = 1.0,
        lifecycle_policy: dict | None = None,
        execution_audit_symbols: tuple[str, ...] = (),
    ) -> dict:
        from backend.services.engine.historical_agent_experiment.qlib_runner import run_formal_backtest_sync

        key = hash_payload({
            "signal_sha256": __import__("hashlib").sha256(Path(signal_path).read_bytes()).hexdigest(),
            "start": start,
            "end": end,
            "topk": topk,
            "n_drop": n_drop,
            "rebalance_days": rebalance_days,
            "cost_multiplier": cost_multiplier,
            "lifecycle_policy": lifecycle_policy,
            "execution_audit_symbols": sorted(execution_audit_symbols),
        })
        cached = self.cache_root / f"{key}.json"
        if cached.exists():
            return json.loads(cached.read_text(encoding="utf-8"))
        collector: list[dict] = []
        original = self.cn_exchange.CnExchange.deal_order
        def audited(exchange, *args, **kwargs):
            result = original(exchange, *args, **kwargs)
            order = args[0] if args else kwargs.get("order")
            record = {"value": float(result[0]), "cost": float(result[1])}
            if order is not None and str(getattr(order, "stock_id", "")) in execution_audit_symbols:
                direction = int(getattr(order, "direction", -1))
                record.update({
                    "symbol": str(order.stock_id),
                    "action": "buy" if direction == 1 else "sell" if direction == 0 else "unknown",
                    "order_amount": float(getattr(order, "amount", 0.0) or 0.0),
                    "dealt_amount": float(getattr(order, "deal_amount", 0.0) or 0.0),
                    "trade_price": None if result[2] is None else float(result[2]),
                    "start_time": str(getattr(order, "start_time", "")),
                    "end_time": str(getattr(order, "end_time", "")),
                    "factor": None if getattr(order, "factor", None) is None else float(order.factor),
                })
            collector.append(record)
            return result
        self.cn_exchange.CnExchange.deal_order = audited
        try:
            result = run_formal_backtest_sync(
                self.service,
                signal_path=signal_path,
                start=start,
                end=end,
                topk=topk,
                n_drop=n_drop,
                rebalance_days=rebalance_days,
                cost_multiplier=cost_multiplier,
                lifecycle_policy=lifecycle_policy,
            )
        finally:
            self.cn_exchange.CnExchange.deal_order = original
        if result.get("status") != "completed" or result.get("error_message"):
            rejected = {
                "status": "rejected",
                "error_code": "FORMAL_QLIB_SIGNAL_QUALITY_REJECTED",
                "error_message": str(result.get("error_message") or "formal Qlib backtest failed")[:500],
                "gross_return": None,
                "net_return": None,
                "benchmark_return": None,
                "fixed_100_benchmark_return": None,
                "net_excess_csi300": None,
                "net_excess_fixed_100": None,
                "sharpe_ratio": None,
                "max_drawdown": None,
                "transaction_cost": None,
                "turnover": None,
                "formal_chain": [
                    "QlibBacktestService",
                    "RedisRecordingStrategy",
                    "SimulatorExecutor",
                    "CnExchange",
                ],
            }
            self.cache_root.mkdir(parents=True, exist_ok=True)
            cached.write_text(
                json.dumps(rejected, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            self.calls += 1
            return rejected
        equity = pd.DataFrame(result.get("equity_curve") or [])
        average_equity = float(equity["value"].mean()) if not equity.empty else 1_000_000.0
        transaction_cost = float(sum(item["cost"] for item in collector))
        turnover = float(sum(abs(item["value"]) for item in collector) / average_equity)
        fixed = self.benchmark[(self.benchmark.index >= start) & (self.benchmark.index <= end)]
        fixed_return = float((1.0 + fixed).prod() - 1.0)
        net_return = result.get("total_return")
        result.update({
            "gross_return": None if net_return is None else float(net_return) + transaction_cost / 1_000_000.0,
            "net_return": net_return,
            "transaction_cost": transaction_cost,
            "turnover": turnover,
            "fixed_100_benchmark_return": fixed_return,
            "net_excess_csi300": None if net_return is None or result.get("benchmark_return") is None else float(net_return) - float(result["benchmark_return"]),
            "net_excess_fixed_100": None if net_return is None else float(net_return) - fixed_return,
            "formal_chain": ["QlibBacktestService", "RedisRecordingStrategy", "SimulatorExecutor", "CnExchange"],
        })
        if execution_audit_symbols:
            raw = [row for row in collector if "symbol" in row]
            unique = {}
            for row in raw:
                key = (
                    row["symbol"], row["action"], row["start_time"], row["end_time"],
                    round(row["order_amount"], 12), round(row["dealt_amount"], 12),
                    round(row["value"], 8), round(row["cost"], 8),
                )
                unique.setdefault(key, row)
            result["execution_audit"] = {
                "requested_symbols": sorted(execution_audit_symbols),
                "raw_order_count": len(raw),
                "deduplicated_order_count": len(unique),
                "orders": list(unique.values()),
                "target_weight_status": "not_emitted_by_topk_dropout",
            }
        if not equity.empty:
            equity["date"] = pd.to_datetime(equity["date"])
            equity["return"] = equity["value"].pct_change()
            monthly = equity.set_index("date")["return"].resample("ME").apply(lambda x: (1 + x.dropna()).prod() - 1)
            result["monthly_win_rate"] = float((monthly > 0).mean()) if len(monthly) else None
            result["worst_month"] = None if monthly.empty else {"month": monthly.idxmin().strftime("%Y-%m"), "return": float(monthly.min())}
            result["best_10_days_contribution"] = float(equity.nlargest(10, "return")["return"].sum())
            excluded = equity.drop(equity.nlargest(10, "return").index)["return"].dropna()
            result["return_without_best_10_days"] = float((1 + excluded).prod() - 1)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str), encoding="utf-8")
        self.calls += 1
        return result
