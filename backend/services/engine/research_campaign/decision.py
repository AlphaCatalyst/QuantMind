import json
import math
import re

from backend.services.engine.factor_dsl import parse_template

from .canonical import hash_payload
from .errors import AgentContractError

_SAFE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
_FORBIDDEN = re.compile(r"(?i)(password\s*[:=]|api[_-]?key\s*[:=]|access[_-]?token\s*[:=]|private[_-]?key\s*[:=]|https?://|/Users/|/tmp/|/private/tmp|factor_impl|subprocess|import\s|curl\s|bash\s|rm\s+-)")
_ROLES = {"lookback_window", "factor_internal_weight", "signal_threshold"}


def decision_json_schema():
    node = {"anyOf": [
        {"type": "object", "additionalProperties": False, "required": ["type", "name"],
         "properties": {"type": {"enum": ["feature", "parameter"]}, "name": {"type": "string"}}},
        {"type": "object", "additionalProperties": False, "required": ["type", "value"],
         "properties": {"type": {"const": "constant"}, "value": {"type": "number"}}},
        {"type": "object", "additionalProperties": False, "required": ["type", "operand"],
         "properties": {"type": {"enum": ["negate", "absolute", "cs_rank", "cs_zscore"]}, "operand": {"$ref": "#/$defs/node"}}},
        {"type": "object", "additionalProperties": False, "required": ["type", "left", "right"],
         "properties": {"type": {"enum": ["add", "subtract", "multiply", "divide"]},
                        "left": {"$ref": "#/$defs/node"}, "right": {"$ref": "#/$defs/node"}}},
        {"type": "object", "additionalProperties": False, "required": ["type", "operand", "window"],
         "properties": {"type": {"enum": ["rolling_mean", "rolling_std", "rolling_min", "rolling_max"]},
                        "operand": {"$ref": "#/$defs/node"}, "window": {"$ref": "#/$defs/node"}}},
        {"type": "object", "additionalProperties": False, "required": ["type", "operand", "periods"],
         "properties": {"type": {"const": "delta"}, "operand": {"$ref": "#/$defs/node"},
                        "periods": {"$ref": "#/$defs/node"}}}]}
    template = {"type": "object", "additionalProperties": False,
        "required": ["schema_version", "name", "description", "dataset_kinds", "parameters", "expression", "output"],
        "properties": {"schema_version": {"const": "1.0.0"}, "name": {"type": "string"},
            "description": {"type": "string"}, "dataset_kinds": {"type": "array", "items": {"type": "string"}},
            "parameters": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                "required": ["name", "type", "default", "minimum", "maximum"],
                "properties": {"name": {"type": "string"}, "type": {"enum": ["integer", "number"]},
                    "default": {"type": "number"}, "minimum": {"type": "number"}, "maximum": {"type": "number"}}}},
            "expression": {"$ref": "#/$defs/node"}, "output": {"type": "object", "additionalProperties": False,
                "required": ["name"], "properties": {"name": {"type": "string"}}}}}
    parameter_search = {"type": "array", "items": {"type": "object", "additionalProperties": False,
        "required": ["name", "role", "values"], "properties": {"name": {"type": "string"},
            "role": {"enum": list(sorted(_ROLES))}, "values": {"type": "array", "items": {"type": "number"}}}}}
    return {"$defs": {"node": node, "template": template, "parameter_search": parameter_search},
            "type": "object", "additionalProperties": False,
            "required": ["schema_version", "decision_id", "goal_id", "iteration", "hypothesis_summary", "proposals", "stop_recommendation"],
            "properties": {
                "schema_version": {"const": "1.0.0"}, "decision_id": {"type": "string"},
                "goal_id": {"type": "string"}, "iteration": {"type": "integer"},
                "hypothesis_summary": {"type": "string"}, "stop_recommendation": {"type": "boolean"},
                "proposals": {"type": "array", "maxItems": 4, "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["proposal_id", "template", "parameter_search", "rationale", "expected_behavior", "novelty_claim", "risks", "invalidation_conditions"],
                    "properties": {"proposal_id": {"type": "string"}, "template": {"$ref": "#/$defs/template"},
                        "parameter_search": {"$ref": "#/$defs/parameter_search"}, "rationale": {"type": "string"},
                        "expected_behavior": {"type": "string"}, "novelty_claim": {"type": "string"},
                        "risks": {"type": "array", "items": {"type": "string"}},
                        "invalidation_conditions": {"type": "array", "items": {"type": "string"}}}}}}}


