from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.services.engine.low_frequency_momentum.artifact import publish_artifact, validate_artifact
from backend.services.engine.low_frequency_momentum.engine import (
    _comparison, _execution_protocol, build_signal_values, candidate_ordering,
    holding_metrics, signal_quality,
)
from backend.services.engine.low_frequency_momentum.protocol import (
    ANNUAL_PERIODS, FULL_PERIOD, PROTOCOLS, REPORT_PERIODS, SIGNALS,
)


def matrix() -> pd.DataFrame:
    dates = pd.date_range("2021-01-04", periods=4)
    rows = []
    for day, date in enumerate(dates):
        for member in range(100):
            rows.append({"symbol": f"SH{600000 + member}", "trade_date": date,
                         "momentum_120_20": member + day, "momentum_60_10": member - day,
                         "momentum_efficiency_60": member / 100, "residual_momentum_60": member * 2})
    return pd.DataFrame(rows)


def test_four_pre_registered_signals_have_fixed_formulas_and_no_parameters():
    assert tuple(SIGNALS) == ("classic_long_term_skip_recent", "dual_horizon_skip_recent_consensus",
                              "path_quality_long_term_momentum", "residual_absolute_momentum_consensus")
    assert SIGNALS["classic_long_term_skip_recent"]["canonical_formula"] == "cs_rank(momentum_120_20)"
    assert all(set(value["fixed_weights"].values()) in (set(), {.5}) for value in SIGNALS.values())


@pytest.mark.parametrize("name", SIGNALS)
def test_signal_builds_exactly_one_value_per_input_key(name):
    source = matrix()
    output = build_signal_values(source, name)
    assert len(output) == len(source)
    assert not output.duplicated(["symbol", "trade_date"]).any()
    assert output["factor_value"].notna().all()


def test_classic_signal_is_cross_sectional_rank_and_consensus_is_equal_weighted():
    source = matrix()
    classic = build_signal_values(source, "classic_long_term_skip_recent")
    assert classic.groupby("trade_date")["factor_value"].max().eq(1.0).all()
    consensus = build_signal_values(source, "dual_horizon_skip_recent_consensus")
    assert np.allclose(consensus.groupby("trade_date")["factor_value"].mean(), 0.0)


def test_signal_quality_enforces_members_and_duplicate_keys():
    source = build_signal_values(matrix(), "classic_long_term_skip_recent")
    assert signal_quality(source)["passed"]
    duplicate = pd.concat([source, source.iloc[[0]]], ignore_index=True)
    assert not signal_quality(duplicate)["passed"]


def test_protocols_are_only_b0_and_l1_with_trade_session_intervals():
    assert set(PROTOCOLS) == {"B0", "L1"}
    assert PROTOCOLS["B0"]["rebalance_interval"] == 5
    assert PROTOCOLS["L1"]["rebalance_interval"] == 10
    assert all(value["topk"] == 20 and value["n_drop"] == 5 for value in PROTOCOLS.values())
    protocol = _execution_protocol()
    assert protocol["candidate_protocol"] == "L1" and not protocol["strategy_optimization_allowed"]
    assert protocol["third_frequency_tested"] is False


def test_period_contract_excludes_reports_from_selection():
    assert tuple(ANNUAL_PERIODS) == ("2021", "2022", "2023", "2024")
    assert FULL_PERIOD == ("2021-01-04", "2024-12-31")
    assert tuple(REPORT_PERIODS) == ("2025", "2026H1")


def test_turnover_cost_and_net_decomposition():
    result = _comparison({"turnover": 50.0, "transaction_cost": 1000.0, "net_return": .1,
                          "gross_return": .12, "cost_drag": .02},
                         {"turnover": 25.0, "transaction_cost": 600.0, "net_return": .11,
                          "gross_return": .12, "cost_drag": .01})
    assert result["turnover_reduction_ratio"] == .5
    assert result["cost_reduction_ratio"] == .4
    assert result["net_improvement_after_cost"] == pytest.approx(.01)


