from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.services.engine.momentum_tail_alpha.artifact import publish_artifact, validate_artifact
from backend.services.engine.momentum_tail_alpha.engine import (
    _period_summary, analysis_frame, classify, component_diagnostics, decay, diagnostic_spec,
    monthly_2023, quantile_and_tail, stability_and_transition,
    stock_contributions, style_and_beta, top_n_diagnostics,
)
from backend.services.engine.momentum_tail_alpha.protocol import (
    DECAY_HORIZONS, HORIZONS, PERIODS, SOURCE_FORMULA, SOURCE_SIGNAL_NAME,
    TOP_NS,
)


def synthetic(days: int = 80) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2023-01-03", periods=days)
    rows, normalized = [], []
    for ordinal, date in enumerate(dates):
        for member in range(100):
            symbol = f"SH{600000 + member}"
            score = member / 100 + ordinal / 10000
            rows.append({"symbol": symbol, "trade_date": date, "model_label": score,
                         "momentum_120_20": score, "residual_momentum_60": score,
                         "log_circ_mv": 10 + member / 100, "style_idio_vol_20": 0.2,
                         "style_idio_vol_60": 0.3, "volatility_20": 0.2,
                         "volatility_60": 0.3, "amount_ratio_20": 1.0,
                         "distance_to_high_60": -score, "style_beta_20": 1.0,
                         "style_beta_60": 1.0})
            normalized.append({"symbol": symbol, "trade_date": date,
                               "adjusted_close": 10 * (1 + .0001 * member) ** ordinal})
    matrix = pd.DataFrame(rows)
    values = matrix[["symbol", "trade_date"]].copy()
    values["factor_value"] = matrix["momentum_120_20"]
    benchmark = pd.DataFrame({"trade_date": dates, "close": 100 * 1.0002 ** np.arange(days)})
    return values, matrix, pd.DataFrame(normalized), benchmark


def test_signal_d_identity_formula_and_fixed_boundary():
    assert SOURCE_SIGNAL_NAME == "residual_absolute_momentum_consensus"
    assert SOURCE_FORMULA == "0.5*cs_zscore(momentum_120_20)+0.5*cs_zscore(residual_momentum_60)"
    assert HORIZONS == (1, 5, 10) and DECAY_HORIZONS[-1] == 40
    assert TOP_NS == (5, 10, 20, 30)


def test_spec_forbids_optimization_selection_registry_and_promotion():
    signal = {"signal_artifact_id": "lfmsa1_x", "signal_spec_id": "lfmss1_x",
              "fixed_weights": {"momentum_120_20": .5, "residual_momentum_60": .5}}
    study = {"signal_artifact_ids": ["lfmsa1_x"]}
    spec = diagnostic_spec(study, signal)
    assert not spec["parameter_optimization_allowed"]
    assert not spec["top_n_selection_allowed"]
    assert not spec["candidate_lock_allowed"]
    assert not spec["registry_write_allowed"] and not spec["promotion_allowed"]


def test_deciles_tail_spreads_extreme_ic_and_monotonicity():
    values, matrix, normalized, _ = synthetic()
    frame = analysis_frame(values, matrix, normalized)
    quantiles, tail, summary = quantile_and_tail(frame)
    assert set(quantiles.decile) == set(range(1, 11))
    row = tail[(tail.period == "2023") & (tail.horizon == 1)].iloc[0]
    assert row.q10_q1 > 0 and row.q10_universe > 0 and row.top_tail_spread > 0
    assert row.formal_label_rankic > 0 and row.forward_close_rankic > 0
    assert row.extreme_rank_ic > 0 and row.full_decile_monotonicity > 0
    assert "T+10" in summary["2023"]


def test_top_n_is_fixed_gross_only_and_never_selects():
    values, matrix, normalized, benchmark = synthetic()
    frame = analysis_frame(values, matrix, normalized)
    results, holdings = top_n_diagnostics(frame, benchmark)
    rows = results[results.period == "2023"]
    assert tuple(rows.top_n) == TOP_NS
    assert rows.net_return.isna().all()
    assert rows.diagnostic_only.all() and rows.not_strategy_optimization.all()
    assert rows.not_candidate_selection.all() and not holdings.empty


def test_contributions_include_top20_q10_q1_and_exclusions():
    values, matrix, normalized, benchmark = synthetic()
    frame = analysis_frame(values, matrix, normalized)
    _, holdings = top_n_diagnostics(frame, benchmark)
    rows, summary = stock_contributions(frame, holdings)
    assert set(rows.source) == {"top20_10day", "q10_daily", "q1_daily"}
    assert all("return_excluding_top_5" in value and "return_excluding_bottom_5" in value
               for value in summary.values())


def test_monthly_2023_separates_formal_label_and_forward_close_rankic():
    values, matrix, normalized, benchmark = synthetic()
    frame = analysis_frame(values, matrix, normalized)
    result = monthly_2023(frame, benchmark)
    assert list(result.month) == ["2023-01", "2023-02", "2023-03", "2023-04"]
    assert {"formal_label_rankic", "forward_close_rankic", "q10_universe"} <= set(result)


def test_beta_and_style_exposure_use_fixed_top20():
    values, matrix, normalized, benchmark = synthetic()
    frame = analysis_frame(values, matrix, normalized)
    style, beta, summary = style_and_beta(frame, benchmark)
    assert not style.empty and not beta.empty
    assert summary["2023"]["weighted_style_beta_60"] == pytest.approx(1.0)
    assert {"top20_weighted_mean", "universe_median", "signal_feature_spearman"} <= set(style)


