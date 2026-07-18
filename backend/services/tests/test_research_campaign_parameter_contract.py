import copy

import pytest

from backend.services.engine.research_campaign.errors import ProposalParameterContractError
from backend.services.engine.research_campaign.parameter_contract import (
    proposal_parameter_contract_summary,
    validate_proposal_parameter_contract,
    valid_minimal_examples,
)


def proposal(example=0):
    sample = copy.deepcopy(valid_minimal_examples()[example])
    sample["proposal_id"] = "contract_test"
    return sample


def violation(value, maximum_trials=8):
    with pytest.raises(ProposalParameterContractError) as caught:
        validate_proposal_parameter_contract(value, 0, maximum_trials=maximum_trials)
    return caught.value.detail


def test_summary_is_derived_from_formal_parameter_and_search_contracts():
    summary = proposal_parameter_contract_summary()
    assert summary["supported_parameter_types"] == ["integer", "number"]
    assert set(summary["supported_parameter_roles"]) == {
        "lookback_window", "factor_internal_weight", "signal_threshold",
    }
    assert summary["role_to_allowed_ast_locations"]["lookback_window"] == "lookback_window"
    assert summary["ast_field_to_context"] == {
        "window": "lookback_window", "periods": "lookback_window",
    }
    assert summary["integer_search_space_schema"]["integer_range"]["properties"]["step"]["minimum"] == 1
    assert summary["number_search_space_schema"]["integer_range_allowed"] is False


def test_all_minimal_examples_pass_the_real_validator():
    examples = valid_minimal_examples()
    assert [item["example"] for item in examples] == [
        "lookback_window", "factor_internal_weight",
    ]
    for index, item in enumerate(examples):
        result = validate_proposal_parameter_contract(
            {"proposal_id": f"example_{index}", **item}, index, maximum_trials=8
        )
        assert result["parameter_search"]["search_space"]


def test_unknown_search_parameter_has_structured_safe_diagnostic():
    value = proposal()
    value["parameter_search"][0]["name"] = "unknown"
    detail = violation(value)
    assert detail["error_code"] == "search_space_parameter_unknown"
    assert detail["proposal_index"] == 0
    assert detail["field_path"] == "proposals[0].parameter_search"
    assert detail["declared_parameters"] == ["window"]
    assert detail["used_parameters"] == ["window"]
    assert detail["search_space_parameters"] == ["unknown"]


def test_undeclared_ast_parameter_and_missing_search_are_distinct():
    undeclared = proposal()
    undeclared["template"]["parameters"] = []
    detail = violation(undeclared)
    assert detail["error_code"] == "parameter_not_declared"
    assert detail["field_path"] == "proposals[0].template.expression"

    missing = proposal()
    missing["parameter_search"] = []
    detail = violation(missing)
    assert detail["error_code"] == "parameter_role_missing"
    assert detail["declared_parameters"] == ["window"]
    assert detail["search_space_parameters"] == []


def test_unused_parameter_is_not_repaired_by_weakening_binding():
    value = proposal()
    value["template"]["expression"] = {
        "type": "cs_rank", "operand": {"type": "feature", "name": "mom_ret_1d"}
    }
    detail = violation(value)
    assert detail["error_code"] == "parameter_declared_but_unused"
    assert detail["unused_parameters"] == ["window"]
    assert "remove unused parameter" in detail["allowed_fix_actions"]


def test_role_mismatch_and_mixed_role_use_are_distinct():
    value = proposal()
    value["parameter_search"][0]["role"] = "factor_internal_weight"
    assert violation(value)["error_code"] == "parameter_role_ast_mismatch"

    mixed = proposal()
    mixed["template"]["expression"] = {
        "type": "add",
        "left": mixed["template"]["expression"],
        "right": {"type": "parameter", "name": "window"},
    }
    assert violation(mixed)["error_code"] == "parameter_used_in_multiple_incompatible_roles"


def test_search_type_bounds_step_and_budget_fail_closed():
    number = proposal(1)
    number["parameter_search"][0]["search_space"] = {
        "kind": "integer_range", "minimum": 0, "maximum": 1, "step": 1,
    }
    assert violation(number)["error_code"] == "search_space_type_mismatch"

    bounds = proposal()
    bounds["parameter_search"][0]["search_space"]["values"] = [3, 21]
    assert violation(bounds)["error_code"] == "search_space_out_of_template_bounds"

    stepped = proposal()
    stepped["template"]["parameters"][0]["step"] = 2
    stepped["parameter_search"][0]["search_space"]["values"] = [3, 4]
    assert violation(stepped)["error_code"] == "step_mismatch"

    budget = proposal()
    budget["parameter_search"][0]["search_space"]["values"] = [2, 3, 4, 5, 6, 7, 8]
    assert violation(budget, maximum_trials=6)["error_code"] == "budget_overflow"


def test_invalid_template_default_and_duplicate_values_fail_closed():
    default = proposal()
    default["template"]["parameters"][0]["default"] = 21
    assert violation(default)["error_code"] == "default_out_of_range"

    duplicate = proposal()
    duplicate["parameter_search"][0]["search_space"]["values"] = [3, 3]
    assert violation(duplicate)["error_code"] == "explicit_values_invalid"


def test_signal_threshold_remains_unavailable():
    value = proposal(1)
    value["parameter_search"][0]["role"] = "signal_threshold"
    assert violation(value)["error_code"] == "unsupported_signal_threshold"
