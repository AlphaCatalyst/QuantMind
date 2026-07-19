from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import numpy as np
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
from backend.services.engine.historical_agent_experiment.missingness import (
    _trace_expression, audit_locked_signals,
)


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


def test_locked_signal_missingness_audit_attributes_source_feature_without_fill(
    tmp_path: Path,
) -> None:
    symbols = [f"SH{600000 + index:06d}" for index in range(100)]
    dates = pd.to_datetime([
        "2024-12-31", "2025-01-02", "2025-01-03",
        "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08",
    ])
    rows = []
    for date_index, day in enumerate(dates):
        for symbol_index, symbol in enumerate(symbols):
            rows.append({
                "symbol": symbol, "trade_date": day, "open": 10.0, "close": 10.0,
                "factor": 1.0, "mom_ret_1d": symbol_index / 100 + date_index / 1000,
                "style_idio_vol_20": (
                    np.nan if day in dates[3:5] else (100 - symbol_index) / 100
                ),
            })
    matrix = pd.DataFrame(rows).sort_values(["trade_date", "symbol"]).reset_index(drop=True)
    dataset = tmp_path / "dataset"; dataset.mkdir()
    matrix.to_parquet(dataset / "historical_matrix.parquet", index=False)
    (dataset / "manifest.json").write_text(json.dumps({"dataset_id": "fuhd_test"}))

    expressions = [
        {"type": "cs_zscore", "operand": {"type": "subtract",
            "left": {"type": "feature", "name": "mom_ret_1d"},
            "right": {"type": "cs_rank", "operand": {"type": "feature", "name": "style_idio_vol_20"}}}},
        {"type": "cs_zscore", "operand": {"type": "subtract",
            "left": {"type": "rolling_mean", "operand": {"type": "feature", "name": "mom_ret_1d"},
                     "window": {"type": "parameter", "name": "window"}},
            "right": {"type": "cs_rank", "operand": {"type": "feature", "name": "style_idio_vol_20"}}}},
    ]
    factor_ids = ["fi_test_one", "fi_test_two"]
    factor_values_ids = ["fv_test_one", "fv_test_two"]
    candidates, factor_dirs, signal_paths, oriented = [], {}, {}, {}
    period_mask = matrix.trade_date.between("2026-01-05", "2026-06-23")
    for index, (factor_id, values_id, expression) in enumerate(zip(factor_ids, factor_values_ids, expressions)):
        parameters = {} if index == 0 else {"window": 2}
        value, _ = _trace_expression(expression, matrix, parameters, period_mask)
        directory = tmp_path / "factor-values" / values_id; directory.mkdir(parents=True)
        pd.DataFrame({"symbol": matrix.symbol, "trade_date": matrix.trade_date,
                      "factor_value": value}).to_parquet(directory / "values.parquet", index=False)
        (directory / "manifest.json").write_text(json.dumps({
            "factor_values_id": values_id, "dataset_snapshot_id": "ds_test",
        }))
        factor_dirs[factor_id] = directory
        oriented[factor_id] = value
        signal = pd.DataFrame({"symbol": matrix.symbol, "trade_date": matrix.trade_date, "pred": value})
        signal_path = tmp_path / "signals" / f"{factor_id}.parquet"
        signal_path.parent.mkdir(exist_ok=True); signal.to_parquet(signal_path, index=False)
        signal_paths[factor_id] = signal_path
        candidates.append({"template": {"expression": expression}, "selected_trial": {
            "factor_instance_id": factor_id, "factor_values_id": values_id,
            "parameters": parameters, "orientation": 1,
        }})
    combo = matrix[["symbol", "trade_date"]].copy()
    normalized = []
    for value in oriented.values():
        normalized.append(value.groupby(matrix.trade_date).transform(
            lambda x: (x - x.mean()) / x.std(ddof=0)
            if x.notna().sum() > 1 and x.std(ddof=0) > 0 else np.nan
        ))
    combo["pred"] = pd.concat(normalized, axis=1).mean(axis=1, skipna=False)
    combo_path = tmp_path / "signals" / "equal_weight_combo.parquet"
    combo.to_parquet(combo_path, index=False); signal_paths["equal_weight_combo"] = combo_path

    view = tmp_path / "qlib-view"
    (view / "calendars").mkdir(parents=True); (view / "instruments").mkdir()
    (view / "features").mkdir()
    calendar = [day.strftime("%Y-%m-%d") for day in dates]
    (view / "calendars" / "day.txt").write_text("\n".join(calendar) + "\n")
    (view / "instruments" / "all.txt").write_text("\n".join(
        f"{symbol}\t{calendar[0]}\t{calendar[-1]}" for symbol in symbols
    ) + "\n")
    for symbol in symbols:
        directory = view / "features" / symbol.lower(); directory.mkdir()
        np.asarray([0.0, *([10.0] * len(calendar))], dtype="<f4").tofile(directory / "open.day.bin")
    (view / "manifest.json").write_text(json.dumps({
        "qlib_view_id": "qcv_test", "dataset_id": "fuhd_test",
        "calendar_boundary_sentinel": None,
    }))
    result = audit_locked_signals(
        dataset_directory=dataset,
        universe_lock={"symbols": symbols, "universe_lock_id": "ful_test"},
        candidates=candidates, qlib_view_directory=view,
        factor_values_directories=factor_dirs, signal_paths=signal_paths,
        source_experiment_id="hae_test", source_backtest_result_id="qbr_test",
        output_root=tmp_path / "artifacts",
    )
    assert result["layer_metrics"]["original_gate_nan_ratio"] == 0.5
    assert result["root_cause"]["primary_layer"] == "source_feature"
    assert result["root_cause"]["implementation_defect_proven"] is False
    assert result["root_cause"]["causes"][-1]["classification"] == "UNRESOLVED_DATA_QUALITY"
    assert result["qlib_alignment"]["view_truncation"] is False
    assert result["qlib_alignment"]["score_nan_added_by_qlib_join"] == 0
    assert result["audit"]["status"] == "created"
    assert result["followup"]["status"] == "created"
