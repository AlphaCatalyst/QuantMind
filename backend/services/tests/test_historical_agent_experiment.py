from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from backend.services.engine.historical_agent_experiment.artifact import (
    publish_historical_artifact, validate_historical_artifact,
)
from backend.services.engine.historical_agent_experiment.memory import (
    build_as_of_memory, validate_as_of_memory,
)
from backend.services.engine.historical_agent_experiment.protocol import BUDGET, ROUNDS, fixed_protocol
from backend.services.engine.historical_agent_experiment.universe import select_fixed_universe
from backend.services.engine.historical_agent_experiment.analysis import lock_final_candidates
from backend.services.engine.historical_agent_experiment.qlib_runner import write_oriented_signal


def test_fixed_protocol_freezes_rounds_budget_and_qllib_contract() -> None:
    protocol = fixed_protocol()
    assert len(ROUNDS) == 4 and BUDGET["max_total_trials"] == 12
    assert protocol["portfolio"] == {
        "engine": "existing_qlib_backtest_service", "universe": "fixed_100",
        "topk": 20, "n_drop": 5, "weight": "equal", "rebalance": "weekly",
        "rebalance_days": 5, "deal_price": "open", "signal_lag_days": 1,
        "benchmark": "fixed_universe_equal_weight", "exchange": "CnExchange", "account": 1000000.0,
    }
    assert protocol["promotion_authority"] == "none"


def test_as_of_memory_rejects_future_fresh_frozen_daily_and_paths() -> None:
    memory = build_as_of_memory(round_number=2, research_end="2021-12-31",
        allowed_features=["mom_ret_1d"], prior_templates=[],
        prior_feedback=[{"evaluation_year": "2021", "rank_ic_band": "weak_positive"}],
        structure_fingerprints=["fp1"])
    assert validate_as_of_memory(memory, expected_round=2, expected_research_end="2021-12-31")
    for key in ("daily_ic", "holdout_2025", "fresh_metrics", "source_path"):
        corrupted = dict(memory); corrupted[key] = []
        with pytest.raises(ValueError):
            validate_as_of_memory(corrupted, expected_round=2, expected_research_end="2021-12-31")


def test_as_of_universe_lock_is_exactly_100_and_immutable(tmp_path: Path) -> None:
    dates = pd.date_range("2019-01-02", periods=20, freq="B")
    frame = pd.DataFrame([{"symbol": f"SH{index:06d}", "trade_date": day,
                           "style_ln_mv_float": float(200-index)}
                          for index in range(120) for day in dates])
    lock = select_fixed_universe(frame)
    assert len(lock["symbols"]) == 100 and lock["replacement_policy"] == "never"
    result = publish_historical_artifact(tmp_path, "fixed_universe_lock", lock)
    assert validate_historical_artifact("fixed_universe_lock", Path(result["path"]),
                                        result["universe_lock_id"])
    manifest = Path(result["path"]) / "manifest.json"
    payload = json.loads(manifest.read_text()); payload["symbols"].pop()
    manifest.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        validate_historical_artifact("fixed_universe_lock", Path(result["path"]),
                                     result["universe_lock_id"])


def test_final_selection_uses_only_pre_holdout_years_and_requires_two_positive_years() -> None:
    candidates = [{"origin_round": 1, "selected_trial": {"factor_instance_id": "fi_a"}},
                  {"origin_round": 4, "selected_trial": {"factor_instance_id": "fi_b"}}]
    metric = lambda value: {"mean_rank_ic": value}
    annual = {"fi_a": {str(year): metric(0.01) for year in range(2021, 2025)},
              "fi_b": {"2024": metric(0.10)}}
    qlib = {"fi_a": {str(year): {"net_excess": 0.01} for year in range(2021, 2025)},
            "fi_b": {"2024": {"net_excess": 1.0}}}
    result = lock_final_candidates(candidates, annual, qlib)
    assert result["selected_factor_instance_ids"] == ["fi_a"]
    assert result["selection_data_end"] == "2024-12-31" and result["holdout_metrics_used"] is False


def test_signal_materialization_locks_orientation(tmp_path: Path) -> None:
    source = tmp_path / "values.parquet"
    pd.DataFrame({"symbol": ["SH600000"], "trade_date": [pd.Timestamp("2021-01-04")],
                  "factor_value": [2.0]}).to_parquet(source, index=False)
    output = write_oriented_signal(source, tmp_path / "signal.parquet", -1)
    assert pd.read_parquet(output).iloc[0]["pred"] == -2.0
