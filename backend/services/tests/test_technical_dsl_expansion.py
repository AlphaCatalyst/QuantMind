from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from jsonschema import Draft202012Validator

from backend.services.engine.autonomous_research_supervisor.control import (
    global_stop_decision,
)
from backend.services.engine.autonomous_technical_feature_factory.grammar import (
    FeatureGrammarError,
    audit_ast_v2,
    evaluate_ast_v2,
)
from backend.services.engine.autonomous_technical_feature_factory.models import (
    V2_PRIMITIVES,
    AutonomousTechnicalFeatureFactorySpecV2,
    TechnicalFeatureFactoryBudgetV2,
)
from backend.services.engine.autonomous_technical_feature_factory.operators import (
    AUTHORIZED_EXTENSION_OPERATORS,
    REJECTED_EXTENSION_OPERATORS,
    build_operator_extension,
)
from backend.services.engine.autonomous_technical_feature_factory.primitives import (
    primitive_values,
)
from backend.services.engine.autonomous_technical_feature_factory.schemas import (
    feature_agent_schema_v2,
)
from backend.services.engine.factor_dsl.canonical import node_payload
from backend.services.engine.factor_dsl.executor import _evaluate
from backend.services.engine.factor_dsl.parser import parse_template


def feature(name: str) -> dict:
    return {"type": "feature", "name": name}


def factory_frame() -> pd.DataFrame:
    rows = []
    dates = pd.bdate_range("2020-01-02", periods=12).strftime("%Y-%m-%d")
    for symbol_index, symbol in enumerate(("A", "B")):
        for day, date in enumerate(dates):
            close = 10 + symbol_index * 3 + day
            rows.append({
                "symbol": symbol,
                "trade_date": date,
                "adjusted_open": close - 0.2,
                "adjusted_high": close + (2 if day % 3 else 0),
                "adjusted_low": close - 1,
                "adjusted_close": close,
                "volume": 100 + day * (symbol_index + 1),
                "amount": 1000 + day * 10,
                "vwap": close / 2,
                "adj_factor": 2.0,
                "daily_return": (day - 5) ** 2 / 100,
                "csi300_return": day / 1000,
                "turnover_rate": 1 + day / 10,
            })
    return pd.DataFrame(rows).sort_values(
        ["symbol", "trade_date"]
    ).reset_index(drop=True)


def dsl_expression(ast: dict):
    def convert(node):
        value = dict(node)
        if value["type"] in {
            "rolling_sum", "rolling_median", "rolling_skew",
            "rolling_argmax_age",
        }:
            value["operand"] = convert(value["operand"])
            value["window"] = {"type": "constant", "value": value["window"]}
        elif value["type"] == "rolling_quantile":
            value["operand"] = convert(value["operand"])
            value["window"] = {"type": "constant", "value": value["window"]}
            value["quantile"] = {"type": "constant", "value": value["quantile"]}
        elif value["type"] == "rolling_corr":
            value["left"] = convert(value["left"])
            value["right"] = convert(value["right"])
            value["window"] = {"type": "constant", "value": value["window"]}
        return value
    payload = {
        "schema_version": "1.0.0",
        "name": "extension_test",
        "description": "Technical operator extension consistency test.",
        "dataset_kinds": ["momentum_feature_matrix_v1"],
        "parameters": [],
        "expression": convert(ast),
        "output": {"name": "value"},
    }
    parsed = parse_template(payload)
    assert node_payload(parsed.expression) == payload["expression"]
    return parsed.expression


def test_operator_contract_schema_and_authorization_inventory():
    value = build_operator_extension()
    assert [row["operator_name"] for row in value["operators"]] == list(
        AUTHORIZED_EXTENSION_OPERATORS
    )
    assert {row["operator_name"] for row in value["rejected_operators"]} == set(
        REJECTED_EXTENSION_OPERATORS
    )
    schema_path = (
        Path(__file__).resolve().parents[3]
        / "docs/quantmind2/implementation/schemas/technical_dsl_operator_extension_v1.schema.json"
    )
    Draft202012Validator(json.loads(schema_path.read_text())).validate(value)


@pytest.mark.parametrize("operator", REJECTED_EXTENSION_OPERATORS)
def test_unbounded_operators_remain_rejected(operator):
    ast = {"type": operator, "operand": feature("daily_return"), "window": 5}
    with pytest.raises(FeatureGrammarError, match="FEATURE_OPERATOR_NOT_AUTHORIZED"):
        audit_ast_v2(ast, V2_PRIMITIVES)


@pytest.mark.parametrize("operator", [
    "rolling_sum", "rolling_median", "rolling_skew", "rolling_argmax_age",
])
def test_unary_extension_is_pit_trailing_and_dsl_local_consistent(operator):
    source = factory_frame()
    ast = {"type": operator, "operand": feature("daily_return"), "window": 5}
    local = evaluate_ast_v2(ast, source, V2_PRIMITIVES)
    dsl = _evaluate(dsl_expression(ast), source, {})
    pd.testing.assert_series_equal(local, dsl, check_names=False)
    changed = source.copy()
    changed.loc[changed.groupby("symbol").tail(1).index, "daily_return"] = 999
    replay = evaluate_ast_v2(ast, changed, V2_PRIMITIVES)
    stable_rows = ~source.index.isin(source.groupby("symbol").tail(1).index)
    pd.testing.assert_series_equal(
        local[stable_rows], replay[stable_rows], check_names=False
    )