def test_absolute_and_residual_components_are_diagnosed_separately():
    values, matrix, normalized, _ = synthetic()
    result = component_diagnostics(analysis_frame(values, matrix, normalized))
    assert set(result.component) == {"momentum_120_20", "residual_momentum_60"}
    assert {"formal_label_rankic", "forward_close_rankic", "top_tail_universe"} <= set(result)


def test_signal_decay_is_diagnostic_and_does_not_change_frequency():
    values, matrix, normalized, _ = synthetic()
    result = decay(analysis_frame(values, matrix, normalized))
    assert set(result) == {"T+1", "T+5", "T+10", "T+20", "T+40"}
    assert result["T+1"]["rankic"] > 0


def test_score_stability_and_rank_transition_include_tail_paths():
    values, matrix, normalized, _ = synthetic()
    frame = analysis_frame(values, matrix, normalized)
    summary, transition = stability_and_transition(frame)
    assert set(summary["score_autocorrelation"]) == {"lag_1", "lag_5", "lag_10", "lag_20"}
    assert set(summary["membership_overlap"]) == {"top10", "top20", "top30"}
    assert summary["q10_retention"] == pytest.approx(1.0)
    assert not transition.empty


@pytest.mark.parametrize(
    "rankic,tail,top,report,expected",
    [
        (4, 4, 6, 2, "broad_monotonic_factor"),
        (2, 4, 6, 2, "tail_selection_overlay"),
        (2, 1, 5, 0, "defensive_relative_factor"),
        (0, 0, 0, 0, "no_reliable_alpha"),
    ],
)
def test_classification_contract(rankic, tail, top, report, expected):
    tail_rows = []
    for index, period in enumerate(PERIODS):
        research = period in tuple(list(PERIODS)[:4])
        tail_rows.append({"period": period, "horizon": 1,
                          "formal_label_rankic": .01 if research and index < rankic else (-.01 if research else .01),
                          "q10_universe": .01 if (research and index < tail) or (not research and index - 4 < report) else -.01})
    top_rows = [{"period": period, "top_n": 20, "csi300_excess": .1 if index < top else -.1}
                for index, period in enumerate(PERIODS)]
    breadth = pd.DataFrame([{"q10_q1": -1, "top20_csi300_excess": -1}])
    result, decision = classify(pd.DataFrame(tail_rows), pd.DataFrame(top_rows), breadth)
    assert result["primary_classification"] == expected
    assert not decision["execute_decision"] and not decision["candidate_lock_created"]


def test_report_periods_are_retrospective_only():
    assert tuple(PERIODS)[-2:] == ("2025", "2026H1")


def test_report_artifact_is_retrospective_only():
    tail = pd.DataFrame([
        {"period": "2025", "horizon": horizon, "formal_label_rankic": .01,
         "forward_close_rankic": .02, "q10_q1": .03, "q10_universe": .04}
        for horizon in (1, 10)
    ])
    topn = pd.DataFrame([{"period": "2025", "top_n": 20, "gross_return": .1}])
    result = _period_summary(tail, topn, "2025")
    assert result["retrospective_report_only"] and result["not_used_for_selection"]
    assert result["not_fresh_validation"] and result["rankic"] == .01


def test_breadth_can_drive_only_regime_specific_classification():
    tail_rows = [{"period": period, "horizon": 1, "formal_label_rankic": -.01,
                  "q10_universe": -.01} for period in PERIODS]
    top_rows = [{"period": period, "top_n": 20, "csi300_excess": -.1} for period in PERIODS]
    breadth = pd.DataFrame([{"q10_q1": .01, "top20_csi300_excess": .1}])
    result, decision = classify(pd.DataFrame(tail_rows), pd.DataFrame(top_rows), breadth)
    assert result["primary_classification"] == "regime_specific_factor"
    assert decision["decision"] == "retain_for_regime_specific_research"


def test_artifacts_validate_and_reject_governance_crossing(tmp_path: Path):
    classification = {"schema_version": "v1", "provider_id": "tushare-pro-v1",
        "source_signal_artifact_id": "signal", "primary_classification": "tail_selection_overlay",
        "secondary_labels": [], "research_decision": "build_momentum_selection_overlay"}
    artifact = publish_artifact(tmp_path, "momentum_tail_signal_classification", classification,
                                {"classification.json": classification, "decision.json": {}})
    assert validate_artifact(Path(artifact["path"]), artifact["classification_id"])["status"] == "valid"
    bad = classification | {"primary_classification": "production_alpha"}
    with pytest.raises(ValueError, match="classification boundary"):
        publish_artifact(tmp_path / "bad", "momentum_tail_signal_classification", bad, {})


def test_final_artifact_rejects_nonzero_execution_or_registry(tmp_path: Path):
    counts = {name: 0 for name in ("agent_calls", "factor_optimization_calls", "strategy_optimization_calls",
        "combined_optimization_calls", "qlib_strategy_calls", "network_calls", "registry_writes", "promotion_writes")}
    identity = {"schema_version": "v1", "provider_id": "tushare-pro-v1", "task_id": "QM2-R1-009",
        "source_study_id": "study", "source_signal_artifact_id": "signal", "artifact_ids": [],
        "classification_id": "classification", "execution_counts": counts}
    artifact = publish_artifact(tmp_path, "momentum_tail_alpha_diagnostic", identity, {"spec.json": {}})
    assert validate_artifact(Path(artifact["path"]), artifact["diagnostic_id"])["status"] == "valid"
    with pytest.raises(ValueError, match="governance boundary"):
        publish_artifact(tmp_path / "bad", "momentum_tail_alpha_diagnostic",
                         identity | {"execution_counts": counts | {"registry_writes": 1}}, {})
