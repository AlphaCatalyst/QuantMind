from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore
from backend.services.engine.momentum_factor_iteration.artifact import publish_artifact, validate_artifact
from backend.services.engine.momentum_factor_iteration.engine import _ast_stats, _nearest_neighbor, _rank_key, _summary
from backend.services.engine.momentum_factor_iteration.features import catalog_payload, compute_features, definitions, quality_report
from backend.services.engine.momentum_factor_iteration.protocol import BUDGET, DATASET_KIND, FOLDS, FORMAL_STRATEGY, ROUND_THEMES
from backend.services.engine.momentum_factor_iteration.regimes import build_regimes


def _data(periods=700):
    dates = pd.bdate_range("2018-01-01", periods=periods)
    rows = []
    for offset, symbol in enumerate(("SH600001", "SZ000001")):
        x = np.arange(len(dates), dtype=float)
        rows.append(pd.DataFrame({"symbol": symbol, "trade_date": dates,
                                  "adjusted_close": 100 + offset + x * .03 + np.sin(x / 8),
                                  "amount": 10000 + x * 10 + offset * 50}))
    market_returns = .0002 + .012 * np.sin(np.arange(len(dates)) / 11)
    benchmark = pd.DataFrame({"trade_date": dates, "close": 3000 * np.cumprod(1 + market_returns)})
    return pd.concat(rows, ignore_index=True), benchmark


def _candidate(factor_id="fi_a"):
    fold_values = [(.01, .02), (.02, .03), (.004, .01), (-.002, -.02)]
    candidate = {
        "factor_instance_id": factor_id, "folds": [{"metrics": {"mean_rank_ic": rank}, "qlib": {
            "net_excess_csi300": excess, "turnover": 10.0, "transaction_cost": 100.0,
            "best_10_days_contribution": .2, "return_without_best_10_days": .01, "max_drawdown": -.1,
        }} for rank, excess in fold_values],
        "finite_coverage": .99, "infinity_count": 0, "pit_violation_count": 0,
        "parameter_neighborhood": {"stability_rate": .75}, "maximum_existing_factor_correlation": .2,
        "ast_depth": 2,
    }
    candidate["summary"] = _summary(candidate)
    return candidate


def test_catalog_has_exactly_36_features_and_at_least_eight_families():
    catalog = catalog_payload()
    assert catalog["dataset_kind"] == DATASET_KIND
    assert catalog["feature_count"] == 36
    assert catalog["family_count"] >= 8
    assert len({item.name for item in definitions()}) == 36


def test_catalog_definitions_include_required_semantics():
    required = {"formula", "economic_meaning", "source_columns", "lookback", "min_periods", "lag_policy",
                "adjustment_policy", "missing_policy", "pit_rule", "expected_direction", "allowed_operators"}
    assert all(required.issubset(item) for item in catalog_payload()["features"])


def test_feature_compute_is_pit_and_cross_year_continuous():
    normalized, benchmark = _data()
    baseline = compute_features(normalized, benchmark)
    cutoff = normalized["trade_date"].sort_values().iloc[500]
    altered = normalized.copy()
    altered.loc[altered["trade_date"] > cutoff, "adjusted_close"] *= 10
    changed = compute_features(altered, benchmark)
    columns = [item.name for item in definitions()]
    pd.testing.assert_frame_equal(baseline.loc[baseline.trade_date <= cutoff, columns].reset_index(drop=True), changed.loc[changed.trade_date <= cutoff, columns].reset_index(drop=True))


def test_feature_compute_propagates_missing_and_has_no_inf():
    normalized, benchmark = _data()
    normalized.loc[100, "adjusted_close"] = np.nan
    output = compute_features(normalized, benchmark)
    assert pd.isna(output.loc[(output.symbol == "SH600001") & (output.trade_date == normalized.loc[100, "trade_date"]), "return_5d"]).all()
    assert not np.isinf(output[[item.name for item in definitions()]].to_numpy()).any()


def test_quality_gate_reports_correlation_and_passes_healthy_features():
    normalized, benchmark = _data(1800)
    report = quality_report(compute_features(normalized, benchmark))
    assert report["failed_features"] == []
    assert isinstance(report["high_correlation_pairs"], list)


def test_regime_contract_is_diagnostic_and_pit_safe():
    normalized, benchmark = _data(1200)
    baseline, contract = build_regimes(normalized, benchmark)
    cutoff = benchmark.trade_date.iloc[900]
    changed = benchmark.copy()
    changed.loc[changed.trade_date > cutoff, "close"] *= 4
    altered, _ = build_regimes(normalized, changed)
    pd.testing.assert_frame_equal(baseline[baseline.trade_date <= cutoff].reset_index(drop=True), altered[altered.trade_date <= cutoff].reset_index(drop=True))
    assert contract["usage"] == "diagnostic_only_not_agent_or_dsl_input"


