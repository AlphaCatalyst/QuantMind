import hashlib
from typing import Any

from backend.services.engine.factor_dsl.canonical import canonical_json_bytes, template_payload

from .models import FactorOptimizationSpec


CANONICALIZATION_VERSION = "factor-optimization-canonical-json-v1"


def spec_payload(spec: FactorOptimizationSpec) -> dict:
    return {
        "schema_version": spec.schema_version,
        "name": spec.name,
        "description": spec.description,
        "template": template_payload(spec.template),
        "snapshot_id": spec.snapshot_id,
        "parameter_roles": {name: role.value for name, role in sorted(spec.parameter_roles.items())},
        "search_space": {name: dict(space.source) for name, space in sorted(spec.search_spaces.items())},
        "budget": {"max_trials": spec.budget.max_trials, "max_failed_trials": spec.budget.max_failed_trials,
                   "stop_on_first_error": spec.budget.stop_on_first_error},
        "quality_gate": {"minimum_finite_coverage": spec.quality_gate.minimum_finite_coverage,
                         "minimum_median_daily_finite_symbols": spec.quality_gate.minimum_median_daily_finite_symbols,
                         "minimum_date_count": spec.quality_gate.minimum_date_count,
                         "minimum_symbol_count": spec.quality_gate.minimum_symbol_count},
        "candidate_ordering": spec.candidate_ordering,
    }


def hash_payload(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
