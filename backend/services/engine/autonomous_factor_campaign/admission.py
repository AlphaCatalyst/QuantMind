from __future__ import annotations

from typing import Any

from backend.services.engine.expanded_factor_iteration.audit import _dsl
from backend.services.engine.factor_dsl import factor_template_id, parse_template
from backend.services.engine.research_campaign.novelty import structural_fingerprint


CORE_MARKERS = ("momentum", "mom_ret", "return_", "trend", "price", "distance_to_high", "breakout", "drawdown", "residual")
FORBIDDEN_ONLY_MARKERS = ("beta", "volatility", "vol_", "liquidity", "liq_", "volume", "amount", "regime")


def _walk(node: Any, depth: int = 1):
    if not isinstance(node, dict):
        return depth, [], []
    features = [node["name"]] if node.get("type") == "feature" else []
    operators = [] if node.get("type") in {"feature", "parameter", "constant"} else [node.get("type")]
    child_stats = [_walk(value, depth + 1) for value in node.values() if isinstance(value, dict)]
    return (
        max([depth, *[item[0] for item in child_stats]]),
        features + [value for item in child_stats for value in item[1]],
        operators + [value for item in child_stats for value in item[2]],
    )


def normalize_proposal(proposal: dict, *, round_number: int, family: str) -> dict:
    template = proposal["template"]
    parsed = parse_template(template)
    depth, features, operators = _walk(template["expression"])
    defaults = {parameter.name: parameter.default for parameter in parsed.parameters}
    return {
        "proposal_id": proposal["proposal_id"], "round_number": round_number,
        "template_name": template["name"], "factor_family": family,
        "economic_hypothesis": proposal["rationale"],
        "canonical_dsl": _dsl(template["expression"]), "canonical_ast": template["expression"],
        "template": template, "factor_template_id": factor_template_id(parsed),
        "default_parameters": defaults, "parameter_schema": template["parameters"],
        "parameter_search": proposal["parameter_search"], "input_features": sorted(set(features)),
        "expected_market_mechanism": proposal["expected_behavior"],
        "expected_holding_horizon": "medium_horizon_10_session_rebalance",
        "expected_failure_modes": list(proposal["risks"]) + list(proposal["invalidation_conditions"]),
        "why_default_parameters_are_reasonable": proposal["expected_behavior"],
        "difference_from_existing_factors": proposal["novelty_claim"],
        "complexity_statement": {"terminal_features": len(set(features)), "parameters": len(parsed.parameters), "ast_depth": depth},
        "operators": sorted(set(operators)), "structural_fingerprint": structural_fingerprint(parsed),
    }


def admit_proposal(proposal: dict, *, allowed_features: set[str], allowed_operators: set[str],
                   known_fingerprints: set[str]) -> dict:
    try:
        item = normalize_proposal(
            proposal, round_number=int(proposal["_round_number"]), family=str(proposal["_factor_family"])
        )
    except Exception as exc:
        return {"admitted": False, "failure_code": "invalid_dsl", "safe_summary": str(exc)[:180]}
    complexity = item["complexity_statement"]
    if complexity["terminal_features"] > 3 or complexity["parameters"] > 2 or complexity["ast_depth"] > 6:
        return {"admitted": False, "failure_code": "semantic_mismatch", "safe_summary": "complexity limit exceeded", "proposal": item}
    if set(item["input_features"]) - allowed_features:
        return {"admitted": False, "failure_code": "missing_feature", "safe_summary": "feature outside round allowlist", "proposal": item}
    if set(item["operators"]) - allowed_operators:
        return {"admitted": False, "failure_code": "invalid_dsl", "safe_summary": "operator outside whitelist", "proposal": item}
    if not item["default_parameters"] and item["parameter_schema"]:
        return {"admitted": False, "failure_code": "AGENT_DEFAULT_PARAMETERS_MISSING", "safe_summary": "default parameters missing", "proposal": item}
    if not any(any(marker in name for marker in CORE_MARKERS) for name in item["input_features"]):
        return {"admitted": False, "failure_code": "semantic_mismatch", "safe_summary": "no core price/momentum/trend feature", "proposal": item}
    if all(any(marker in name for marker in FORBIDDEN_ONLY_MARKERS) for name in item["input_features"]):
        return {"admitted": False, "failure_code": "semantic_mismatch", "safe_summary": "pure conditioning factor forbidden", "proposal": item}
    if item["structural_fingerprint"] in known_fingerprints:
        return {"admitted": False, "failure_code": "duplicate_structure", "safe_summary": "structure fingerprint already seen", "proposal": item}
    return {"admitted": True, "failure_code": None, "safe_summary": "admitted", "proposal": item}