def test_six_round_themes_cover_at_least_eight_families():
    assert len(ROUND_THEMES) == 6
    assert len(set().union(*map(set, ROUND_THEMES.values()))) >= 8
    assert len(ROUND_THEMES[6]) >= 2


def test_early_stop_requires_family_diversity_gate_in_source():
    import inspect
    from backend.services.engine.momentum_factor_iteration import engine
    source = inspect.getsource(engine.execute_experiment)
    assert "explored_family_count >= 6" in source


def test_campaign_and_strategy_budgets_are_frozen():
    assert BUDGET.max_total_agent_calls == 12
    assert BUDGET.max_total_admitted_templates == 18
    assert BUDGET.max_total_trials == 144
    assert FORMAL_STRATEGY["topk"] == 20 and FORMAL_STRATEGY["n_drop"] == 5
    assert FORMAL_STRATEGY["rebalance_frequency"] == 5 and FORMAL_STRATEGY["benchmark"] == "CSI300"
    assert len(FOLDS) == 4


def test_ast_stats_enforce_terminal_parameter_and_depth_evidence():
    ast = {"type": "add", "left": {"type": "feature", "name": "return_20d"},
           "right": {"type": "multiply", "left": {"type": "parameter", "name": "weight"},
                     "right": {"type": "feature", "name": "momentum_efficiency_20"}}}
    depth, features, parameters = _ast_stats(ast)
    assert depth == 3 and features == {"return_20d", "momentum_efficiency_20"} and parameters == {"weight"}


def test_neighbor_requires_one_adjacent_parameter_change():
    selected = {"trial_id": "a", "ordinal": 1, "parameters": {"w": 10, "x": .5}}
    trials = [selected, {"trial_id": "b", "ordinal": 2, "parameters": {"w": 20, "x": .5}}, {"trial_id": "c", "ordinal": 3, "parameters": {"w": 20, "x": 1.0}}]
    search = {"w": {"values": [10, 20]}, "x": {"values": [.5, 1.0]}}
    assert _nearest_neighbor(selected, trials, search)["trial_id"] == "b"


def test_candidate_eligibility_enforces_all_gates():
    candidate = _candidate()
    assert candidate["summary"]["eligible"] is True
    unstable = copy.deepcopy(candidate)
    unstable["parameter_neighborhood"]["stability_rate"] = .25
    unstable["summary"] = _summary(unstable)
    assert unstable["summary"]["eligible"] is False
    assert "parameter_stability" in unstable["summary"]["eligibility_failures"]


def test_stable_order_does_not_consume_later_report_fields():
    first, second = _candidate("fi_a"), _candidate("fi_b")
    second["retrospective_reports"] = {"2025": {"net_excess_csi300": 999}}
    assert _rank_key(first) < _rank_key(second)


def test_artifact_is_immutable_store_recoverable_and_research_only(tmp_path):
    identity = {"schema_version": "momentum-factor-candidate-lock-v1", "provider_id": "tushare-pro-v1",
                "status": "research_registered", "promotion_writes": 0}
    local = publish_artifact(tmp_path / "local", "momentum_factor_candidate_lock", identity, {"candidate.json": identity})
    store = FileSystemResearchArtifactStore(resolve_config(tmp_path / "store"))
    store.initialize()
    receipt = store.import_artifact("momentum_factor_candidate_lock", local["path"], local["candidate_lock_id"], lineage=("mfd1_x",))
    cold = tmp_path / "cold"
    store.materialize_artifact(receipt.descriptor_id, cold)
    assert validate_artifact(cold, local["candidate_lock_id"], "momentum_factor_candidate_lock")["status"] == "valid"
    assert store.import_artifact("momentum_factor_candidate_lock", local["path"], local["candidate_lock_id"], lineage=("mfd1_x",)).exact_existing


def test_artifact_rejects_production_status(tmp_path):
    identity = {"schema_version": "momentum-factor-candidate-lock-v1", "provider_id": "tushare-pro-v1", "status": "production", "promotion_writes": 0}
    with pytest.raises(ValueError, match="forbidden Registry status"):
        publish_artifact(tmp_path, "momentum_factor_candidate_lock", identity, {})


def test_round_artifact_rejects_later_period_leak(tmp_path):
    identity = {"schema_version": "momentum-factor-round-result-v1", "provider_id": "tushare-pro-v1", "promotion_writes": 0, "holdout_2025": {}}
    with pytest.raises(ValueError, match="leaks forbidden evidence"):
        publish_artifact(tmp_path, "momentum_factor_round_result", identity, {})
