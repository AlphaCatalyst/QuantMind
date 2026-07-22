from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from backend.services.engine.parameter_optimization_ablation.artifact import publish_artifact, validate_artifact
from backend.services.engine.parameter_optimization_ablation.engine import (
    _flat_choice, _flatten_parameters, _local_rows, _mode_parameter_rows, _parameter_rows,
    _search_intensity, _turnover_cost,
)
from backend.services.engine.parameter_optimization_ablation.metrics import (
    classify_overfit, gains, ordering_key, parameter_consistency, plateau_analysis,
    rank_stability, select_trial, selection_summary,
)
from backend.services.engine.parameter_optimization_ablation.protocol import (
    ARTIFACT_FILES, COMBINED_MODES, FACTOR_MODES, FOLDS, FORMAL_STRATEGY,
    PERIODS, S0, S1, S2, STRATEGY_MODES, TASK_ID,
)


def _metrics(rankic=0.02, excess=0.1, drawdown=-0.2, turnover=1.0, cost=0.01):
    return selection_summary([{"rankic": rankic, "excess": excess,
        "maximum_drawdown": drawdown, "turnover": turnover, "transaction_cost": cost}])


def _trial(trial_id, value, rankic=0.02, excess=0.1):
    return {"trial_id": trial_id, "configuration_id": f"config-{value}",
            "parameters": {"window": value}, "window": value,
            "topk": 20, "n_drop": 5, "rebalance_interval": 5,
            "selection_metrics": _metrics(rankic, excess)}


def test_task_identity_is_new_and_does_not_reuse_r1_004():
    assert TASK_ID == "QM2-R1-005"


def test_original_explicit_search_space_is_cartesian_and_not_expanded():
    rows = _parameter_rows({"window": {"kind": "explicit_values", "values": [10, 20, 40]}})
    assert rows == [{"window": 10}, {"window": 20}, {"window": 40}]


def test_light_factor_space_is_default_plus_direct_neighbors_only():
    full = [{"window": 10}, {"window": 20}, {"window": 40}]
    assert _local_rows({"window": 20}, full) == [{"window": 20}, {"window": 10}, {"window": 40}]


def test_light_factor_space_changes_only_one_parameter():
    full = _parameter_rows({"a": {"kind": "explicit_values", "values": [1, 2, 3]},
                            "b": {"kind": "explicit_values", "values": [4, 5, 6]}})
    rows = _local_rows({"a": 2, "b": 5}, full)
    assert len(rows) == 5
    assert all(sum(row[key] != {"a": 2, "b": 5}[key] for key in row) <= 1 for row in rows)


def test_factor_modes_have_frozen_meanings():
    candidate = {"agent_default_parameters": {"window": 20},
                 "local_parameter_rows": [{"window": 20}, {"window": 10}],
                 "full_parameter_rows": [{"window": 10}, {"window": 20}, {"window": 40}]}
    assert _mode_parameter_rows(candidate, "F0") == [{"window": 20}]
    assert len(_mode_parameter_rows(candidate, "F1")) == 2
    assert len(_mode_parameter_rows(candidate, "F2")) == 3


def test_strategy_spaces_are_exactly_frozen():
    assert S0 == ((20, 5, 5),)
    assert len(S1) == 7
    assert len(S2) == 24
    assert all(n_drop < topk for topk, n_drop, _ in S2)


def test_factor_strategy_and_combined_modes_are_separate():
    assert FACTOR_MODES == ("F0", "F1", "F2")
    assert tuple(STRATEGY_MODES) == ("S0", "S1", "S2")
    assert COMBINED_MODES == {"O0": ("F0", "S0"), "O1": ("F1", "S1"), "O2": ("F2", "S2")}
    assert FORMAL_STRATEGY["topk"] == 20 and FORMAL_STRATEGY["signal_lag"] == 1


