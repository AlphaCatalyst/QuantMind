from __future__ import annotations

import copy

import pytest

from backend.services.engine.strategy_optimization.errors import StrategyOptimizationError
from backend.services.engine.strategy_optimization.engine import _candidate_lock, _run_trial
from backend.services.engine.strategy_optimization.ordering import parameter_sensitivity, rank_trials
from backend.services.engine.strategy_optimization.parser import parse_optimization_spec
from backend.services.engine.strategy_optimization.planner import plan_trials, study_id


SIGNALS = [f"usa_{index}" for index in range(4)]


def payload():
    return {
        "schema_version": "1.0.0", "name": "fixed100-strategy-grid-v1", "description": "research diagnostic",
        "unified_signal_ids": SIGNALS, "universe_id": "tu100_x", "qlib_view_id": "tqv_x",
        "research_period": {"start": "2019-01-02", "end": "2024-12-31"},
        "retrospective_holdout_periods": {"2025": {"start": "2025-01-02", "end": "2025-12-30"}, "2026H1": {"start": "2026-01-05", "end": "2026-06-23"}},
        "search_space": {"topk": [10, 20, 30], "n_drop": [0, 5, 10], "rebalance_interval": [1, 5, 10]},
        "budget": {"max_trials_per_signal": 24, "max_total_trials": 96},
        "execution_contract": {"weighting": "equal_weight", "signal_transform": "existing_unified_signal", "signal_lag_trade_dates": 1, "execution_price": "open", "cost_contract": "existing_formal_cn_exchange", "chain": ["QlibBacktestService", "RedisRecordingStrategy", "SimulatorExecutor", "CnExchange"], "calendar": "qlib_trade_calendar"},
        "benchmark_policy": {"selection_benchmark": "SH000300", "canonicality": "canonical", "fixed_100_usable_for_selection": False},
        "eligibility": {"minimum_valid_years": 6, "minimum_average_holdings_ratio": 0.8, "require_finite_metrics": True, "allow_nav_fill": False},
        "ordering": [{"field": "positive_excess_year_count", "direction": "desc"}, {"field": "median_annual_net_excess", "direction": "desc"}, {"field": "worst_annual_net_excess", "direction": "desc"}, {"field": "sharpe_ratio", "direction": "desc"}, {"field": "maximum_drawdown_abs", "direction": "asc"}, {"field": "turnover", "direction": "asc"}, {"field": "transaction_cost", "direction": "asc"}, {"field": "trial_id", "direction": "asc"}],
        "evidence_policy": {"evidence_class": "retrospective_contaminated_strategy_parameter_diagnostic", "predictive_claim": False, "usable_for_research": True, "usable_for_parameter_selection": "research_only", "usable_for_promotion": False, "eligible_for_production": False},
        "data_authority": "tushare-pro-v1",
    }


def test_strict_spec_and_deterministic_96_trial_plan():
    spec = parse_optimization_spec(payload())
    assert study_id(spec) == study_id(spec)
    trials = plan_trials(spec)
    assert len(trials) == 96
    assert all(item.n_drop < item.topk for item in trials)
    assert len({item.trial_id for item in trials}) == 96
    assert {sum(item.unified_signal_id == signal for item in trials) for signal in SIGNALS} == {24}


@pytest.mark.parametrize("mutation", [
    lambda x: x["search_space"].update({"threshold": [0]}),
    lambda x: x["search_space"].update({"topk": [10, 20]}),
    lambda x: x.update({"data_authority": "quantmind-production-feature-snapshots-v1"}),
    lambda x: x.update({"benchmark_policy": {"selection_benchmark": "FIXED100", "canonicality": "noncanonical", "fixed_100_usable_for_selection": True}}),
    lambda x: x["execution_contract"].update({"execution_price": "close"}),
])
def test_rejects_search_authority_benchmark_and_execution_drift(mutation):
    value = copy.deepcopy(payload()); mutation(value)
    with pytest.raises(StrategyOptimizationError):
        parse_optimization_spec(value)