def test_holding_metrics_prove_longer_holding_from_daily_positions():
    positions = []
    for date, symbols in (("2021-01-04", ("A", "B")), ("2021-01-05", ("A", "B")),
                          ("2021-01-06", ("A", "C")), ("2021-01-07", ("A", "C"))):
        positions.extend({"date": date, "symbol": symbol, "weight": .5, "amount": 1, "side": "long"} for symbol in symbols)
    metrics, frame = holding_metrics({"positions": positions, "trades": []})
    assert metrics["evidence_available"]
    assert metrics["number_of_entries"] == 3 and metrics["number_of_exits"] == 1
    assert metrics["holding_overlap"] == pytest.approx(1 / 3)
    assert len(frame) == 8


def test_candidate_ordering_is_stable_and_does_not_use_report_periods():
    base = {"eligibility": {"positive_rankic_year_count": 3, "positive_excess_year_count": 3,
            "median_rankic": .01, "worst_rankic": -.001, "median_excess": .02,
            "median_turnover_reduction": .4, "median_cost_reduction": .3,
            "median_l1_net_return": .1, "median_b0_net_return": .05,
            "median_best10_contribution": .2, "maximum_existing_factor_correlation": .3},
            "full": {"L1": {"metrics": {"max_drawdown": -.1}}}, "signal_spec_id": "b"}
    better = {**base, "signal_spec_id": "a"}
    assert sorted([base, better], key=candidate_ordering)[0]["signal_spec_id"] == "a"


def test_signal_artifact_completeness_and_fixed_parameter_boundary(tmp_path):
    identity = {"schema_version": "low-frequency-momentum-signal-spec-v1", "provider_id": "tushare-pro-v1",
        "signal_spec_id": "semantic", "name": "classic", "economic_hypothesis": "h",
        "canonical_formula": "cs_rank(x)", "canonical_ast": {}, "input_feature_ids": ["mf"],
        "fixed_weights": {}, "optimizable_parameters": [], "orientation": 1, "universe_id": "u",
        "dataset_id": "d", "date_range": ["2019", "2026"], "missing_policy": "none",
        "signal_lag": 1, "structural_fingerprint": "f", "promotion_writes": 0}
    artifact = publish_artifact(tmp_path, "low_frequency_momentum_signal_spec", identity, {"signal_spec.json": identity})
    assert validate_artifact(artifact["path"], artifact["signal_artifact_id"])["status"] == "valid"
    with pytest.raises(ValueError, match="parameter boundary"):
        publish_artifact(tmp_path / "bad", "low_frequency_momentum_signal_spec",
                         identity | {"optimizable_parameters": ["window"]}, {"signal_spec.json": identity})


def test_candidate_lock_is_l1_research_only(tmp_path):
    identity = {"schema_version": "low-frequency-momentum-candidate-lock-v1", "provider_id": "tushare-pro-v1",
        "signal_spec_id": "s", "signal_artifact_id": "a", "economic_hypothesis": "h",
        "canonical_formula": "f", "input_features": ["x"], "fixed_weights": {}, "protocol_id": "L1",
        "annual_2021_2024_metrics": {}, "full_period_metrics": {}, "baseline_comparison": {},
        "turnover_reduction": .4, "cost_reduction": .3, "concentration": .2,
        "existing_factor_correlations": {}, "eligibility_evidence": {}, "status": "research_registered",
        "promotion_writes": 0}
    artifact = publish_artifact(tmp_path, "low_frequency_momentum_candidate_lock", identity, {"candidate.json": identity})
    manifest = json.loads((Path(artifact["path"]) / "manifest.json").read_text())
    assert manifest["identity"]["status"] == "research_registered"
    with pytest.raises(ValueError, match="research-only"):
        publish_artifact(tmp_path / "bad", "low_frequency_momentum_candidate_lock",
                         identity | {"status": "production"}, {})
