from __future__ import annotations

from functools import reduce
from operator import mul

from backend.services.engine.factor_dsl.enums import NodeKind, ParameterType
from backend.services.engine.factor_dsl.errors import TemplateValidationError
from backend.services.engine.factor_dsl.parser import (
    PARAMETER_OPTIONAL_FIELDS,
    PARAMETER_REQUIRED_FIELDS,
    parse_template,
)
from backend.services.engine.factor_optimization.enums import ParameterRole
from backend.services.engine.factor_optimization.errors import (
    OptimizationAdmissionError,
    OptimizationSpecError,
)
from backend.services.engine.factor_optimization.roles import (
    AST_FIELD_CONTEXTS,
    ROLE_AST_CONTEXTS,
    parameter_usage,
    validate_parameter_roles,
)
from backend.services.engine.factor_optimization.schema import (
    factor_optimization_spec_schema,
)
from backend.services.engine.factor_optimization.search_space import parse_search_space

from .errors import ProposalParameterContractError


ALLOWED_FIX_ACTIONS = (
    "remove unused parameter",
    "bind parameter into valid AST location",
    "correct parameter role",
    "correct search-space name",
    "correct search-space kind",
    "reduce search-space values",
    "replace unnecessary parameter with constant",
)


def _node(kind, **fields):
    return {"type": kind, **fields}


def _template(name, parameter, expression):
    return {
        "schema_version": "1.0.0",
        "name": name,
        "description": "Mechanical parameter-contract example; not a research candidate.",
        "dataset_kinds": ["legacy_feature_matrix_v1"],
        "parameters": [parameter],
        "expression": expression,
        "output": {"name": name},
    }


def valid_minimal_examples():
    window = {
        "name": "window", "type": "integer", "default": 5,
        "minimum": 2, "maximum": 20, "step": 1,
    }
    weight = {
        "name": "weight", "type": "number", "default": 0.5,
        "minimum": 0.0, "maximum": 1.0,
    }
    examples = (
        {
            "example": "lookback_window",
            "template": _template(
                "contract_window_example",
                window,
                _node(
                    "rolling_mean",
                    operand=_node("feature", name="mom_ret_1d"),
                    window=_node("parameter", name="window"),
                ),
            ),
            "parameter_search": [{
                "name": "window", "role": "lookback_window",
                "search_space": {"kind": "explicit_values", "values": [3, 5, 10]},
            }],
        },
        {
            "example": "factor_internal_weight",
            "template": _template(
                "contract_weight_example",
                weight,
                _node(
                    "multiply",
                    left=_node("parameter", name="weight"),
                    right=_node("feature", name="style_beta_20"),
                ),
            ),
            "parameter_search": [{
                "name": "weight", "role": "factor_internal_weight",
                "search_space": {"kind": "explicit_values", "values": [0.2, 0.5, 0.8]},
            }],
        },
    )
    for index, example in enumerate(examples):
        normalized = validate_proposal_parameter_contract(
            {"proposal_id": f"example_{index}", **example}, index, maximum_trials=8
        )
        if not normalized["parameter_search"]["search_space"]:
            raise RuntimeError("parameter-contract example did not validate")
    return list(examples)


