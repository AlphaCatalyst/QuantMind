from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from backend.services.engine.strategy_layer.errors import StrategyLayerError
from backend.services.engine.strategy_layer.qlib_adapter import to_qlib_score
from backend.services.engine.strategy_layer.result import publish_strategy_registry
from backend.services.engine.strategy_layer.service import build_execution_plan, build_portfolio_target, parse_strategy_spec, strategy_spec_id


def payload(**overrides):
    value = {
        "schema_version": "1.0.0", "name": "topk20", "description": "diagnostic",
        "unified_signal_id": "usa_x", "universe_id": "tu100_x", "qlib_view_id": "tqv_x",
        "start_date": "2020-01-01", "end_date": "2020-02-01",
        "selection": {"type": "topk_dropout", "topk": 20, "n_drop": 5},
        "rebalance": {"frequency": "weekly", "interval_sessions": 5, "rebalance_day": "first_available_session"},
        "weighting": {"type": "equal_weight"},
        "execution": {"chain": ["QlibBacktestService", "RedisRecordingStrategy", "SimulatorExecutor", "CnExchange"], "deal_price": "open", "signal_lag_days": 1},
        "costs": {"commission": 0.00025, "stamp_duty": 0.0005, "transfer_fee": 0.00001, "impact_cost_coefficient": 0.0005, "minimum_commission": 5.0},
        "benchmark": {"name": "CSI300", "symbol": "SH000300", "canonicality": "canonical"},
        "quality_gates": {"minimum_daily_finite_count": 25},
        "evidence_policy": {"signal_evidence_class": "research_diagnostic", "usable_for_research": True, "usable_for_parameter_optimization": False, "usable_for_promotion": False},
        "data_authority": "tushare-pro-v1",
    }
    value.update(overrides)
    return value


def signal():
    return pd.DataFrame([{"symbol": f"S{i:03d}", "trade_date": date, "score": float(i)} for date in pd.date_range("2020-01-01", periods=11, freq="B") for i in range(30)])


def test_strategy_contract_plan_and_qlib_score():
    spec = parse_strategy_spec(payload())
    plan = build_execution_plan(spec, signal_artifact_id="usa_x", lifecycle_policy_id="fulp_x", termination_policy_id="stp_x")
    assert strategy_spec_id(spec).startswith("sts_")
    assert plan["agent_calls"] == plan["strategy_optimization_trials"] == plan["promotion_writes"] == 0
    assert list(to_qlib_score(signal()).columns) == ["symbol", "trade_date", "pred"]


def test_topk_dropout_weekly_equal_weight_and_lifecycle_gate(tmp_path):
    spec = parse_strategy_spec(payload())
    life = signal()[["symbol", "trade_date"]].copy(); life["active"] = True; life["tradable"] = True
    life.loc[life.symbol == "S029", "tradable"] = False
    result = build_portfolio_target(signal(), spec, tmp_path, lifecycle=life)
    frame = pd.read_parquet(Path(result["path"]) / "portfolio_target.parquet")
    assert frame.trade_date.nunique() == 3
    assert frame.groupby("trade_date").size().max() == 20
    assert frame.groupby("trade_date").target_weight.sum().sub(1).abs().max() < 1e-12
    assert "S029" not in set(frame.symbol)


def test_rejects_noncanonical_benchmark_and_optimization():
    bad = payload(); bad["benchmark"] = {"name": "Fixed-100", "symbol": "FIXED100", "canonicality": "noncanonical"}
    with pytest.raises(StrategyLayerError): parse_strategy_spec(bad)
    bad = payload(); bad["evidence_policy"]["usable_for_parameter_optimization"] = True
    with pytest.raises(StrategyLayerError): parse_strategy_spec(bad)


def test_registry_forbids_promotion(tmp_path):
    good = publish_strategy_registry(tmp_path, [{"strategy_spec_id": "sts_x", "status": "backtest_completed"}], ["sbr_x"])
    assert good["strategy_research_registry_id"].startswith("srr_")
    locked = publish_strategy_registry(tmp_path, [{"strategy_spec_id": "sts_x", "status": "parameter_candidate_locked"}], ["spcl_x"])
    assert locked["strategy_research_registry_id"].startswith("srr_")
    with pytest.raises(ValueError):
        publish_strategy_registry(tmp_path, [{"strategy_spec_id": "sts_x", "status": "approved"}], ["sbr_x"])