def _trial(trial_id, positive, median, worst, sharpe, dd, turnover, cost, **params):
    return {"trial_id": trial_id, "topk": params.get("topk", 20), "n_drop": params.get("n_drop", 5), "rebalance_interval": params.get("rebalance_interval", 5), "metrics": {"eligible": True, "positive_excess_year_count": positive, "median_annual_net_excess": median, "worst_annual_net_excess": worst, "full_period": {"sharpe_ratio": sharpe, "maximum_drawdown": dd, "turnover": turnover, "transaction_cost": cost}}}


def test_stable_lexicographic_order_and_parameter_sensitivity():
    best = _trial("sot_a", 5, .03, -.02, .7, -.2, 10, 1)
    peer = _trial("sot_b", 5, .02, -.01, .8, -.1, 5, .5, topk=10)
    assert rank_trials([peer, best])[0] is best
    sensitivity = parameter_sensitivity([best, peer], best)
    assert sensitivity["stability_label"] == "parameter_robust"


def test_holdout_fields_cannot_enter_ordering():
    spec = payload(); spec["ordering"][0] = {"field": "2025_net_excess", "direction": "desc"}
    with pytest.raises(StrategyOptimizationError):
        parse_optimization_spec(spec)


def test_trial_executes_formal_full_and_six_year_segments_with_fixed_parameters(tmp_path):
    class Runner:
        def __init__(self): self.calls = []
        def run(self, path, start, end, **kwargs):
            self.calls.append((start, end, kwargs))
            return {
                "status": "completed", "formal_chain": ["QlibBacktestService", "RedisRecordingStrategy", "SimulatorExecutor", "CnExchange"],
                "gross_return": .1, "net_return": .08, "benchmark_return": .05,
                "net_excess_csi300": .03, "sharpe_ratio": .5, "max_drawdown": -.1,
                "annual_return": .08, "turnover": 2.0, "transaction_cost": 100.0,
                "monthly_win_rate": .5, "equity_curve": [{"date": "2020-01-01", "value": 1.0}],
                "positions": [{"date": "2020-01-01", "symbol": f"S{i}"} for i in range(20)],
            }
    runner = Runner()
    raw, metrics = _run_trial(runner, tmp_path / "signal.parquet", {"topk": 20, "n_drop": 5, "rebalance_interval": 10})
    assert len(runner.calls) == 7
    assert all(call[2] == {"topk": 20, "n_drop": 5, "rebalance_days": 10} for call in runner.calls)
    assert metrics["eligible"] and len(metrics["annual"]) == 6
    assert raw["formal_chain"][-1] == "CnExchange"


def test_failed_formal_trial_is_retained_and_ineligible(tmp_path):
    class Runner:
        def run(self, *args, **kwargs):
            return {"status": "rejected", "error_code": "FORMAL_QLIB_SIGNAL_QUALITY_REJECTED", "error_message": "quality gate"}
    _, metrics = _run_trial(Runner(), tmp_path / "signal.parquet", {"topk": 10, "n_drop": 0, "rebalance_interval": 1})
    assert metrics["eligible"] is False
    assert metrics["full_period"]["error_code"] == "FORMAL_QLIB_SIGNAL_QUALITY_REJECTED"


def test_candidate_lock_is_research_only_and_binds_selected_trial():
    spec = parse_optimization_spec(payload())
    selected = {"study_id": study_id(spec), "unified_signal_id": SIGNALS[0], "trial_id": "sot_selected", "topk": 20, "n_drop": 5, "rebalance_interval": 5}
    first_id, first = _candidate_lock(spec, selected)
    second_id, second = _candidate_lock(spec, selected)
    assert first_id == second_id and first == second
    assert first["selected_trial_id"] == "sot_selected"
    assert first["usable_for_promotion"] is False and first["eligible_for_production"] is False
