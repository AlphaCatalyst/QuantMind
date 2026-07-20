from __future__ import annotations

import copy
import json

import numpy as np
import pandas as pd
import pytest

from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore
from backend.services.engine.expanded_factor_iteration.artifact import publish_artifact, validate_artifact
from backend.services.engine.expanded_factor_iteration.engine import _candidate_summary, _memory, _rank_key
from backend.services.engine.expanded_factor_iteration.features import (
    DEFINITIONS,
    LEGACY_REQUIRED,
    compute_feature_candidates,
    feature_contract,
    quality_and_selection,
)
from backend.services.engine.expanded_factor_iteration.protocol import BUDGET, FOLDS, fixed_protocol
from backend.services.engine.expanded_factor_iteration.redundancy import assess_template, equivalence_fingerprint


def _authority() -> dict:
    return {
        "authority_record_id": "tda_x",
        "normalized_bars_id": "tnb_x",
        "label_dataset_id": "tld_x",
        "qlib_view_id": "tqv_x",
        "universe_500": {"universe_lock_id": "tu500_x"},
        "universe_100": {"universe_lock_id": "tu100_x"},
    }


def _template(expression: dict, name: str = "novel") -> dict:
    return {
        "schema_version": "1.0.0",
        "name": name,
        "description": "bounded research Template",
        "dataset_kinds": ["tushare_feature_matrix_v2"],
        "expression": expression,
        "parameters": [],
        "output": {"name": name},
    }


def _candidate(rank_ic, excess, *, factor_id="fi_a", turnover=1.0, correlation=0.1):
    folds = []
    for number, (rank_value, excess_value) in enumerate(zip(rank_ic, excess), 1):
        folds.append({
            "fold_number": number,
            "metrics": {"mean_rank_ic": rank_value},
            "qlib": {
                "net_excess_csi300": excess_value,
                "turnover": turnover,
                "transaction_cost": 100.0,
                "return_without_best_10_days": 0.01,
                "max_drawdown": -0.10,
            },
        })
    value = {
        "factor_instance_id": factor_id,
        "folds": folds,
        "finite_coverage": 0.95,
        "infinity_count": 0,
        "maximum_old_factor_correlation": correlation,
        "redundancy_risk": "normal",
    }
    value["summary"] = _candidate_summary(value, weak_turnover=2.0)
    return value


def test_feature_catalog_contract_is_bounded_and_complete():
    assert len(DEFINITIONS) == 26
    catalog = feature_contract(tuple(item.name for item in DEFINITIONS[:24]))
    assert catalog["feature_count"] == 24
    assert catalog["universe_scope"] == "fixed_100_only"
    assert catalog["network_calls"] == 0
    required = {
        "feature_name", "source_columns", "canonical_formula", "lookback", "min_periods",
        "ddof", "grouping", "sort_order", "adjustment_semantics", "missing_policy",
        "warmup_requirement", "PIT_statement", "dtype",
    }
    assert all(set(row) == required for row in catalog["features"])
    assert all(row["missing_policy"] == "propagate_no_fill" for row in catalog["features"])


def test_feature_compute_is_cross_year_continuous_pit_safe_and_does_not_fill():
    dates = pd.bdate_range("2020-10-01", "2021-02-15")
    normalized = pd.DataFrame({
        "symbol": "000001.SZ", "trade_date": dates,
        "adjusted_open": np.arange(len(dates), dtype=float) + 99.0,
        "adjusted_high": np.arange(len(dates), dtype=float) + 101.0,
        "adjusted_low": np.arange(len(dates), dtype=float) + 98.0,
        "adjusted_close": np.arange(len(dates), dtype=float) + 100.0,
        "vol": 1000.0, "amount": 10000.0, "turnover_rate": 1.0, "circ_mv": 100000.0,
    })
    benchmark = pd.DataFrame({"trade_date": dates, "close": np.arange(len(dates), dtype=float) + 3000.0})
    base = compute_feature_candidates(normalized, benchmark)
    jan = base.loc[base["trade_date"] == pd.Timestamp("2021-01-04")].iloc[0]
    assert np.isfinite(jan["mom_ret_60d"])
    changed = normalized.copy()
    changed.loc[changed["trade_date"] > "2021-01-04", "adjusted_close"] *= 100
    altered = compute_feature_candidates(changed, benchmark)
    pd.testing.assert_series_equal(
        base.loc[base["trade_date"] <= "2021-01-04", "mom_ret_20d"].reset_index(drop=True),
        altered.loc[altered["trade_date"] <= "2021-01-04", "mom_ret_20d"].reset_index(drop=True),
    )
    missing = normalized.copy()
    missing.loc[20, "adjusted_close"] = np.nan
    missing_values = compute_feature_candidates(missing, benchmark)
    assert pd.isna(missing_values.loc[20, "mom_ret_1d"])
    assert pd.isna(missing_values.loc[21, "mom_ret_1d"])


def test_quality_gate_and_selection_are_bounded_without_duplicate_keys():
    dates = pd.bdate_range("2018-09-03", "2026-06-23")
    rows = []
    for symbol, offset in (("A", 0.0), ("B", 0.2)):
        x = np.arange(len(dates), dtype=float)
        rows.append(pd.DataFrame({
            "symbol": symbol, "trade_date": dates,
            "adjusted_open": 100 + offset + x * .01,
            "adjusted_high": 101 + offset + x * .01,
            "adjusted_low": 99 + offset + x * .01,
            "adjusted_close": 100.5 + offset + x * .01,
            "vol": 1000 + x, "amount": 10000 + x * 10,
            "turnover_rate": 1 + (x % 10) * .01, "circ_mv": 100000 + x * 100,
        }))
    normalized = pd.concat(rows, ignore_index=True)
    benchmark = pd.DataFrame({"trade_date": dates, "close": 3000 + np.arange(len(dates)) * .1})
    quality, selected = quality_and_selection(compute_feature_candidates(normalized, benchmark))
    assert len(selected) <= 24 and set(LEGACY_REQUIRED).issubset(selected)
    assert quality["duplicate_key_count"] == 0 and quality["infinity_count"] == 0
    assert all(quality["features"][name]["quality_passed"] for name in selected if name not in LEGACY_REQUIRED)


