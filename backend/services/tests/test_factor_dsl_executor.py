import numpy as np
import pandas as pd

from backend.services.engine.factor_dsl.executor import _evaluate
from backend.services.engine.factor_dsl.parser import parse_template


def expression(payload):
    base = {"schema_version": "1.0.0", "name": "test", "description": "Test expression semantics.",
            "dataset_kinds": ["legacy_feature_matrix_v1"], "parameters": [], "expression": payload, "output": {"name": "test"}}
    return parse_template(base).expression


def frame():
    return pd.DataFrame({"symbol": ["A", "B", "A", "B", "A", "B"],
                         "trade_date": pd.to_datetime(["2024-01-01"] * 2 + ["2024-01-02"] * 2 + ["2024-01-03"] * 2),
                         "x": [1.0, 10.0, 3.0, 20.0, 5.0, 30.0], "zero": [0.0] * 6})


def test_time_series_semantics_are_symbol_local_trailing_and_ddof_zero():
    data = frame()
    lag = _evaluate(expression({"type": "lag", "operand": {"type": "feature", "name": "x"}, "periods": {"type": "constant", "value": 1}}), data, {})
    delta = _evaluate(expression({"type": "delta", "operand": {"type": "feature", "name": "x"}, "periods": {"type": "constant", "value": 1}}), data, {})
    mean = _evaluate(expression({"type": "rolling_mean", "operand": {"type": "feature", "name": "x"}, "window": {"type": "constant", "value": 2}}), data, {})
    std = _evaluate(expression({"type": "rolling_std", "operand": {"type": "feature", "name": "x"}, "window": {"type": "constant", "value": 2}}), data, {})
    assert lag.tolist()[2:] == [1.0, 10.0, 3.0, 20.0]
    assert delta.tolist()[2:] == [2.0, 10.0, 2.0, 10.0]
    assert mean.tolist()[2:] == [2.0, 15.0, 4.0, 25.0]
    assert std.tolist()[2:] == [1.0, 5.0, 1.0, 5.0]


def test_safe_divide_rank_and_zscore_semantics():
    data = frame()
    divide = _evaluate(expression({"type": "divide", "left": {"type": "feature", "name": "x"}, "right": {"type": "feature", "name": "zero"}}), data, {})
    rank = _evaluate(expression({"type": "cs_rank", "operand": {"type": "feature", "name": "x"}}), data, {})
    zscore = _evaluate(expression({"type": "cs_zscore", "operand": {"type": "feature", "name": "x"}}), data, {})
    assert divide.isna().all() and not np.isinf(divide).any()
    assert rank.tolist() == [0.5, 1.0] * 3
    assert zscore.tolist() == [-1.0, 1.0] * 3


def test_cross_section_is_order_independent():
    data = frame(); node = expression({"type": "cs_rank", "operand": {"type": "feature", "name": "x"}})
    first = _evaluate(node, data, {}).set_axis(data.index)
    shuffled = data.sample(frac=1, random_state=7)
    second = _evaluate(node, shuffled, {}).reindex(data.index)
    assert first.equals(second)


def test_pointwise_arithmetic_unary_clip_and_nan_propagation():
    data = frame(); data.loc[2, "x"] = np.nan
    payload = {"type": "clip", "operand": {"type": "absolute", "operand": {"type": "negate", "operand": {"type": "subtract", "left": {"type": "multiply", "left": {"type": "feature", "name": "x"}, "right": {"type": "constant", "value": 2}}, "right": {"type": "constant", "value": 1}}}}, "lower": {"type": "constant", "value": 0}, "upper": {"type": "constant", "value": 10}}
    result = _evaluate(expression(payload), data, {})
    assert result.iloc[0] == 1.0 and result.iloc[1] == 10.0 and np.isnan(result.iloc[2])


def test_rolling_min_max_and_small_cross_section_rules():
    data = frame()
    min_values = _evaluate(expression({"type": "rolling_min", "operand": {"type": "feature", "name": "x"}, "window": {"type": "constant", "value": 2}}), data, {})
    max_values = _evaluate(expression({"type": "rolling_max", "operand": {"type": "feature", "name": "x"}, "window": {"type": "constant", "value": 2}}), data, {})
    assert min_values.tolist()[2:] == [1.0, 10.0, 3.0, 20.0]
    assert max_values.tolist()[2:] == [3.0, 20.0, 5.0, 30.0]
    single = data[data.symbol == "A"].copy()
    rank = _evaluate(expression({"type": "cs_rank", "operand": {"type": "feature", "name": "x"}}), single, {})
    zscore = _evaluate(expression({"type": "cs_zscore", "operand": {"type": "feature", "name": "zero"}}), data, {})
    assert rank.isna().all() and zscore.isna().all()
