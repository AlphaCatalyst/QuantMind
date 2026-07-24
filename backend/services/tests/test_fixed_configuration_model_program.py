from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.services.engine.fixed_configuration_model_program.engine import (
    _cross_section_transform,
    _daily_statistics,
    _gate,
    _seed_stability,
    select_bundle_c,
)
from backend.services.engine.fixed_configuration_model_program.models import (
    FEATURE_CATALOG_ID,
    PRIMITIVE_CATALOG_ID,
    FixedConfigurationModelSpecV1,
    ModelFeatureBundleSpecV1,
    PurgedWalkForwardSpecV1,
)


def _frame() -> pd.DataFrame:
    rows = []
    rng = np.random.default_rng(7)
    for day in pd.date_range("2019-01-02", periods=30, freq="B"):
        for ordinal in range(25):
            base = rng.normal()
            rows.append({
                "trade_date": day,
                "symbol": f"SH{ordinal:06d}",
                "a": base,
                "duplicate_a": base,
                "b": rng.normal(),
                "model_label": base * .01 + rng.normal(scale=.01),
                "raw_label": base * .01 + rng.normal(scale=.01),
            })
    return pd.DataFrame(rows)


def test_fixed_model_spec_freezes_existing_lightgbm_and_three_seeds():
    spec = FixedConfigurationModelSpecV1().payload()
    assert spec["model_type"] == "lightgbm"
    assert spec["label_name"] == "model_label"
    assert spec["seeds"] == (20260701, 20260702, 20260703)
    assert spec["early_stopping_policy"] == "disabled_fixed_rounds"
    assert spec["model_hyperparameter_optimization_calls"] == 0
    assert spec["strategy_optimization_calls"] == 0
    assert spec["combined_optimization_calls"] == 0
    assert spec["feature_catalog_id"] == FEATURE_CATALOG_ID
    assert spec["primitive_catalog_id"] == PRIMITIVE_CATALOG_ID


def test_walk_forward_has_four_expanding_outer_folds_and_ten_session_purge():
    walk = PurgedWalkForwardSpecV1().payload()
    assert len(walk["folds"]) == 4
    assert walk["purge_sessions"] == 10
    assert [row["train_start"] for row in walk["folds"]] == ["2019-01-02"] * 4
    assert walk["outer_test_used_for_training"] is False
    assert walk["outer_test_used_for_preprocessing_fit"] is False
    assert walk["outer_test_used_for_feature_selection"] is False


def test_walk_forward_rejects_short_purge():
    with pytest.raises(ValueError, match="purge"):
        PurgedWalkForwardSpecV1(purge_sessions=9).payload()


def test_bundle_c_requires_train_only_unlabeled_selection():
    with pytest.raises(ValueError, match="train"):
        ModelFeatureBundleSpecV1(
            "spec", "combined_decorrelated_technical", ("a",),
            "invalid", False,
        ).payload()


def test_bundle_c_deduplicates_without_label_access():
    selected, evidence = select_bundle_c(_frame(), ["a", "duplicate_a", "b"])
    assert len({"a", "duplicate_a"} & set(selected)) == 1
    assert "b" in selected
    assert evidence["label_reads"] == 0
    assert evidence["performance_reads"] == 0
    assert evidence["selection_data"] == "train_only"
    assert evidence["redundancy_rejections"][0]["absolute_spearman"] >= .95


def test_cross_section_transform_is_same_date_and_has_fixed_missing_policy():
    frame = _frame()
    frame.loc[0, "a"] = np.nan
    transformed = _cross_section_transform(frame, ["a", "b"])
    assert transformed.shape == (len(frame), 2)
    assert np.isfinite(transformed.to_numpy()).all()
    for _, positions in frame.groupby("trade_date").groups.items():
        values = transformed.loc[positions, "b"]
        assert abs(float(values.mean())) < 1e-5


def test_daily_statistics_uses_official_label_rankic_and_reports_tail_diagnostics():
    frame = _frame().rename(columns={"a": "raw_prediction"})
    metrics, daily, rows = _daily_statistics(frame)
    assert len(daily) == len(rows) == 30
    assert metrics["mean_rankic"] > 0
    assert metrics["coverage"] == 1.0
    assert metrics["infinity_count"] == 0
    assert metrics["q10_q1"] is not None
    assert metrics["top20_universe_spread"] is not None


def test_seed_ensemble_stability_does_not_select_seed():
    frame = _frame()
    base = frame["a"].to_numpy()
    stability = _seed_stability([base, base + 1e-7, base - 1e-7], frame)
    assert stability["single_seed_selected"] is False
    assert stability["minimum_prediction_pearson"] > .999
    assert stability["minimum_prediction_spearman"] > .999


def test_retrospective_gate_enforces_stability_and_incremental_value():
    folds = []
    for _ in range(4):
        folds.append({"metrics": {
            "mean_rankic": .006,
            "coverage": .99,
            "infinity_count": 0,
            "pit_violation_count": 0,
            "csi300_excess": .04,
            "turnover": 12.0,
            "best_10_days_contribution": .20,
            "maximum_drawdown": -.10,
        }})
    stability = {"concentration_gate": {"passed": True}}
    baseline_bundle = {"bundle_name": "existing_technical_core"}
    assert _gate(baseline_bundle, folds, stability, None)["passed"]
    expanded = {"bundle_name": "expanded_technical_space"}
    assert not _gate(expanded, folds, stability, folds)["passed"]


def test_strategy_protocol_is_frozen_without_optimization():
    strategy = FixedConfigurationModelSpecV1().payload()["strategy_protocol"]
    assert strategy == {
        "topk": 20,
        "n_drop": 5,
        "rebalance_interval": 10,
        "weighting": "equal_weight",
        "signal_lag": 1,
        "execution": "open",
        "benchmark": "CSI300",
    }