def proposal_parameter_contract_summary():
    optimization_schema = factor_optimization_spec_schema()
    search_variants = optimization_schema["$defs"]["searchSpace"]["oneOf"]
    by_kind = {
        item["properties"]["kind"]["const"]: item
        for item in search_variants
    }
    examples = valid_minimal_examples()
    provider_examples = []
    for example in examples:
        item = {**example, "template": {
            **example["template"],
            "parameters": [
                {key: value for key, value in parameter.items() if key != "step"}
                for parameter in example["template"]["parameters"]
            ],
        }}
        item["parameter_search"] = [
            {"name": search["name"], "role": search["role"],
             **search["search_space"]}
            for search in example["parameter_search"]
        ]
        provider_examples.append(item)
    return {
        "schema_version": "proposal-parameter-contract-summary-v1",
        "supported_parameter_types": [item.value for item in ParameterType],
        "supported_parameter_roles": [item.value for item in ParameterRole],
        "campaign_allowed_parameter_roles": [
            ParameterRole.LOOKBACK_WINDOW.value,
            ParameterRole.FACTOR_INTERNAL_WEIGHT.value,
        ],
        "role_to_allowed_ast_locations": {
            role.value: context for role, context in ROLE_AST_CONTEXTS.items()
        } | {ParameterRole.SIGNAL_THRESHOLD.value: "unavailable_before_signal_stage"},
        "ast_field_to_context": dict(AST_FIELD_CONTEXTS),
        "template_parameter_required_fields": sorted(PARAMETER_REQUIRED_FIELDS),
        "template_parameter_optional_fields": sorted(PARAMETER_OPTIONAL_FIELDS),
        "integer_search_space_schema": {
            "integer_range": by_kind["integer_range"],
            "explicit_values": by_kind["explicit_values"],
        },
        "number_search_space_schema": {
            "explicit_values": by_kind["explicit_values"],
            "integer_range_allowed": False,
        },
        "binding_rules": [
            "declared_parameters == used_parameters == search_space_parameters == role_assignments",
            "each parameter has exactly one role",
            "lookback_window is used only in window or periods AST fields",
            "factor_internal_weight is used only as an arithmetic operand",
            "signal_threshold is unavailable before the Signal stage",
            "integer values obey Template bounds and optional step",
            "number parameters use explicit_values",
            "the Cartesian product must not exceed the remaining Trial budget",
        ],
        "invalid_examples_summary": {
            "parameter_not_declared": "AST parameter has no Template declaration",
            "parameter_declared_but_unused": "Template parameter has no AST use",
            "parameter_role_missing": "searched parameter has no role",
            "parameter_role_ast_mismatch": "role conflicts with every AST use",
            "search_space_parameter_missing": "declared/used parameter has no search space",
            "search_space_parameter_unknown": "search space names an undeclared parameter",
            "search_space_type_mismatch": "search kind conflicts with parameter type",
            "search_space_out_of_template_bounds": "search value is outside Template bounds",
            "integer_range_invalid": "integer range bounds or step are invalid",
            "explicit_values_invalid": "explicit values are empty, duplicate, or non-finite",
            "default_out_of_range": "Template default is outside its bounds",
            "step_mismatch": "search value does not align with Template step",
            "parameter_used_in_multiple_incompatible_roles": "one parameter has lookback and arithmetic uses",
            "unsupported_signal_threshold": "signal_threshold is unavailable in this Campaign",
            "budget_overflow": "Cartesian search product exceeds remaining Trial budget",
        },
        "valid_minimal_examples": examples,
        "provider_transport_valid_minimal_examples": provider_examples,
    }


def _parameter_names(node):
    if isinstance(node, dict):
        if node.get("type") == NodeKind.PARAMETER.value and isinstance(node.get("name"), str):
            yield node["name"]
        for value in node.values():
            yield from _parameter_names(value)
    elif isinstance(node, list):
        for value in node:
            yield from _parameter_names(value)


def _diagnostic(proposal, index, *, code, path, declared=(), used=(), search=(), roles=None):
    detail = {
        "proposal_index": index,
        "proposal_id": proposal.get("proposal_id") if isinstance(proposal, dict) else None,
        "error_code": code,
        "field_path": path,
        "declared_parameters": sorted(declared),
        "used_parameters": sorted(used),
        "unused_parameters": sorted(set(declared) - set(used)),
        "search_space_parameters": sorted(search),
        "role_assignments": dict(sorted((roles or {}).items())),
        "allowed_fix_actions": list(ALLOWED_FIX_ACTIONS),
    }
    raise ProposalParameterContractError(detail)


def _template_error_code(message):
    if "range/default/step" in message:
        return "default_out_of_range"
    if "parameter.default" in message:
        return "default_out_of_range"
    if "parameter.step" in message:
        return "integer_range_invalid"
    return "other"


def _search_error_code(message):
    if "only valid for integer" in message:
        return "search_space_type_mismatch"
    if "outside Template bounds" in message:
        return "search_space_out_of_template_bounds"
    if "violates Template step" in message:
        return "step_mismatch"
    if "integer_range" in message:
        return "integer_range_invalid"
    if "explicit" in message or "finite numeric" in message or "must be integer" in message:
        return "explicit_values_invalid"
    return "other"


def _normalize_search(raw, proposal, index):
    if isinstance(raw, list):
        roles, spaces = {}, {}
        for item_index, item in enumerate(raw):
            if not isinstance(item, dict):
                _diagnostic(proposal, index, code="other", path=f"proposals[{index}].parameter_search[{item_index}]")
            if set(item) == {"name", "role", "values"}:
                name, role = item["name"], item["role"]
                space = {"kind": "explicit_values", "values": item["values"]}
            elif set(item) == {"name", "role", "kind", "values"}:
                name, role = item["name"], item["role"]
                space = {"kind": item["kind"], "values": item["values"]}
            elif set(item) == {"name", "role", "search_space"}:
                name, role, space = item["name"], item["role"], item["search_space"]
            else:
                _diagnostic(proposal, index, code="other", path=f"proposals[{index}].parameter_search[{item_index}]")
            if name in roles:
                _diagnostic(proposal, index, code="explicit_values_invalid",
                            path=f"proposals[{index}].parameter_search[{item_index}].name")
            roles[name], spaces[name] = role, space
        return roles, spaces
    if isinstance(raw, dict) and set(raw) == {"parameter_roles", "search_space"}:
        return raw["parameter_roles"], raw["search_space"]
    _diagnostic(proposal, index, code="other", path=f"proposals[{index}].parameter_search")


