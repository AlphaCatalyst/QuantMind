import re

from .canonical import hash_payload
from .enums import DecisionSource, PromotionAction, RegistryStatus
from .errors import FactorRegistryError
from .models import FactorPromotionDecision, FactorPromotionPolicy, RegistryEntry
from .policy import validate_policy
from .schema import require_id, require_known_status


def entry_payload(entry):
    payload = dict(entry.__dict__); payload["status"] = entry.status.value
    if payload.get("research_evidence") is None:
        payload.pop("research_evidence", None)
    if payload.get("fresh_validation_admission") is None:
        payload.pop("fresh_validation_admission", None)
    if payload.get("fresh_validation_status") is None:
        payload.pop("fresh_validation_status", None)
    if payload.get("fresh_validation_evidence") is None:
        payload.pop("fresh_validation_evidence", None)
    payload["parameter_values"] = dict(sorted(entry.parameter_values.items()))
    payload["factor_values_ids"] = list(entry.factor_values_ids)
    payload["status_reasons"] = list(entry.status_reasons)
    payload["evidence_hashes"] = dict(sorted(entry.evidence_hashes.items()))
    payload["created_from_protocols"] = list(entry.created_from_protocols)
    return payload


def parse_entry(payload):
    required = set(RegistryEntry.__dataclass_fields__)
    optional = {"research_evidence", "fresh_validation_admission", "fresh_validation_status",
                "fresh_validation_evidence"}
    if not isinstance(payload, dict) or not required - optional <= set(payload) or set(payload) - required:
        raise FactorRegistryError("Registry Entry fields do not match closed schema")
    payload = {**payload, "research_evidence": payload.get("research_evidence"),
               "fresh_validation_admission": payload.get("fresh_validation_admission"),
               "fresh_validation_status": payload.get("fresh_validation_status"),
               "fresh_validation_evidence": payload.get("fresh_validation_evidence")}
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
    evidence = payload["research_evidence"]
    if evidence is not None:
        expected = {"campaign_id", "research_goal_id", "research_decision_id", "development_evaluation_id",
                    "development_is_contaminated", "is_validation_evidence", "is_frozen_evidence"}
        if not isinstance(evidence, dict) or set(evidence) != expected:
            raise FactorRegistryError("Research evidence fields do not match closed schema")
        patterns = {"campaign_id": r"^rc_[0-9a-f]{64}$", "research_goal_id": r"^rg_[0-9a-f]{64}$",
                    "research_decision_id": r"^rd_[0-9a-f]{64}$", "development_evaluation_id": r"^der_[0-9a-f]{64}$"}
        for key, pattern in patterns.items():
            if not isinstance(evidence[key], str) or not re.fullmatch(pattern, evidence[key]):
                raise FactorRegistryError("Research evidence identity is invalid")
        if evidence["development_is_contaminated"] is not True or evidence["is_validation_evidence"] is not False or evidence["is_frozen_evidence"] is not False:
            raise FactorRegistryError("Research evidence must remain quarantined")
    admission = payload["fresh_validation_admission"]
    if admission is not None:
        expected = {"policy_id", "result_id", "admitted", "reasons", "rank"}
        if not isinstance(admission, dict) or set(admission) != expected:
            raise FactorRegistryError("Fresh Validation admission fields do not match closed schema")
        if (not re.fullmatch(r"^fvap_[0-9a-f]{64}$", str(admission["policy_id"])) or
                not re.fullmatch(r"^fvar_[0-9a-f]{64}$", str(admission["result_id"])) or
                not isinstance(admission["admitted"], bool) or
                not isinstance(admission["reasons"], list) or
                any(not isinstance(reason, str) or not reason for reason in admission["reasons"]) or
                isinstance(admission["rank"], bool) or not isinstance(admission["rank"], int) or admission["rank"] < 1):
            raise FactorRegistryError("Fresh Validation admission evidence is invalid")
        if admission["admitted"] == bool(admission["reasons"]):
            raise FactorRegistryError("Fresh Validation admission outcome is contradictory")
    fresh_status = payload["fresh_validation_status"]
    if fresh_status is not None:
        expected = {"candidate_lock_id", "protocol_id", "watermark_id", "status"}
        if not isinstance(fresh_status, dict) or set(fresh_status) != expected:
            raise FactorRegistryError("Fresh Validation status fields do not match closed schema")
        patterns = {"candidate_lock_id": r"^fvcl_[0-9a-f]{64}$", "protocol_id": r"^fvp_[0-9a-f]{64}$",
                    "watermark_id": r"^fdw_[0-9a-f]{64}$"}
        if any(not re.fullmatch(pattern, str(fresh_status[key])) for key, pattern in patterns.items()) or \
                fresh_status["status"] not in {"awaiting_data", "collecting", "evaluated"}:
            raise FactorRegistryError("Fresh Validation status evidence is invalid")
    fresh_evidence = payload["fresh_validation_evidence"]
    if fresh_evidence is not None:
        expected = {"candidate_lock_id", "protocol_id", "result_id", "passed", "reasons", "rank",
                    "evaluation_window"}
        if not isinstance(fresh_evidence, dict) or set(fresh_evidence) != expected:
            raise FactorRegistryError("Fresh Validation evidence fields do not match closed schema")
        if (not re.fullmatch(r"^fvvr_[0-9a-f]{64}$", str(fresh_evidence["result_id"])) or
                not isinstance(fresh_evidence["passed"], bool) or not isinstance(fresh_evidence["reasons"], list)):
            raise FactorRegistryError("Fresh Validation result evidence is invalid")
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
