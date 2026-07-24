from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.services.engine.autonomous_technical_feature_factory.admission import (
    quality_evidence, signal_correlation,
)
from backend.services.engine.autonomous_technical_feature_factory.grammar import (
    FeatureGrammarError, audit_ast, evaluate_ast,
)
from backend.services.engine.autonomous_technical_feature_factory.models import (
    AutonomousTechnicalFeatureFactorySpecV1, TechnicalFeatureFactoryBudget,
)
from backend.services.engine.autonomous_technical_feature_factory.schemas import feature_agent_schema


def feature(name):
    return {"type": "feature", "name": name}


def frame(days=140, symbols=100):
    dates = pd.bdate_range("2019-01-02", periods=days).strftime("%Y-%m-%d")
    rows = []
    for symbol_index in range(symbols):
        for day_index, date in enumerate(dates):
            rows.append({
                "symbol": f"S{symbol_index:03d}", "trade_date": date,
                "adjusted_open": 10 + symbol_index / 10 + day_index / 100,
                "adjusted_high": 11 + symbol_index / 10 + day_index / 100,
                "adjusted_low": 9 + symbol_index / 10 + day_index / 100,
                "adjusted_close": 10 + symbol_index / 10 + day_index / 100,
                "volume": 1000 + symbol_index * 10 + day_index,
                "amount": 10000 + symbol_index * 100 + day_index,
                "vwap": 10 + symbol_index / 10,
                "daily_return": (symbol_index - 50) / 10000 + day_index / 100000,
                "csi300_return": day_index / 100000,
            })
    return pd.DataFrame(rows).sort_values(["symbol", "trade_date"]).reset_index(drop=True)


def test_factory_spec_is_frozen_and_unlabeled():
    payload = AutonomousTechnicalFeatureFactorySpecV1().payload()
    assert payload["factory_spec_id"].startswith("atffs1_")
    assert payload["label_access"] is False
    assert payload["backtest_access"] is False
    assert payload["budgets"]["maximum_agent_calls"] == 8


def test_factory_budget_cannot_expand():
    with pytest.raises(ValueError):
        AutonomousTechnicalFeatureFactorySpecV1(
            budgets=TechnicalFeatureFactoryBudget(maximum_agent_calls=9)
        ).payload()


@pytest.mark.parametrize("operator", ["rolling_sum", "rolling_corr", "log1p", "cs_rank", "cs_zscore"])
def test_unauthorized_feature_operator_is_rejected(operator):
    ast = {"type": operator, "operand": feature("daily_return"), "window": 20}
    with pytest.raises(FeatureGrammarError, match="FEATURE_OPERATOR_NOT_AUTHORIZED"):
        audit_ast(ast)


@pytest.mark.parametrize("primitive", ["raw_label", "model_label", "forward_return", "financial_roe"])
def test_forward_label_and_noncontract_input_are_rejected(primitive):
    with pytest.raises(FeatureGrammarError, match="FEATURE_PRIMITIVE_NOT_AUTHORIZED"):
        audit_ast(feature(primitive))


def test_feature_ast_limits_primitives_windows_depth_and_operators():
    valid = {
        "type": "safe_divide",
        "left": {"type": "delta", "operand": feature("adjusted_close"), "periods": 20},
        "right": {"type": "rolling_std", "operand": feature("daily_return"), "window": 20},
    }
    audit = audit_ast(valid)
    assert audit.primitives == ("adjusted_close", "daily_return")
    assert audit.windows == (20,)
    assert audit.depth <= 6
    assert audit.operator_count == 3


def test_window_outside_frozen_set_is_rejected():
    with pytest.raises(FeatureGrammarError, match="FEATURE_WINDOW_NOT_AUTHORIZED"):
        audit_ast({"type": "rolling_mean", "operand": feature("daily_return"), "window": 21})


def test_feature_evaluation_is_grouped_and_pit_lagged():
    source = frame(days=8, symbols=2)
    ast = {"type": "lag", "operand": feature("adjusted_close"), "periods": 5}
    values = evaluate_ast(ast, source)
    assert values.groupby(source["symbol"]).apply(lambda value: value.head(5).isna().all()).all()


def test_safe_divide_emits_no_infinity():
    source = frame(days=8, symbols=2)
    source["amount"] = 0
    ast = {"type": "safe_divide", "left": feature("volume"), "right": feature("amount")}
    values = evaluate_ast(ast, source)
    assert not np.isinf(values.to_numpy(dtype=float, na_value=np.nan)).any()


def test_quality_gate_accepts_stable_nondegenerate_feature():
    source = frame(days=520)
    values = source[["symbol", "trade_date"]].copy()
    symbol_level = np.repeat(np.arange(100), 520)
    day = np.tile(np.arange(520), 100)
    values["feature_value"] = symbol_level + 20 * np.sin(day / 7 + symbol_level / 13)
    evidence = quality_evidence(values, "2019-01-02", "2020-12-31")
    assert evidence["finite_coverage"] == 1
    assert evidence["minimum_daily_finite_members"] == 100
    assert evidence["duplicate_key_count"] == 0
    assert evidence["nonzero_cross_sectional_dispersion_days"] == 1
    assert evidence["passed"]


def test_quality_gate_rejects_degenerate_feature():
    source = frame(days=520)
    values = source[["symbol", "trade_date"]].copy()
    values["feature_value"] = 1.0
    evidence = quality_evidence(values, "2019-01-02", "2020-12-31")
    assert not evidence["passed"]
    assert "dispersion" in evidence["failed_gates"]


def test_signal_duplicate_threshold_inputs_are_exact():
    source = frame(days=20, symbols=10)
    left = source[["symbol", "trade_date"]].copy()
    left["feature_value"] = source["adjusted_close"]
    right = left.copy()
    assert signal_correlation(left, right) == pytest.approx(1)


def test_feature_agent_schema_has_no_label_or_performance_fields():
    rendered = str(feature_agent_schema()).lower()
    assert "raw_label" not in rendered
    assert "rankic" not in rendered
    assert "backtest" not in rendered


def test_research_feature_state_cannot_be_production_by_spec():
    payload = AutonomousTechnicalFeatureFactorySpecV1().payload()
    assert payload["usable_for_production"] is False