def test_redundancy_normalizes_commutative_order_and_orientation_flip():
    left = {"type": "feature", "name": "mom_ret_20d"}
    right = {"type": "feature", "name": "style_idio_vol_20"}
    first = _template({"type": "add", "left": left, "right": right}, "a")
    swapped = _template({"type": "add", "left": right, "right": left}, "b")
    fingerprint, _ = equivalence_fingerprint(first)
    assert equivalence_fingerprint(swapped)[0] == fingerprint
    rejected = assess_template(swapped, known_structural=set(), known_equivalent={fingerprint})
    assert rejected["admitted"] is False
    negated = _template({"type": "negate", "operand": first["expression"]}, "c")
    assert equivalence_fingerprint(negated) == (fingerprint, True)


def test_memory_excludes_later_period_and_daily_evidence():
    audit = {"factors": [{
        "factor_instance_id": "fi_old", "template_name": "old", "canonical_dsl": "cs_rank(x)",
        "structural_fingerprint": "nfp_old",
    }]}
    memory = _memory(2, ("mom_ret_20d",), audit, [], {"nfp_old"})
    assert memory["visibility_cutoff"] == "2024-12-31"
    assert memory["daily_series_included"] is False
    assert memory["daily_labels_included"] is False
    assert memory["daily_ic_included"] is False
    assert memory["later_period_feedback_included"] is False
    assert memory["fixed_100_relative_metrics_included"] is False


def test_four_walk_forward_folds_and_fixed_strategy_are_frozen():
    assert [(item.research_end, item.evaluation_year) for item in FOLDS] == [
        ("2020-12-31", "2021"), ("2021-12-31", "2022"),
        ("2022-12-30", "2023"), ("2023-12-29", "2024"),
    ]
    protocol = fixed_protocol(_authority(), "tfd2_x", LEGACY_REQUIRED)
    assert protocol["strategy"] == {
        "engine": "QlibBacktestService",
        "chain": ["QlibBacktestService", "RedisRecordingStrategy", "SimulatorExecutor", "CnExchange"],
        "universe": "tushare_fixed_100", "topk": 20, "n_drop": 5,
        "rebalance_trade_dates": 5, "weighting": "equal_weight",
        "signal_lag_trade_dates": 1, "execution_price": "open", "benchmark": "CSI300",
    }
    assert protocol["fixed_100_benchmark"]["usable_for_selection"] is False
    assert BUDGET["max_agent_calls"] == 12 and BUDGET["max_trials"] == 96


def test_candidate_eligibility_and_stable_ordering_enforce_all_gates():
    eligible = _candidate([.01, .02, -.005, .03], [.02, -.01, .03, .01], factor_id="fi_b")
    assert eligible["summary"]["eligible"] is True
    high_turnover = _candidate([.01, .02, -.005, .03], [.02, -.01, .03, .01], turnover=3.0)
    assert high_turnover["summary"]["eligible"] is False
    weak = _candidate([.01, -.02, -.03, .03], [.02, -.01, .03, .01], factor_id="fi_a")
    assert sorted([weak, eligible], key=_rank_key)[0]["factor_instance_id"] == "fi_b"


def test_candidate_selection_cannot_be_changed_by_later_report_fields():
    first = _candidate([.01, .02, -.005, .03], [.02, -.01, .03, .01], factor_id="fi_a")
    second = copy.deepcopy(first)
    second["factor_instance_id"] = "fi_b"
    second["retrospective_reports"] = {"2025": {"net_excess_csi300": 999.0}, "2026H1": {"net_excess_csi300": 999.0}}
    assert _rank_key(first) < _rank_key(second)


def test_candidate_lock_artifact_is_research_only_and_cold_recoverable(tmp_path):
    identity = {
        "schema_version": "agent-factor-candidate-lock-v2", "provider_id": "tushare-pro-v1",
        "status": "research_registered", "predictive_claim": False,
        "usable_for_promotion": False, "eligible_for_production": False, "promotion_writes": 0,
    }
    local = publish_artifact(tmp_path / "local", "agent_factor_candidate_lock", identity, {"candidate.json": identity})
    store = FileSystemResearchArtifactStore(resolve_config(tmp_path / "store"))
    store.initialize()
    receipt = store.import_artifact(
        "agent_factor_candidate_lock", local["path"], local["candidate_lock_id"], lineage=("tfd2_x",)
    )
    cold = tmp_path / "cold"
    store.materialize_artifact(receipt.descriptor_id, cold)
    assert validate_artifact(cold, local["candidate_lock_id"], "agent_factor_candidate_lock")["status"] == "valid"
    assert store.import_artifact(
        "agent_factor_candidate_lock", local["path"], local["candidate_lock_id"], lineage=("tfd2_x",)
    ).exact_existing is True


def test_candidate_lock_rejects_promotion_status(tmp_path):
    identity = {"provider_id": "tushare-pro-v1", "status": "active", "promotion_writes": 0}
    with pytest.raises(ValueError, match="forbidden Registry status"):
        publish_artifact(tmp_path, "agent_factor_candidate_lock", identity)
