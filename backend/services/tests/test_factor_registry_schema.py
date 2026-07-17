from dataclasses import replace
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from backend.services.engine.factor_registry.errors import FactorRegistryError, RegistryPolicyError
from backend.services.engine.factor_registry.models import RegistryEntry
from backend.services.engine.factor_registry.decisions import decision_payload, plan_decision
from backend.services.engine.factor_registry.parser import decision_from_payload, entry_payload, parse_entry
from backend.services.engine.factor_registry.policy import default_promotion_policy, policy_payload, validate_policy
from backend.services.engine.factor_registry.enums import RegistryStatus


def entry():
    return RegistryEntry("fi_"+"1"*64,"ft_"+"2"*64,"template",{"window":5},"ds_"+"3"*64,
        ("fv_"+"4"*64,),"fos_"+"5"*64,"fot_"+"6"*64,"vd_"+"7"*64,"fvr_"+"8"*64,
        "fvs_"+"9"*64,None,-1,RegistryStatus.VALIDATION_REJECTED,("validation_gate_failed",),
        {"mean_rank_ic":-0.01},None,{"validation":"a"*64},"ft_"+"2"*64,("factor-validation-result-v1",),None)


def test_entry_round_trip_is_immutable_and_family_is_template():
    parsed=parse_entry(entry_payload(entry())); assert parsed==entry(); assert parsed.family_id==parsed.template_id


@pytest.mark.parametrize("mutation", [
    lambda p:p.pop("factor_instance_id"),
    lambda p:p.__setitem__("status","good"),
    lambda p:p.__setitem__("orientation",0),
    lambda p:p.__setitem__("family_id","ft_"+"f"*64),
    lambda p:p.__setitem__("parameter_values",{"window":6}),
])
def test_entry_closed_schema_and_core_invariants(mutation):
    payload=entry_payload(entry()); mutation(payload)
    if payload.get("parameter_values")=={"window":6}:
        # Schema accepts a bound value; evidence builder, not prose/parser, owns parameter parity.
        assert parse_entry(payload).parameter_values=={"window":6}
    else:
        with pytest.raises(FactorRegistryError): parse_entry(payload)


def test_frozen_metrics_without_frozen_identity_rejected():
    payload=entry_payload(entry()); payload["frozen_metrics_summary"]={"mean_rank_ic":0.1}
    with pytest.raises(FactorRegistryError): parse_entry(payload)


def test_policy_identity_and_non_disableable_safety():
    policy=default_promotion_policy(); assert validate_policy(policy)==policy
    assert policy.requires_human_approval and not policy.allows_auto_approval and not policy.allows_auto_activation
    with pytest.raises(RegistryPolicyError): validate_policy(replace(policy,no_label_leakage=False))
    with pytest.raises(RegistryPolicyError): validate_policy(replace(policy,allows_auto_approval=True))
    with pytest.raises(RegistryPolicyError): validate_policy(replace(policy,minimum_oriented_frozen_mean_rank_ic=0.0))


def test_registry_entry_and_policy_json_schemas_are_strict():
    root = Path(__file__).resolve().parents[3]
    schemas = root / "docs/quantmind2/implementation/schemas"
    entry_schema = json.loads((schemas / "factor_registry_entry_v1.schema.json").read_text())
    policy_schema = json.loads((schemas / "factor_promotion_policy_v1.schema.json").read_text())
    Draft202012Validator(entry_schema).validate(entry_payload(entry()))
    Draft202012Validator(policy_schema).validate(policy_payload(default_promotion_policy()))
    invalid = entry_payload(entry()); invalid["unknown"] = True
    assert list(Draft202012Validator(entry_schema).iter_errors(invalid))
    weakened = policy_payload(default_promotion_policy()); weakened["allows_auto_approval"] = True
    assert list(Draft202012Validator(policy_schema).iter_errors(weakened))


def test_promotion_decision_schema_and_identity_are_strict():
    root = Path(__file__).resolve().parents[3]
    schema = json.loads((root / "docs/quantmind2/implementation/schemas/factor_promotion_decision_v1.schema.json").read_text())
    candidate = replace(entry(), status=RegistryStatus.PROMOTION_CANDIDATE)
    decision = plan_decision(entry=candidate, registry_snapshot_id="frs_"+"a"*64,
        policy_id=default_promotion_policy().policy_id, action="approve", reason="reviewed",
        decided_by="board", decision_source="human", created_at="2026-07-17T05:00:00Z")
    payload = decision_payload(decision)
    Draft202012Validator(schema).validate(payload); assert decision_from_payload(payload) == decision
    payload["reason"] = "tampered"
    with pytest.raises(FactorRegistryError): decision_from_payload(payload)
