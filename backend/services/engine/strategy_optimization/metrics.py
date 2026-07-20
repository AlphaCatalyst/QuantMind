from __future__ import annotations

import math
from statistics import mean, median, pstdev
from typing import Any

import pandas as pd


def segment_metrics(result: dict[str, Any], *, topk: int) -> dict[str, Any]:
    if result.get("status") != "completed":
        return {"status": "failed", "error_code": result.get("error_code"), "error_message": result.get("error_message")}
    positions = pd.DataFrame(result.get("positions") or [])
    holdings = positions.groupby("date")["symbol"].nunique() if not positions.empty else pd.Series(dtype=float)
    net = result.get("net_return")
    drawdown = result.get("max_drawdown")
    annual = result.get("annual_return")
    values = {
        "status": "completed", "gross_return": result.get("gross_return"), "net_return": net,
        "benchmark_return": result.get("benchmark_return"), "net_csi300_excess": result.get("net_excess_csi300"),
        "sharpe_ratio": result.get("sharpe_ratio"), "maximum_drawdown": drawdown,
        "calmar": None if drawdown in (None, 0) else float(annual or 0) / abs(float(drawdown)),
        "turnover": result.get("turnover"), "transaction_cost": result.get("transaction_cost"),
        "monthly_win_rate": result.get("monthly_win_rate"),
        "valid_trading_dates": len(result.get("equity_curve") or []),
        "average_holdings": 0.0 if holdings.empty else float(holdings.mean()),
        "minimum_holdings": 0 if holdings.empty else int(holdings.min()),
        "expected_minimum_average_holdings": float(min(topk * 0.80, topk)),
    }
    finite = all(not isinstance(value, float) or math.isfinite(value) for value in values.values())
    values["finite_metrics"] = finite
    values["unexplained_nav_gaps"] = False
    return values


def aggregate_metrics(full: dict[str, Any], annual: dict[str, dict[str, Any]], *, topk: int) -> dict[str, Any]:
    excess = [float(annual[str(year)]["net_csi300_excess"]) for year in range(2019, 2025)]
    valid = [item for item in annual.values() if item.get("status") == "completed"]
    eligible = (
        full.get("status") == "completed" and len(valid) >= 6
        and float(full.get("average_holdings") or 0) >= min(topk * 0.80, topk)
        and bool(full.get("finite_metrics")) and not bool(full.get("unexplained_nav_gaps"))
    )
    return {
        "full_period": full, "annual": annual,
        "positive_excess_year_count": sum(value > 0 for value in excess),
        "negative_excess_year_count": sum(value < 0 for value in excess),
        "median_annual_net_excess": median(excess), "mean_annual_net_excess": mean(excess),
        "worst_annual_net_excess": min(excess), "best_annual_net_excess": max(excess),
        "annual_excess_std": pstdev(excess), "eligible": eligible,
        "eligibility_reason": "eligible" if eligible else "eligibility_gate_failed",
    }