def test_rolling_corr_pairwise_full_window_and_zero_variance():
    source = factory_frame()
    ast = {
        "type": "rolling_corr",
        "left": feature("daily_return"),
        "right": feature("volume"),
        "window": 5,
    }
    local = evaluate_ast_v2(ast, source, V2_PRIMITIVES)
    dsl = _evaluate(dsl_expression(ast), source, {})
    pd.testing.assert_series_equal(local, dsl, check_names=False)
    source["volume"] = 1.0
    assert evaluate_ast_v2(ast, source, V2_PRIMITIVES).isna().all()


@pytest.mark.parametrize("quantile", [0.20, 0.50, 0.80])
def test_rolling_quantile_is_fixed_constant_and_round_trips(quantile):
    source = factory_frame()
    ast = {
        "type": "rolling_quantile",
        "operand": feature("daily_return"),
        "window": 5,
        "quantile": quantile,
    }
    local = evaluate_ast_v2(ast, source, V2_PRIMITIVES)
    dsl = _evaluate(dsl_expression(ast), source, {})
    pd.testing.assert_series_equal(local, dsl, check_names=False)
    assert np.isfinite(local.dropna()).all()
    invalid = dict(ast, quantile=0.75)
    with pytest.raises(FeatureGrammarError, match="FEATURE_QUANTILE_NOT_AUTHORIZED"):
        audit_ast_v2(invalid, V2_PRIMITIVES)


def test_rolling_skew_minimum_sample_and_constant_behavior():
    source = factory_frame()
    ast = {
        "type": "rolling_skew", "operand": feature("daily_return"), "window": 5
    }
    values = evaluate_ast_v2(ast, source, V2_PRIMITIVES)
    assert values.groupby(source["symbol"]).head(4).isna().all()
    source["daily_return"] = 1.0
    assert evaluate_ast_v2(ast, source, V2_PRIMITIVES).isna().all()


def test_rolling_argmax_age_uses_most_recent_tied_maximum():
    source = factory_frame().iloc[:12].copy()
    source["daily_return"] = [1, 3, 3, 2, 1, 1, 2, 2, 2, 1, 0, -1]
    ast = {
        "type": "rolling_argmax_age",
        "operand": feature("daily_return"),
        "window": 5,
    }
    values = evaluate_ast_v2(ast, source, V2_PRIMITIVES)
    assert values.iloc[4] == 2
    assert values.iloc[8] == 0


def test_primitive_formulas_are_pit_safe_and_zero_division_is_nan():
    source = factory_frame()
    source.loc[0, "adjusted_open"] = 0
    source.loc[1, "adjusted_high"] = source.loc[1, "adjusted_low"]
    values = primitive_values(source)
    assert set(values) == {
        "overnight_gap", "intraday_return", "high_low_range",
        "close_location_value", "close_vs_vwap", "turnover_pressure",
    }
    assert np.isnan(values["intraday_return"].iloc[0])
    assert np.isnan(values["close_location_value"].iloc[1])
    assert values["overnight_gap"].groupby(source["symbol"]).head(1).isna().all()


def test_factory_v2_spec_is_frozen_unlabeled_and_bounded():
    payload = AutonomousTechnicalFeatureFactorySpecV2().payload(
        operator_extension_id="tdoe1_test",
        primitive_catalog_id="tpc2_test",
        existing_feature_catalog_v2_id="tfc2_test",
    )
    assert payload["factory_name"] == "technical_feature_factory_002"
    assert payload["budgets"]["maximum_agent_calls"] == 10
    assert payload["label_access"] is False
    assert payload["performance_access"] is False
    with pytest.raises(ValueError):
        AutonomousTechnicalFeatureFactorySpecV2(
            budgets=TechnicalFeatureFactoryBudgetV2(maximum_agent_calls=11)
        ).payload(
            operator_extension_id="x",
            primitive_catalog_id="y",
            existing_feature_catalog_v2_id="z",
        )


def test_feature_agent_v2_schema_exposes_no_predictive_fields():
    rendered = json.dumps(feature_agent_schema_v2(), sort_keys=True).lower()
    for forbidden in ("raw_label", "model_label", "rankic", "backtest"):
        assert forbidden not in rendered


def test_cycle_two_global_stop_requires_both_empty_dimensions():
    stopped = global_stop_decision(
        consecutive_cycles_without_new_feature=2,
        consecutive_cycles_without_candidate=2,
        novelty_exhausted=True,
        active_fresh_candidates=0,
    )
    feature_only = global_stop_decision(
        consecutive_cycles_without_new_feature=0,
        consecutive_cycles_without_candidate=2,
        novelty_exhausted=False,
        active_fresh_candidates=0,
    )
    assert stopped["stop"] is True
    assert feature_only["stop"] is False


def test_cli_has_no_token_argument_and_exposes_cycle_command():
    root = Path(__file__).resolve().parents[3]
    factory_cli = (
        root / "tools/quantmind2/run_autonomous_technical_feature_factory.py"
    ).read_text()
    supervisor_cli = (
        root / "tools/quantmind2/run_autonomous_research_supervisor.py"
    ).read_text()
    assert "--token" not in factory_cli + supervisor_cli
    assert "run-next-research-cycle" in supervisor_cli