def _loads_closed(raw):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 65536 or "```" in raw:
        raise AgentContractError("Agent response is not bounded plain JSON")
    try:
        decoder = json.JSONDecoder(parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        payload, end = decoder.raw_decode(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        raise AgentContractError("Agent response is not strict JSON") from exc
    if raw[end:].strip():
        raise AgentContractError("Agent response contains text outside JSON")
    return payload


def _forbidden_control_key(value):
    if isinstance(value, dict):
        if any(re.search(r"(?i)(frozen|promotion|approve|activate|label|registry_status)", str(key)) for key in value):
            return True
        return any(_forbidden_control_key(item) for item in value.values())
    if isinstance(value, list): return any(_forbidden_control_key(item) for item in value)
    return False


def parse_decision(raw, *, iteration, goal, budget, provider_id, model_id):
    payload = _loads_closed(raw)
    required = {"schema_version", "decision_id", "goal_id", "iteration", "hypothesis_summary", "proposals", "stop_recommendation"}
    if (not isinstance(payload, dict) or set(payload) != required or payload["schema_version"] != "1.0.0" or
            payload["goal_id"] != goal.goal_id or payload["iteration"] != iteration):
        raise AgentContractError("ResearchDecision fields or iteration are invalid")
    if not isinstance(payload["hypothesis_summary"], str) or len(payload["hypothesis_summary"]) > 2000 or not isinstance(payload["stop_recommendation"], bool):
        raise AgentContractError("ResearchDecision summary/stop is invalid")
    proposals = payload["proposals"]
    if not isinstance(proposals, list) or len(proposals) > budget.max_proposals_per_iteration:
        raise AgentContractError("ResearchDecision proposal count exceeds budget")
    normalized = []
    for proposal in proposals:
        fields = {"proposal_id", "template", "parameter_search", "rationale", "expected_behavior", "novelty_claim", "risks", "invalidation_conditions"}
        if not isinstance(proposal, dict) or set(proposal) != fields or not _SAFE.fullmatch(str(proposal["proposal_id"])):
            raise AgentContractError("Proposal fields or identity are invalid")
        if any(not isinstance(proposal[x], str) or not proposal[x].strip() or len(proposal[x]) > 2000
               for x in ("rationale", "expected_behavior", "novelty_claim")):
            raise AgentContractError("Proposal explanation is invalid")
        if any(not isinstance(proposal[x], list) or len(proposal[x]) > 8 or
               any(not isinstance(item, str) or not item or len(item) > 500 for item in proposal[x])
               for x in ("risks", "invalidation_conditions")):
            raise AgentContractError("Proposal risk contract is invalid")
        if _FORBIDDEN.search(json.dumps(proposal, ensure_ascii=False)) or _forbidden_control_key(proposal):
            raise AgentContractError("Proposal contains forbidden control, path, code, secret, or quarantined terms")
        template = parse_template(proposal["template"])
        search = proposal["parameter_search"]
        if isinstance(search, list):
            if any(not isinstance(item, dict) or set(item) != {"name", "role", "values"} for item in search):
                raise AgentContractError("Proposal parameter_search is invalid")
            search = {"parameter_roles": {item["name"]: item["role"] for item in search},
                      "search_space": {item["name"]: {"kind": "explicit_values", "values": item["values"]} for item in search}}
            proposal = {**proposal, "parameter_search": search}
        if not isinstance(search, dict) or set(search) != {"parameter_roles", "search_space"}:
            raise AgentContractError("Proposal parameter_search is invalid")
        roles = search["parameter_roles"]; spaces = search["search_space"]
        if not isinstance(roles, dict) or not isinstance(spaces, dict) or set(roles) != set(spaces) or set(roles) - {p.name for p in template.parameters}:
            raise AgentContractError("Proposal parameter contract is invalid")
        if any(role not in _ROLES for role in roles.values()):
            raise AgentContractError("Proposal parameter role is invalid")
        normalized.append(proposal)
    stable = {"schema_version": "1.0.0", "goal_id": goal.goal_id, "iteration": iteration, "provider_id": provider_id,
              "model_id": model_id, "hypothesis_summary": payload["hypothesis_summary"],
              "proposals": normalized, "stop_recommendation": payload["stop_recommendation"]}
    return {**stable, "decision_id": "rd_" + hash_payload(stable), "agent_supplied_decision_id": payload["decision_id"]}