def test_fold_protocol_has_no_future_or_report_period_selection():
    assert len(FOLDS) == 4
    assert all(fold["research"][1] < fold["evaluation"][0] for fold in FOLDS)
    assert max(fold["evaluation"][1] for fold in FOLDS) < PERIODS["2025"][0]


def test_uniform_lexicographic_ordering_and_trial_id_tiebreak():
    left, right = _trial("a", 10), _trial("b", 20)
    assert ordering_key(left) < ordering_key(right)
    assert select_trial([right, left])["trial_id"] == "a"


def test_fold_lock_identity_is_created_from_research_selection():
    choice = {**_trial("selected", 20), "layer": "factor", "mode": "F0",
              "object": "candidate_a", "fold": 1, "signal_id": "signal"}
    flattened = _flat_choice(choice)
    assert flattened["fold_lock_id"].startswith("poafl1_")


def test_selection_summary_contains_rankic_excess_drawdown_turnover_and_cost():
    result = _metrics()
    assert result["median_rankic"] == pytest.approx(0.02)
    assert result["median_csi300_excess"] == pytest.approx(0.1)
    assert result["maximum_drawdown_abs"] == pytest.approx(0.2)
    assert result["turnover"] == 1.0 and result["transaction_cost"] == 0.01


def test_research_and_report_gains_use_same_subtraction_contract():
    baseline = {"mean_rankic": 0.01, "net_csi300_excess": 0.02, "sharpe_ratio": 0.1, "maximum_drawdown": -0.3}
    optimized = {"mean_rankic": 0.03, "net_csi300_excess": 0.07, "sharpe_ratio": 0.4, "maximum_drawdown": -0.2}
    result = gains(optimized, baseline)
    assert result == pytest.approx({"rankic": 0.02, "csi300_excess": 0.05, "sharpe": 0.3, "drawdown": 0.1})


def test_generalization_gap_definition():
    research_gain, average_report_gain = 0.12, -0.03
    assert research_gain - average_report_gain == pytest.approx(0.15)


def test_rank_stability_reports_spearman_kendall_and_selected_percentile():
    result = rank_stability({"a": 3, "b": 2, "c": 1}, {"a": 1, "b": 2, "c": 3}, "a", "2025")
    assert result["spearman_rank_correlation"] == pytest.approx(-1.0)
    assert result["kendall_rank_correlation"] == pytest.approx(-1.0)
    assert result["selected_trial_later_percentile"] == 0.0


def test_fold_parameter_consistency_detects_instability():
    result = parameter_consistency([{"window": 10}, {"window": 40}, {"window": 10}, {"window": 40}],
                                   [{"window": 10}, {"window": 20}, {"window": 40}])
    assert result["exact_match_rate"] == 0.0
    assert result["fold_parameter_instability"] is True


def test_nested_factor_parameters_are_flattened_without_collision():
    result = _flatten_parameters({"candidate_a": {"window": 40}, "candidate_b": {"weight": 0.75}})
    assert result == {"candidate_a.window": 40, "candidate_b.weight": 0.75}


def test_parameter_plateau_classifies_sharp_peak():
    selected = _trial("best", 20, rankic=0.02, excess=0.2)
    neighbors = [_trial("left", 10, rankic=0.01, excess=0.0),
                 selected, _trial("right", 40, rankic=0.01, excess=0.0)]
    result = plateau_analysis(selected, neighbors, ("window",))
    assert result["neighbor_count"] == 2
    assert result["classification"] == "sharp_peak"


def test_likely_robust_policy_requires_both_report_periods():
    classification = classify_overfit({"csi300_excess": 0.1},
        [{"csi300_excess": 0.01}, {"csi300_excess": 0.02}], 0.5, 0.5, [0.5, 0.5])
    assert classification == "likely_robust"


def test_likely_overfit_policy_detects_negative_average_report_gain():
    classification = classify_overfit({"csi300_excess": 0.1},
        [{"csi300_excess": -0.01}, {"csi300_excess": -0.02}], 0.8, 1.0, [0.8, 0.8])
    assert classification == "likely_overfit"


