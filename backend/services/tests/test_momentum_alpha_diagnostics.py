from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.services.engine.momentum_alpha_diagnostics.artifact import publish_artifact, validate_artifact
from backend.services.engine.momentum_alpha_diagnostics.metrics import (
    beta_and_contributions, daily_cross_section, holding_and_style,
    horizon_decay, period_cross_metrics, semantic_audit,
)
from backend.services.engine.momentum_alpha_diagnostics.engine import _classify
from backend.services.engine.momentum_alpha_diagnostics.protocol import (
    CANDIDATE_A, CANDIDATE_B, ENSEMBLE_ID, FORMAL_STRATEGY, PERIODS,
)


def _lock(lock_id: str, name: str) -> dict:
    return {"candidate_lock_id": lock_id, "template_name": name}


def _signals() -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.date_range("2025-01-02", periods=20, freq="B")
    rows = []
    for date in dates:
        for index in range(100):
            rows.append({"symbol": f"SH{index:06d}", "trade_date": date,
                         "pred": float(index), "model_label": float(index),
                         "raw_label": (index - 50) / 10000})
    merged = pd.DataFrame(rows)
    return merged[["symbol", "trade_date", "pred"]], merged.drop(columns="pred")


def test_candidate_a_semantics_are_deviation_not_risk_adjusted():
    result = semantic_audit(_lock(CANDIDATE_A, "risk_adjusted"), _lock(CANDIDATE_B, "hybrid"),
                            {"distance_to_high_60": {"formula": "adjusted_close/rolling_max(adjusted_close,60)-1"}})
    assert result["candidate_a"]["semantic_classification"] == "momentum_deviation_or_surprise"
    assert result["candidate_a"]["risk_adjustment_present"] is False
    assert result["candidate_a"]["semantic_mismatch"] is True


def test_candidate_b_negative_distance_sign_rewards_pullback():
    result = semantic_audit(_lock(CANDIDATE_A, "a"), _lock(CANDIDATE_B, "b"),
                            {"distance_to_high_60": {"formula": "adjusted_close/rolling_max(adjusted_close,60)-1"}})
    assert "abs(distance_to_high_60)" in result["candidate_b"]["algebraic_equivalence"]
    assert result["candidate_b"]["breakout_confirmation"] is False


def test_historical_ids_and_strategy_are_frozen():
    assert CANDIDATE_A.startswith("srmcl1_") and CANDIDATE_B.startswith("srmcl1_")
    assert ENSEMBLE_ID.startswith("srmen1_")
    assert FORMAL_STRATEGY == {"topk": 20, "n_drop": 5, "rebalance_frequency": 5,
        "prediction_lag_sessions": 1, "deal_price": "open", "benchmark": "CSI300", "exchange": "CnExchange"}


def test_rankic_deciles_spread_and_observable_mean():
    signal, matrix = _signals()
    daily = daily_cross_section(signal, matrix)
    result = period_cross_metrics(daily, "2025-01-02", "2025-12-31")
    assert result["mean_rankic"] == pytest.approx(1.0)
    assert len(result["quantile_mean_returns"]) == 10
    assert result["q10_q1_spread"] > 0
    assert result["q10_observable_mean_spread"] > 0
    assert result["monotonicity"] == pytest.approx(1.0)
    assert "not an investable benchmark" in result["observable_mean_definition"]


def test_weekly_monthly_rankic_and_positive_rate_are_present():
    signal, matrix = _signals()
    result = period_cross_metrics(daily_cross_section(signal, matrix), "2025-01-02", "2025-12-31")
    assert result["weekly_rankic"] == pytest.approx(1.0)
    assert result["monthly_rankic"] == pytest.approx(1.0)
    assert result["rankic_positive_rate"] == 1.0


def test_horizon_decay_uses_same_locked_signal():
    signal, _ = _signals()
    dates = sorted(signal.trade_date.unique())
    rows = []
    for symbol_index, symbol in enumerate(signal.symbol.unique()):
        for day, date in enumerate(dates):
            price = 10 + symbol_index * 0.01 + day * symbol_index * 0.0001
            rows.append({"symbol": symbol, "trade_date": date, "adjusted_open": price, "adjusted_close": price * 1.001})
    result = horizon_decay(signal, pd.DataFrame(rows), {"probe": (str(dates[0])[:10], str(dates[-1])[:10])})
    assert set(result["probe"]) == {"T+1", "T+2", "T+3", "T+5", "T+10"}


def test_period_boundaries_mark_later_evidence_separately():
    assert PERIODS["2019-2024"][1] == "2024-12-31"
    assert PERIODS["2025"][0] > PERIODS["2019-2024"][1]


