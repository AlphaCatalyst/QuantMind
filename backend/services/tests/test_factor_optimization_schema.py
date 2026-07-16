import copy

import pytest
from jsonschema import Draft202012Validator

from backend.services.engine.factor_optimization.examples import rolling_rank_study_spec, weighted_delta_study_spec
from backend.services.engine.factor_optimization.parser import parse_optimization_spec
from backend.services.engine.factor_optimization.schema import factor_optimization_spec_schema


def test_valid_specs_and_json_schema():
    payload = rolling_rank_study_spec(); Draft202012Validator(factor_optimization_spec_schema()).validate(payload)
    spec = parse_optimization_spec(payload)
    assert spec.search_spaces["window"].values == (2, 3, 5, 10, 20)


@pytest.mark.parametrize("mutation", [
    lambda x: x.update({"unknown": True}),
    lambda x: x["search_space"].update({"missing": {"kind": "explicit_values", "values": [1]}}),
    lambda x: x["parameter_roles"].update({"window": "factor_internal_weight"}),
    lambda x: x["parameter_roles"].update({"window": "signal_threshold"}),
    lambda x: x["budget"].update({"max_trials": 257}),
])
def test_strict_spec_unknown_parameter_role_mismatch_threshold_and_budget(mutation):
    payload = rolling_rank_study_spec(); mutation(payload)
    with pytest.raises(ValueError): parse_optimization_spec(payload)


def test_integer_range_and_explicit_types_and_duplicates():
    payload = rolling_rank_study_spec(); payload["search_space"]["window"] = {"kind": "integer_range", "minimum": 2, "maximum": 6, "step": 2}
    assert parse_optimization_spec(payload).search_spaces["window"].values == (2, 4, 6)
    payload["search_space"]["window"] = {"kind": "integer_range", "minimum": 1, "maximum": 22, "step": 1}
    assert parse_optimization_spec(payload).search_spaces["window"].values == tuple(range(2, 21))
    payload = weighted_delta_study_spec()
    assert parse_optimization_spec(payload).search_spaces["weight"].values == (0.2, 0.5, 0.8)
    payload["search_space"]["weight"]["values"] = [0.2, 0.2]
    with pytest.raises(ValueError): parse_optimization_spec(payload)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, 1.1])
def test_invalid_nonfinite_bool_or_template_step_value(value):
    payload = weighted_delta_study_spec(); payload["search_space"]["weight"]["values"] = [value]
    with pytest.raises(ValueError): parse_optimization_spec(payload)


def test_out_of_range_and_parameter_name_does_not_infer_role():
    payload = rolling_rank_study_spec(); payload["search_space"]["window"]["values"] = [21]
    with pytest.raises(ValueError): parse_optimization_spec(payload)
    payload = weighted_delta_study_spec(); payload["parameter_roles"] = {"periods": "factor_internal_weight", "weight": "lookback_window"}
    with pytest.raises(ValueError): parse_optimization_spec(payload)
