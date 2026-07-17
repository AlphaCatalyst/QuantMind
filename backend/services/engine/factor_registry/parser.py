import re

from .canonical import hash_payload
from .enums import DecisionSource, PromotionAction, RegistryStatus
from .errors import FactorRegistryError
from .models import FactorPromotionDecision, FactorPromotionPolicy, RegistryEntry
from .policy import validate_policy
from .schema import require_id, require_known_status


def entry_payload(entry):
    payload = dict(entry.__dict__); payload["status"] = entry.status.value
    payload["parameter_values"] = dict(sorted(entry.parameter_values.items()))
    payload["factor_values_ids"] = list(entry.factor_values_ids)
    payload["status_reasons"] = list(entry.status_reasons)
    payload["evidence_hashes"] = dict(sorted(entry.evidence_hashes.items()))
    payload["created_from_protocols"] = list(entry.created_from_protocols)
    return payload


def parse_entry(payload):
    required = set(RegistryEntry.__dataclass_fields__)
    if not isinstance(payload, dict) or set(payload) != required:
        raise FactorRegistryError("Registry Entry fields do not match closed schema")
    require_id("factor_instance_id", payload["factor_instance_id"]); require_id("template_id", payload["template_id"])
    require_id("dataset_snapshot_id", payload["dataset_snapshot_id"])
    require_id("study_id", payload["optimization_study_id"]); require_id("trial_id", payload["optimization_trial_id"])
    for value in payload["factor_values_ids"]: require_id("factor_values_id", value)
    require_id("validation_dataset_id", payload["validation_dataset_id"], nullable=True)
    require_id("validation_result_id", payload["validation_result_id"], nullable=True)
    require_id("selection_id", payload["candidate_selection_id"], nullable=True)
    require_id("frozen_result_id", payload["frozen_result_id"], nullable=True)
    status = require_known_status(payload["status"])
    if payload["family_id"] != payload["template_id"] or payload["orientation"] not in (-1, 1, None):
        raise FactorRegistryError("Registry Entry family/orientation mismatch")
    if payload["frozen_result_id"] is None and payload["frozen_metrics_summary"] is not None:
        raise FactorRegistryError("Frozen metrics require Frozen evidence")
    return RegistryEntry(**{**payload, "status": status, "factor_values_ids": tuple(payload["factor_values_ids"]),
        "status_reasons": tuple(payload["status_reasons"]), "created_from_protocols": tuple(payload["created_from_protocols"])})


def policy_from_payload(payload):
    try: policy = FactorPromotionPolicy(**payload)
    except TypeError as exc: raise FactorRegistryError("Promotion Policy fields invalid") from exc
    return validate_policy(policy)


def decision_from_payload(payload):
    try:
        required = set(FactorPromotionDecision.__dataclass_fields__)
        if not isinstance(payload, dict) or set(payload) != required:
            raise ValueError("closed Decision schema mismatch")
        require_id("factor_instance_id", payload["factor_instance_id"])
        if not re.fullmatch(r"^frs_[0-9a-f]{64}$", payload["registry_snapshot_id"]):
            raise ValueError("invalid Registry Snapshot ID")
        if not re.fullmatch(r"^fpp_[0-9a-f]{64}$", payload["policy_id"]):
            raise ValueError("invalid Promotion Policy ID")
        source = {key: value for key, value in payload.items() if key not in {"decision_id", "evidence_hash"}}
        digest = hash_payload(source)
        if payload["evidence_hash"] != digest or payload["decision_id"] != "fpd_" + digest:
            raise ValueError("Promotion Decision identity mismatch")
        return FactorPromotionDecision(**{**payload, "action": PromotionAction(payload["action"]),
            "decision_source": DecisionSource(payload["decision_source"])})
    except (TypeError, ValueError, KeyError) as exc:
        raise FactorRegistryError("Promotion Decision fields invalid") from exc
