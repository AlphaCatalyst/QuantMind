from __future__ import annotations

import numpy as np
import pandas as pd

from backend.services.engine.multi_horizon_label_research.engine import (
    _alignment,
    _cross_section_label,
    _label_values,
    _retrospective_gate,
    _walk_for_label,
)
from backend.services.engine.multi_horizon_label_research.models import (
    ExecutableLabelAuditV1,
    TechnicalReturnLabelFamilyV1,
)


def _bars(symbols: int = 100, sessions: int = 15) -> pd.DataFrame:
    rows = []
    for day_number, date in enumerate(pd.date_range("2024-01-02", periods=sessions, freq="B")):
        for ordinal in range(symbols):
            price = 10.0 + ordinal / 10.0 + day_number / 100.0
            rows.append(
                {
                    "symbol": f"SH{ordinal:06d}",
                    "trade_date": date,
                    "adjusted_open": price,
                    "adjusted_close": price * (1.0 + ordinal / 10000.0),
                    "tradable": True,
                }
            )
    return pd.DataFrame(rows)


def _fold(rankic: float = 0.01, excess: float = 0.05) -> dict:
    return {
        "fold_id": "fold",
        "metrics": {
            "mean_rankic": rankic,
            "coverage": 0.90,
            "infinity_count": 0,
            "pit_violation_count": 0,
            "csi300_excess": excess,
            "net_return": 0.08,
            "maximum_drawdown": -0.08,
            "turnover": 20.0,
            "best_10_days_contribution": 0.20,
        },
        "daily_rankic": [rankic, rankic],
    }


def test_label_family_is_preregistered_with_overlap_and_hac():
    family = TechnicalReturnLabelFamilyV1().payload()
    assert [row["horizon_sessions"] for row in family["labels"]] == [1, 5, 10]
    assert [row["overlapping_label"] for row in family["labels"]] == [False, True, True]
    assert [row["hac_lag"] for row in family["labels"]] == [10, 10, 15]
    assert family["fourth_horizon_allowed"] is False
    assert family["cross_section_transform"].startswith("same-date 5-MAD")


def test_executable_audit_keeps_metadata_execution_and_materialization_separate():
    audit = ExecutableLabelAuditV1("metadata", "executable", "materialized").payload()
    assert audit["metadata_formula"] == "metadata"
    assert audit["executable_formula"] == "executable"
    assert audit["actual_materialized_values"] == "materialized"
    assert audit["entry_price"] == "adjusted_open[T+1]"
    assert audit["exit_price"] == "adjusted_close[T+h]"
    assert audit["legacy_label_artifact_modified"] is False


def test_l1_l5_l10_use_official_sessions_and_adjusted_entry_exit_prices():
    bars = _bars()
    family = TechnicalReturnLabelFamilyV1().payload()
    for definition in family["labels"]:
        values, quality = _label_values(bars, definition)
        first = values.iloc[0]
        horizon = definition["horizon_sessions"]
        symbol = first["symbol"]
        source = bars[bars["symbol"] == symbol].reset_index(drop=True)
        expected = source.loc[horizon, "adjusted_close"] / source.loc[1, "adjusted_open"] - 1
        assert first["entry_date"] == source.loc[1, "trade_date"]
        assert first["exit_date"] == source.loc[horizon, "trade_date"]
        assert np.isclose(first["raw_return"], expected)
        assert quality["infinity_count"] == 0
        assert quality["pit_violation_count"] == 0


def test_missing_or_untradable_exit_is_not_filled_or_replaced():
    bars = _bars()
    target = (bars["symbol"] == "SH000000") & (bars["trade_date"] == pd.Timestamp("2024-01-09"))
    bars.loc[target, "tradable"] = False
    definition = TechnicalReturnLabelFamilyV1().payload()["labels"][1]
    values, _ = _label_values(bars, definition)
    row = values[(values["symbol"] == "SH000000") & (values["trade_date"] == pd.Timestamp("2024-01-02"))].iloc[0]
    assert np.isnan(row["raw_return"])
    assert row["sample_weight"] == 0
    assert row["missing_reason"] == "not_tradable"


def test_cross_section_transform_is_same_date_five_mad_population_zscore():
    frame = pd.DataFrame(
        {
            "trade_date": [pd.Timestamp("2024-01-02")] * 6,
            "raw_return": [-2.0, -1.0, 0.0, 1.0, 2.0, 100.0],
        }
    )
    value = _cross_section_label(frame)
    assert np.isclose(value.mean(), 0.0)
    assert np.isclose(value.std(ddof=0), 1.0)
    assert value.iloc[-1] < 3.0


def test_quality_gate_requires_85_percent_and_ninety_daily_members():
    _, quality = _label_values(_bars(), TechnicalReturnLabelFamilyV1().payload()["labels"][0])
    assert quality["coverage"] >= 0.85
    assert quality["daily_finite_members_median"] >= 90
    assert quality["passed"] is True


def test_walk_purge_is_never_shorter_than_label_horizon_or_ten():
    walk = {"walk_forward_spec_id": "pwfs1_x", "purge_sessions": 10}
    for definition in TechnicalReturnLabelFamilyV1().payload()["labels"]:
        derived = _walk_for_label(walk, definition)
        assert derived["purge_sessions"] == max(10, definition["horizon_sessions"])
        assert derived["walk_forward_spec_id"].startswith("pwfs1_")
        assert derived["base_walk_forward_spec_id"] == "pwfs1_6a226e117f7eca56f380f1e7445bcb462dc7b7ffeedfe5d0e076b6d4a9c0a7d9"


def test_retrospective_gate_uses_frozen_thresholds_and_incremental_value():
    folds = [_fold() for _ in range(4)]
    stability = {"concentration_gate": {"passed": True}}
    baseline = {"bundle_name": "existing_technical_core"}
    assert _retrospective_gate(baseline, folds, stability, None)["passed"]
    expanded = {"bundle_name": "expanded_technical_space"}
    result = _retrospective_gate(expanded, folds, stability, folds)
    assert result["checks"]["coverage"]
    assert not result["checks"]["incremental_value"]
    assert not result["passed"]


def test_alignment_compares_all_three_labels_without_selecting_one():
    rows = {
        "technical_return_1d": [_fold(0.001, 0.01) for _ in range(4)],
        "technical_return_5d": [_fold(0.005, 0.03) for _ in range(4)],
        "technical_return_10d": [_fold(0.010, 0.05) for _ in range(4)],
    }
    result = _alignment("existing_technical_core", rows)
    assert result["rankic_improves_with_horizon"] is True
    assert result["cross_year_consistent_improvement"] is True
    assert result["long_horizon_only_2024_driven"] is False
    assert result["selection_performed"] is False
    assert result["l10_matches_ten_session_rebalance_semantically"] is True
