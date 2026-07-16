import json
import re
from pathlib import Path

from backend.services.engine.factor_dsl.parser import parse_template

from .enums import ParameterRole
from .errors import OptimizationSpecError
from .identity import OPTIMIZATION_SCHEMA_VERSION
from .models import FactorOptimizationSpec, OptimizationBudget, QualityGate
from .roles import validate_parameter_roles
from .search_space import parse_search_space


NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
SNAPSHOT_RE = re.compile(r"^ds_[0-9a-f]{64}$")


def _exact(value, required, optional=(), where="object"):
    if not isinstance(value, dict):
        raise OptimizationSpecError(f"{where} must be an object")
    missing = set(required) - set(value)
    extra = set(value) - set(required) - set(optional)
    if missing or extra:
        raise OptimizationSpecError(f"{where} fields invalid: missing={sorted(missing)}, extra={sorted(extra)}")


def parse_optimization_spec(payload):
    if isinstance(payload, (str, bytes, Path)):
        if isinstance(payload, Path) or (isinstance(payload, str) and not payload.lstrip().startswith("{")):
            payload = json.loads(Path(payload).read_text(encoding="utf-8"))
        else:
            payload = json.loads(payload)
    required = {"schema_version", "name", "description", "template", "snapshot_id", "parameter_roles",
                "search_space", "budget", "quality_gate", "candidate_ordering"}
    _exact(payload, required, where="optimization spec")
    if payload["schema_version"] != OPTIMIZATION_SCHEMA_VERSION:
        raise OptimizationSpecError("schema_version must be 1.0.0")
    if not isinstance(payload["name"], str) or not NAME_RE.fullmatch(payload["name"]):
        raise OptimizationSpecError("name must be a safe identifier")
    if not isinstance(payload["description"], str) or not payload["description"].strip() or len(payload["description"]) > 2000:
        raise OptimizationSpecError("description must be non-empty and bounded")
    if not isinstance(payload["snapshot_id"], str) or not SNAPSHOT_RE.fullmatch(payload["snapshot_id"]):
        raise OptimizationSpecError("snapshot_id must be an immutable Dataset Snapshot identity")
    template = parse_template(payload["template"])
    definitions = {p.name: p for p in template.parameters}
    raw_roles = payload["parameter_roles"]
    raw_spaces = payload["search_space"]
    if not isinstance(raw_roles, dict) or not isinstance(raw_spaces, dict) or not raw_spaces:
        raise OptimizationSpecError("parameter_roles and non-empty search_space must be objects")
    if set(raw_roles) != set(raw_spaces):
        raise OptimizationSpecError("each searched parameter must have exactly one explicit role")
    if set(raw_spaces) - set(definitions):
        raise OptimizationSpecError(f"unknown searched parameters: {sorted(set(raw_spaces)-set(definitions))}")
    roles = {}
    for name, raw_role in raw_roles.items():
        try:
            roles[name] = ParameterRole(raw_role)
        except ValueError as exc:
            raise OptimizationSpecError(f"invalid parameter role for {name}") from exc
    validate_parameter_roles(template, roles)
    spaces = {name: parse_search_space(raw_spaces[name], definitions[name]) for name in raw_spaces}
    _exact(payload["budget"], {"max_trials", "max_failed_trials"}, {"stop_on_first_error"}, "budget")
    max_trials = payload["budget"]["max_trials"]
    max_failed = payload["budget"]["max_failed_trials"]
    stop = payload["budget"].get("stop_on_first_error", False)
    if any(isinstance(x, bool) or not isinstance(x, int) for x in (max_trials, max_failed)) or not 1 <= max_trials <= 256 or not 0 <= max_failed <= 32:
        raise OptimizationSpecError("budget must satisfy max_trials 1..256 and max_failed_trials 0..32")
    if not isinstance(stop, bool):
        raise OptimizationSpecError("stop_on_first_error must be boolean")
    _exact(payload["quality_gate"], set(), {"minimum_finite_coverage", "minimum_median_daily_finite_symbols",
                                            "minimum_date_count", "minimum_symbol_count"}, "quality_gate")
    gate = QualityGate(**payload["quality_gate"])
    if isinstance(gate.minimum_finite_coverage, bool) or not isinstance(gate.minimum_finite_coverage, (int, float)) or not 0 <= gate.minimum_finite_coverage <= 1:
        raise OptimizationSpecError("minimum_finite_coverage must be in [0,1]")
    for field in ("minimum_median_daily_finite_symbols", "minimum_date_count", "minimum_symbol_count"):
        value = getattr(gate, field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise OptimizationSpecError(f"{field} must be a positive integer")
    if payload["candidate_ordering"] != "mechanical_validation_readiness_v1":
        raise OptimizationSpecError("candidate_ordering must use the frozen mechanical rule")
    return FactorOptimizationSpec(OPTIMIZATION_SCHEMA_VERSION, payload["name"], payload["description"].strip(),
                                  template, payload["snapshot_id"], roles, spaces,
                                  OptimizationBudget(max_trials, max_failed, stop), gate,
                                  payload["candidate_ordering"])
