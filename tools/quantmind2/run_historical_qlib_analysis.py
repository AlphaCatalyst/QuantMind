#!/usr/bin/env python3
"""Run the locked QM2-P0-011B formal Qlib analysis in an isolated runtime."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd


def _runtime_compatibility() -> None:
    # setuptools installs its local distutils compatibility module on Python 3.12.
    import setuptools  # noqa: F401
    module = types.ModuleType("pkg_resources")
    module.resource_filename = lambda package, name: str(Path(importlib.util.find_spec(package).origin).parent / name)
    module.iter_entry_points = lambda *args, **kwargs: []
    module.working_set = []
    sys.modules.setdefault("pkg_resources", module)


class _NullRedis:
    def _ensure_connection(self): return True
    def __getattr__(self, _name): return lambda *args, **kwargs: None


def main() -> int:
    _runtime_compatibility()
    import backend.shared.redis_sentinel_client as redis_sentinel
    redis_sentinel.get_redis_sentinel_client = lambda: _NullRedis()
    from backend.services.engine.qlib_app.services.backtest_service import QlibBacktestService
    import backend.services.engine.qlib_app.utils.cn_exchange as cn_exchange
    cn_exchange.get_redis_sentinel_client = lambda: _NullRedis()
    from backend.services.engine.historical_agent_experiment.analysis import (
        YEAR_WINDOWS, fixed_universe_equal_weight_benchmark,
    )
    from backend.services.engine.historical_agent_experiment.qlib_runner import run_formal_backtest_sync

    root = Path.home() / ".cache/quantmind2/historical-agent-experiment/QM2-P0-011B"
    stage = json.loads((root / "stage1-analysis.json").read_text())
    selected = stage["selection"]["selected_factor_instance_ids"]
    experiment = json.loads((root / "domain/historical_agent_experiment/hae_7e4b138b726280d21eae0bdd24285c3fb2ef011f851ee7d2509425c4e85c1b52/manifest.json").read_text())
    by_id = {item["selected_trial"]["factor_instance_id"]: item for item in experiment["all_candidates"]}
    matrix = pd.read_parquet(root / "domain/fixed_universe_historical_dataset/fuhd_734dae599ff7925af7e6625a5c3a3ffd84ae2b1019efd239b431a69913cf95fb/historical_matrix.parquet")
    benchmark = fixed_universe_equal_weight_benchmark(matrix)
    parts = []
    for factor_id in selected:
        selected_trial = by_id[factor_id]["selected_trial"]
        frame = pd.read_parquet(root / "factor-values" / selected_trial["factor_values_id"] / "values.parquet")
        frame["value"] = pd.to_numeric(frame.factor_value, errors="coerce") * selected_trial["orientation"]
        parts.append(frame[["symbol", "trade_date", "value"]].rename(columns={"value": factor_id}))
    combo = parts[0]
    for frame in parts[1:]: combo = combo.merge(frame, on=["symbol", "trade_date"], how="outer", validate="one_to_one")
    for factor_id in selected:
        combo[factor_id] = combo.groupby("trade_date")[factor_id].transform(
            lambda values: (values-values.mean())/values.std(ddof=0)
            if values.notna().sum() > 1 and values.std(ddof=0) > 0 else np.nan)
    combo["pred"] = combo[selected].mean(axis=1, skipna=False)
    combo_path = root / "signals/equal_weight_combo.parquet"
    combo[["symbol", "trade_date", "pred"]].to_parquet(combo_path, index=False)
    signals = {factor_id: root / "signals" / f"{factor_id}.parquet" for factor_id in selected}
    signals["equal_weight_combo"] = combo_path
    service = QlibBacktestService(str(root / "qlib-views/qcv_211a18992244b4e795cc659ba86fc1c25e30b53028c05373ef13ae9986fdd9d2"))
    async def noop(*args, **kwargs): return None
    service._notify_progress = noop
    collector = []
    original = cn_exchange.CnExchange.deal_order
    def audited(exchange, *args, **kwargs):
        result = original(exchange, *args, **kwargs)
        collector.append({"value": float(result[0]), "cost": float(result[1])})
        return result
    cn_exchange.CnExchange.deal_order = audited

    def run(signal, start, end, **kwargs):
        collector.clear()
        result = run_formal_backtest_sync(service, signal_path=signal, start=start, end=end, **kwargs)
        equity = result.get("equity_curve") or []
        average_equity = float(np.mean([row["value"] for row in equity])) if equity else 1.0
        result["audited_transaction_cost"] = float(sum(row["cost"] for row in collector))
        result["audited_turnover"] = float(sum(abs(row["value"]) for row in collector) / average_equity)
        result["audited_deals"] = len(collector)
        return result

    annual, full = {}, {}
    for name, signal in signals.items():
        annual[name] = {}
        for year, (start, end) in YEAR_WINDOWS.items():
            result = run(signal, start, end)
            returns = benchmark[(benchmark.index >= start) & (benchmark.index <= end)]
            benchmark_return = float((1+returns).prod()-1)
            result["fixed_universe_benchmark_return"] = benchmark_return
            result["net_excess"] = result.get("total_return")-benchmark_return if result.get("total_return") is not None else None
            annual[name][year] = result
        result = run(signal, "2019-01-02", "2026-06-23")
        benchmark_return = float((1+benchmark).prod()-1)
        result["fixed_universe_benchmark_return"] = benchmark_return
        result["net_excess"] = result.get("total_return")-benchmark_return if result.get("total_return") is not None else None
        full[name] = result
    robustness = {
        "topk10": run(combo_path, "2019-01-02", "2026-06-23", topk=10, n_drop=5),
        "topk30": run(combo_path, "2019-01-02", "2026-06-23", topk=30, n_drop=5),
        "daily": run(combo_path, "2019-01-02", "2026-06-23", rebalance_days=1),
        "cost2x": run(combo_path, "2019-01-02", "2026-06-23", cost_multiplier=2.0),
    }
    concentration = {}
    for name, result in full.items():
        equity = pd.DataFrame(result.get("equity_curve") or [])
        positions = pd.DataFrame(result.get("positions") or [])
        if equity.empty: top_days, excluded = [], None
        else:
            equity["return"] = equity.value.pct_change(); top = equity.nlargest(10, "return")
            top_days = top[["date", "return"]].to_dict("records")
            excluded = float((1+equity.loc[~equity.index.isin(top.index), "return"].dropna()).prod()-1)
        if positions.empty: top_symbols, exposure_share = {}, None
        else:
            exposure = positions.assign(abs_weight=positions.weight.abs()).groupby("symbol").abs_weight.sum().sort_values(ascending=False)
            top_symbols = exposure.head(10).to_dict(); exposure_share = float(exposure.head(10).sum()/exposure.sum())
        concentration[name] = {"top_10_return_days": top_days,
            "return_excluding_top_10_days": excluded,
            "top_10_symbols_by_absolute_position_exposure": top_symbols,
            "top_10_symbol_exposure_share": exposure_share}
    output = {"selected": selected, "selection_locked_before_holdout": True,
              "holdout_feedback_to_agent": False, "annual": annual, "full_period": full,
              "robustness": robustness, "concentration": concentration,
              "formal_qlib_calls": len(signals)*9+len(robustness),
              "redis_side_effects": "disabled_only; execution and CnExchange unchanged"}
    (root / "final-analysis.json").write_text(json.dumps(output, ensure_ascii=False, sort_keys=True, default=str))
    summary = {"selected": selected, "formal_qlib_calls": output["formal_qlib_calls"],
               "holdout": {name: {year: {key: rows[year].get(key) for key in
                    ("total_return", "net_excess", "sharpe_ratio", "max_drawdown", "audited_turnover", "audited_transaction_cost")}
                    for year in ("2025", "2026H1")} for name, rows in annual.items()},
               "full": {name: {key: result.get(key) for key in
                    ("total_return", "net_excess", "sharpe_ratio", "max_drawdown", "audited_turnover", "audited_transaction_cost")}
                    for name, result in full.items()}}
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__": raise SystemExit(main())