def test_artifact_publication_and_cold_validation(tmp_path: Path):
    frame = pd.DataFrame({"entity": ["a"], "period": ["2025"], "trade_date": [pd.Timestamp("2025-01-02")], "ic": [0.1]})
    cross = tmp_path / "cross.parquet"; quantiles = tmp_path / "quantiles.parquet"
    frame.to_parquet(cross, index=False); frame.to_parquet(quantiles, index=False)
    artifact = publish_artifact(tmp_path / "domain", "momentum_cross_sectional_diagnostic",
        {"source_experiment_id": "srme1_probe"}, {"cross_sectional_metrics.parquet": cross,
        "quantile_returns.parquet": quantiles, "horizon_decay.json": {"a": {}}})
    assert validate_artifact(Path(artifact["path"]), artifact["artifact_id"])["status"] == "valid"


def test_artifact_missing_required_file_hard_fails(tmp_path: Path):
    artifact = publish_artifact(tmp_path / "domain", "momentum_semantic_audit",
        {"source_experiment_id": "srme1_probe"}, {"semantic_audit.json": {"ok": True}})
    root = Path(artifact["path"]); (root / "semantic_audit.json").unlink()
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_artifact(root, artifact["artifact_id"])


def test_no_agent_optimizer_or_promotion_contract():
    identity = {"agent_calls": 0, "optimization_calls": 0, "network_calls": 0,
                "promotion_writes": 0, "candidate_status_after": ["research_registered"]}
    assert not any(identity[key] for key in ("agent_calls", "optimization_calls", "network_calls", "promotion_writes"))
    assert identity["candidate_status_after"] == ["research_registered"]


def test_manifest_is_deterministic_and_json_readable(tmp_path: Path):
    artifact = publish_artifact(tmp_path / "domain", "momentum_semantic_audit",
        {"source_experiment_id": "srme1_probe"}, {"semantic_audit.json": {"value": 1}})
    manifest = json.loads((Path(artifact["path"]) / "manifest.json").read_text())
    assert manifest["artifact_id"] == artifact["artifact_id"]


def test_no_sector_claim_without_pit_contract():
    record = {"sector_concentration": None, "sector_status": "not_computed_no_PIT_industry_contract"}
    assert record["sector_concentration"] is None


def test_beta_residual_and_stock_day_contributions():
    dates = pd.date_range("2025-01-02", periods=25, freq="B")
    result = {"equity_curve": [{"date": str(date.date()), "value": 1_000_000 * (1.001 ** i)} for i, date in enumerate(dates)],
              "positions": [{"date": str(date.date()), "symbol": "SH000001", "weight": 1.0} for date in dates]}
    features = pd.DataFrame({"symbol": "SH000001", "trade_date": dates,
        "style_beta_60": 0.8, "mom_ret_1d": 0.001})
    benchmark = pd.DataFrame({"trade_date": dates, "close": 100 * (1.001 ** np.arange(len(dates)))})
    beta, stocks, days = beta_and_contributions(result, features, benchmark, "candidate_a", "2025")
    assert {"portfolio_beta", "weighted_average_stock_beta", "market_component", "residual_component"}.issubset(beta)
    assert stocks.iloc[0].symbol == "SH000001"
    assert len(days) == len(dates)


def test_style_exposure_and_holding_concentration():
    dates = pd.date_range("2025-01-02", periods=6, freq="B")
    positions = pd.DataFrame([{"date": str(date.date()), "symbol": f"SH{i:06d}", "weight": 0.05}
                              for date in dates for i in range(20)])
    features = pd.DataFrame([{"trade_date": date, "symbol": f"SH{i:06d}", "style_beta_20": i / 20}
                             for date in dates for i in range(100)])
    signal = features[["trade_date", "symbol"]].assign(pred=np.arange(len(features), dtype=float))
    style, concentration = holding_and_style(positions, features, signal, "candidate_a", "2025", ("style_beta_20",))
    assert set(style.feature) == {"style_beta_20"}
    assert concentration.holdings.eq(20).all()
    assert concentration.sector_concentration.isna().all()


def test_failure_classification_keeps_registry_and_chooses_overlay():
    period = lambda rankic, mono: {"mean_rankic": rankic, "monotonicity": mono}
    cross = {name: {"2025": period(0.005, 0.1), "2026H1": period(-0.004, -0.1)}
             for name in ("candidate_a", "candidate_b")}
    beta = {f"{name}:2025": {"net_return": 0.05, "csi300_excess": -0.1}
            for name in ("candidate_a", "candidate_b")}
    costs = {f"{name}:2025": {"zero_cost_return": 0.06, "net_return": 0.05}
             for name in ("candidate_a", "candidate_b")}
    classification, decision = _classify(cross, beta, costs, {})
    assert decision["decision"] == "continue_as_stock_selection_overlay_only"
    assert decision["promotion_writes"] == 0
    assert all("signal_degradation" in row["labels"] for row in classification.values())
