from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pandas as pd


def write_oriented_signal(values_path: Path, output_path: Path, orientation: int) -> Path:
    frame = pd.read_parquet(values_path, engine="pyarrow")
    frame["pred"] = pd.to_numeric(frame.pop("factor_value"), errors="coerce") * int(orientation)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output_path, index=False, engine="pyarrow")
    return output_path


async def run_formal_backtest(service, *, signal_path: Path, start: str, end: str,
                              topk: int = 20, n_drop: int = 5,
                              rebalance_days: int = 5, cost_multiplier: float = 1.0) -> dict:
    from backend.services.engine.qlib_app.schemas.backtest import QlibBacktestRequest

    os.environ["QLIB_PRED_PATH"] = str(signal_path)
    request = QlibBacktestRequest(
        strategy_type="TopkDropout",
        strategy_params={"topk": topk, "n_drop": n_drop,
                         "rebalance_days": rebalance_days, "signal": "<PRED>"},
        start_date=start, end_date=end, initial_capital=1_000_000,
        benchmark_symbol="SH000300", universe="all", deal_price="open", signal_lag_days=1,
        commission=0.00025 * cost_multiplier, stamp_duty=0.0005 * cost_multiplier,
        transfer_fee=0.00001 * cost_multiplier, impact_cost_coefficient=0.0005 * cost_multiplier,
        min_commission=5.0 * cost_multiplier, min_transfer_fee=0.01 * cost_multiplier,
        history_source="optimization", seed=20260719,
    )
    result = await service.run_backtest(request)
    return result.model_dump(mode="json")


def run_formal_backtest_sync(service, **kwargs) -> dict:
    return asyncio.run(run_formal_backtest(service, **kwargs))