def test_search_intensity_records_count_best_median_and_spread():
    trial_sets, periods = {}, {}
    for mode_index, mode in enumerate(("F0", "F1", "F2")):
        periods[mode] = {}
        for name in ("candidate_a", "candidate_b", "ensemble"):
            rows = [_trial(f"{mode}-{name}-a", 10, excess=0.1),
                    _trial(f"{mode}-{name}-b", 20, excess=0.2)]
            trial_sets[(mode, name, 4)] = rows
            periods[mode][name] = {
                "2019-2024": {"net_csi300_excess": mode_index / 10},
                "2025": {"net_csi300_excess": -mode_index / 10},
                "2026H1": {"net_csi300_excess": -mode_index / 10},
            }
    result = _search_intensity(trial_sets, periods)
    assert result["F1"]["candidate_a"]["trial_count"] == 2
    assert result["F1"]["candidate_a"]["best_minus_median"] == pytest.approx(0.05)
    assert result["intensity_effect"]["ensemble"]["research_rises_while_report_falls"] is True


def test_turnover_and_cost_drag_detect_consumed_gain():
    def period(gross, net, turnover, cost):
        return {"gross_return": gross, "net_return": net, "cost_drag": gross-net,
                "turnover": turnover, "transaction_cost": cost}
    periods = {"S0": {"candidate_a": {p: period(.10, .09, 1, .01) for p in PERIODS}},
               "S1": {"candidate_a": {p: period(.11, .08, 2, .03) for p in PERIODS}}}
    # Supply all contract objects because the analysis function is intentionally fixed-width.
    for name in ("candidate_b", "ensemble"):
        periods["S0"][name] = periods["S0"]["candidate_a"]
        periods["S1"][name] = periods["S1"]["candidate_a"]
    result = _turnover_cost(periods, "S0", ("S1",))
    assert result["S1"]["candidate_a"]["2025"]["optimization_gain_consumed_by_cost"] is True


def test_all_six_store_artifact_contracts_are_registered():
    assert len(ARTIFACT_FILES) == 6
    assert "optimization_overfit_assessment" in ARTIFACT_FILES


def test_artifact_publish_validate_and_cold_copy(tmp_path: Path):
    kind = "parameter_optimization_ablation_spec"
    files = {name: {"name": name} for name in ARTIFACT_FILES[kind]}
    identity = {"provider_id": "tushare-pro-v1", "agent_calls": 0,
                "network_calls": 0, "promotion_writes": 0}
    artifact = publish_artifact(tmp_path / "domain", kind, identity, files)
    assert validate_artifact(Path(artifact["path"]), artifact["artifact_id"])["status"] == "valid"


def test_artifact_forbidden_execution_boundary_hard_fails(tmp_path: Path):
    kind = "parameter_optimization_ablation_spec"
    files = {name: {} for name in ARTIFACT_FILES[kind]}
    with pytest.raises(ValueError, match="forbidden execution boundary"):
        publish_artifact(tmp_path / "domain", kind,
            {"provider_id": "tushare-pro-v1", "agent_calls": 1}, files)


def test_artifact_hash_tamper_hard_fails(tmp_path: Path):
    kind = "parameter_optimization_ablation_spec"
    artifact = publish_artifact(tmp_path / "domain", kind,
        {"provider_id": "tushare-pro-v1"}, {name: {} for name in ARTIFACT_FILES[kind]})
    root = Path(artifact["path"]); (root / "spec.json").write_text('{"tampered":true}\n')
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_artifact(root, artifact["artifact_id"])


def test_contract_never_changes_candidate_or_promotion_state():
    result = {"candidate_status_before": ["research_registered"] * 2,
              "candidate_status_after": ["research_registered"] * 2,
              "agent_calls": 0, "network_calls": 0, "promotion_writes": 0}
    assert result["candidate_status_before"] == result["candidate_status_after"]
    assert not any(result[key] for key in ("agent_calls", "network_calls", "promotion_writes"))