def validate_proposal_parameter_contract(proposal, index, *, maximum_trials):
    try:
        template = parse_template(proposal["template"])
    except (KeyError, TemplateValidationError) as exc:
        _diagnostic(
            proposal, index, code=_template_error_code(str(exc)),
            path=f"proposals[{index}].template.parameters",
        )
    declared = {parameter.name for parameter in template.parameters}
    used = set(_parameter_names(proposal["template"]["expression"]))
    roles, spaces = _normalize_search(proposal.get("parameter_search"), proposal, index)
    if not isinstance(roles, dict):
        _diagnostic(proposal, index, code="parameter_role_missing",
                    path=f"proposals[{index}].parameter_search", declared=declared, used=used)
    if not isinstance(spaces, dict):
        _diagnostic(proposal, index, code="search_space_parameter_missing",
                    path=f"proposals[{index}].parameter_search", declared=declared, used=used, roles=roles)
    search_names = set(spaces)
    role_names = set(roles)
    undeclared_uses = used - declared
    if undeclared_uses:
        _diagnostic(proposal, index, code="parameter_not_declared",
                    path=f"proposals[{index}].template.expression", declared=declared,
                    used=used, search=search_names, roles=roles)
    unknown = (search_names | role_names) - declared
    if unknown:
        _diagnostic(proposal, index, code="search_space_parameter_unknown",
                    path=f"proposals[{index}].parameter_search", declared=declared,
                    used=used, search=search_names, roles=roles)
    unused = declared - used
    if unused:
        _diagnostic(proposal, index, code="parameter_declared_but_unused",
                    path=f"proposals[{index}].template.parameters", declared=declared,
                    used=used, search=search_names, roles=roles)
    if declared - role_names:
        _diagnostic(proposal, index, code="parameter_role_missing",
                    path=f"proposals[{index}].parameter_search", declared=declared,
                    used=used, search=search_names, roles=roles)
    if declared - search_names:
        _diagnostic(proposal, index, code="search_space_parameter_missing",
                    path=f"proposals[{index}].parameter_search", declared=declared,
                    used=used, search=search_names, roles=roles)
    if role_names != search_names:
        code = "parameter_role_missing" if search_names - role_names else "search_space_parameter_missing"
        _diagnostic(proposal, index, code=code,
                    path=f"proposals[{index}].parameter_search", declared=declared,
                    used=used, search=search_names, roles=roles)
    parsed_roles = {}
    for name, raw_role in roles.items():
        try:
            parsed_roles[name] = ParameterRole(raw_role)
        except ValueError:
            _diagnostic(proposal, index, code="parameter_role_missing",
                        path=f"proposals[{index}].parameter_search.{name}.role",
                        declared=declared, used=used, search=search_names, roles=roles)
        if parsed_roles[name] is ParameterRole.SIGNAL_THRESHOLD:
            _diagnostic(proposal, index, code="unsupported_signal_threshold",
                        path=f"proposals[{index}].parameter_search.{name}.role",
                        declared=declared, used=used, search=search_names, roles=roles)
    uses = parameter_usage(template.expression)
    for name, contexts in uses.items():
        if len(contexts) > 1:
            _diagnostic(proposal, index, code="parameter_used_in_multiple_incompatible_roles",
                        path=f"proposals[{index}].template.expression", declared=declared,
                        used=used, search=search_names, roles=roles)
    try:
        validate_parameter_roles(template, parsed_roles)
    except OptimizationAdmissionError:
        _diagnostic(proposal, index, code="parameter_role_ast_mismatch",
                    path=f"proposals[{index}].parameter_search", declared=declared,
                    used=used, search=search_names, roles=roles)
    definitions = {parameter.name: parameter for parameter in template.parameters}
    normalized_spaces = {}
    for name, space in spaces.items():
        try:
            normalized_spaces[name] = parse_search_space(space, definitions[name]).source
        except OptimizationSpecError as exc:
            _diagnostic(proposal, index, code=_search_error_code(str(exc)),
                        path=f"proposals[{index}].parameter_search.{name}.search_space",
                        declared=declared, used=used, search=search_names, roles=roles)
    counts = [
        len(parse_search_space(normalized_spaces[name], definitions[name]).values)
        for name in sorted(normalized_spaces)
    ]
    trial_count = reduce(mul, counts, 1)
    if trial_count > maximum_trials:
        _diagnostic(proposal, index, code="budget_overflow",
                    path=f"proposals[{index}].parameter_search", declared=declared,
                    used=used, search=search_names, roles=roles)
    return {
        **proposal,
        "parameter_search": {
            "parameter_roles": {name: parsed_roles[name].value for name in sorted(parsed_roles)},
            "search_space": {name: normalized_spaces[name] for name in sorted(normalized_spaces)},
        },
    }
