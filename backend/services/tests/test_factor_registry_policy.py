from dataclasses import replace

import pytest

from backend.services.engine.factor_registry.decisions import plan_decision, status_after_decision
from backend.services.engine.factor_registry.enums import RegistryStatus
from backend.services.engine.factor_registry.errors import RegistryDecisionError, RegistryPolicyError
from backend.services.engine.factor_registry.policy import default_promotion_policy
from backend.services.engine.factor_registry.status import derive_status, promotion_gate
from backend.services.tests.test_factor_registry_schema import entry


POLICY=default_promotion_policy()
VALID={"mean_rank_ic":0.02}
FROZEN={"date_count_valid":111,"median_daily_observations":299,"mean_rank_ic":0.02,"rank_icir":0.2,"rank_ic_positive_rate":0.6}


def test_status_derivation_all_evidence_stages():
    assert derive_status(has_validation=False,validation_passed=False,selected=False,frozen_metrics=None,validation_metrics=None,policy=POLICY)[0] is RegistryStatus.RESEARCH_REGISTERED
    assert derive_status(has_validation=True,validation_passed=False,selected=False,frozen_metrics=None,validation_metrics=VALID,policy=POLICY)[0] is RegistryStatus.VALIDATION_REJECTED
    assert derive_status(has_validation=True,validation_passed=True,selected=False,frozen_metrics=None,validation_metrics=VALID,policy=POLICY)[0] is RegistryStatus.VALIDATION_PASSED_NOT_SELECTED
    assert derive_status(has_validation=True,validation_passed=True,selected=True,frozen_metrics=FROZEN,validation_metrics=VALID,policy=POLICY)[0] is RegistryStatus.PROMOTION_CANDIDATE
    assert derive_status(has_validation=True,validation_passed=True,selected=True,frozen_metrics=FROZEN,validation_metrics=VALID,policy=POLICY,invalidated=True)[0] is RegistryStatus.INVALIDATED


@pytest.mark.parametrize("field,value,reason", [
    ("date_count_valid",59,"frozen_valid_dates_below_policy"),
    ("median_daily_observations",99,"frozen_median_observations_below_policy"),
    ("mean_rank_ic",0.009,"frozen_mean_rank_ic_below_policy"),
    ("rank_icir",0.09,"frozen_rank_icir_below_policy"),
    ("rank_ic_positive_rate",0.51,"frozen_positive_rate_below_policy"),
])
def test_each_statistical_gate_fails_without_absolute_value(field,value,reason):
    metrics={**FROZEN,field:value}; passed,reasons=promotion_gate(VALID,metrics,POLICY)
    assert not passed and reason in reasons


def test_sign_consistency_is_oriented_not_absolute():
    passed,reasons=promotion_gate(VALID,{**FROZEN,"mean_rank_ic":-0.2},POLICY)
    assert not passed and "validation_frozen_sign_mismatch" in reasons


def test_decision_sources_and_transitions():
    candidate=replace(entry(),status=RegistryStatus.PROMOTION_CANDIDATE)
    approve=plan_decision(entry=candidate,registry_snapshot_id="frs_"+"a"*64,policy_id=POLICY.policy_id,
        action="approve",reason="explicit review",decided_by="review-board",decision_source="human",created_at="2026-07-17T05:00:00Z")
    assert status_after_decision(candidate,approve).status is RegistryStatus.APPROVED
    approved=replace(candidate,status=RegistryStatus.APPROVED)
    activate=plan_decision(entry=approved,registry_snapshot_id="frs_"+"a"*64,policy_id=POLICY.policy_id,
        action="activate",reason="control approval",decided_by="control",decision_source="control_layer",created_at="2026-07-17T05:01:00Z")
    assert status_after_decision(approved,activate).status is RegistryStatus.ACTIVE
    retire=plan_decision(entry=replace(candidate,status=RegistryStatus.ACTIVE),registry_snapshot_id="frs_"+"a"*64,policy_id=POLICY.policy_id,
        action="retire",reason="retire",decided_by="human",decision_source="human",created_at="2026-07-17T05:02:00Z")
    assert status_after_decision(replace(candidate,status=RegistryStatus.ACTIVE),retire).status is RegistryStatus.RETIRED


def test_illegal_approve_activate_and_agent_source_rejected():
    for status,action in ((RegistryStatus.VALIDATION_REJECTED,"approve"),(RegistryStatus.FROZEN_REJECTED,"activate")):
        with pytest.raises(RegistryDecisionError): plan_decision(entry=replace(entry(),status=status),registry_snapshot_id="frs_"+"a"*64,
            policy_id=POLICY.policy_id,action=action,reason="x",decided_by="x",decision_source="human",created_at="2026-07-17T05:00:00Z")
    with pytest.raises(RegistryDecisionError): plan_decision(entry=replace(entry(),status=RegistryStatus.PROMOTION_CANDIDATE),registry_snapshot_id="frs_"+"a"*64,
        policy_id=POLICY.policy_id,action="approve",reason="x",decided_by="agent",decision_source="agent",created_at="2026-07-17T05:00:00Z")


def test_frozen_requirement_cannot_be_disabled():
    from backend.services.engine.factor_registry.policy import validate_policy
    with pytest.raises(RegistryPolicyError): validate_policy(replace(POLICY, frozen_artifact_required=False))


def test_decision_is_frozen_and_invalidation_is_explicit():
    from dataclasses import FrozenInstanceError
    candidate=replace(entry(),status=RegistryStatus.PROMOTION_CANDIDATE)
    decision=plan_decision(entry=candidate,registry_snapshot_id="frs_"+"a"*64,policy_id=POLICY.policy_id,
        action="invalidate",reason="lineage revoked",decided_by="control",decision_source="control_layer",created_at="2026-07-17T05:03:00Z")
    assert status_after_decision(candidate,decision).status is RegistryStatus.INVALIDATED
    with pytest.raises(FrozenInstanceError): decision.reason="changed"
