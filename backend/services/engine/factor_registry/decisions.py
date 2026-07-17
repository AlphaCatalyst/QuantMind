from dataclasses import replace
from datetime import datetime

from .canonical import hash_payload
from .enums import DecisionSource, PromotionAction, RegistryStatus
from .errors import RegistryDecisionError
from .models import FactorPromotionDecision


def decision_payload(decision, *, include_identity=True):
    payload = dict(decision.__dict__)
    payload["action"] = decision.action.value; payload["decision_source"] = decision.decision_source.value
    if not include_identity:
        payload.pop("decision_id", None); payload.pop("evidence_hash", None)
    return payload


def plan_decision(*, entry, registry_snapshot_id, policy_id, action, reason, decided_by, decision_source, created_at):
    try:
        action = PromotionAction(action); source = DecisionSource(decision_source)
        datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise RegistryDecisionError("invalid decision enum or timestamp") from exc
    if not reason or not decided_by or source not in {DecisionSource.HUMAN, DecisionSource.CONTROL_LAYER}:
        raise RegistryDecisionError("human/control-layer decision identity and reason required")
    allowed = {
        PromotionAction.APPROVE: {RegistryStatus.PROMOTION_CANDIDATE},
        PromotionAction.REJECT: {RegistryStatus.PROMOTION_CANDIDATE},
        PromotionAction.ACTIVATE: {RegistryStatus.APPROVED},
        PromotionAction.RETIRE: {RegistryStatus.APPROVED, RegistryStatus.ACTIVE},
        PromotionAction.INVALIDATE: set(RegistryStatus) - {RegistryStatus.INVALIDATED},
    }
    if entry.status not in allowed[action]:
        raise RegistryDecisionError("decision action is illegal for current Registry status")
    source_payload = {"factor_instance_id": entry.factor_instance_id, "registry_snapshot_id": registry_snapshot_id,
        "policy_id": policy_id, "action": action.value, "reason": reason, "decided_by": decided_by,
        "decision_source": source.value, "created_at": created_at}
    evidence_hash = hash_payload(source_payload)
    return FactorPromotionDecision("fpd_" + evidence_hash, entry.factor_instance_id, registry_snapshot_id,
        policy_id, action, reason, decided_by, source, created_at, evidence_hash)


def status_after_decision(entry, decision):
    mapping = {PromotionAction.APPROVE: RegistryStatus.APPROVED, PromotionAction.REJECT: RegistryStatus.FROZEN_REJECTED,
        PromotionAction.ACTIVATE: RegistryStatus.ACTIVE, PromotionAction.RETIRE: RegistryStatus.RETIRED,
        PromotionAction.INVALIDATE: RegistryStatus.INVALIDATED}
    return replace(entry, status=mapping[decision.action], status_reasons=(f"decision:{decision.action.value}",))
