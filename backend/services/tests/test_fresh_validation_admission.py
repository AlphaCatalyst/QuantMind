from dataclasses import replace
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from backend.services.engine.fresh_validation_admission.artifact import publish_admission_result, validate_admission_result
from backend.services.engine.fresh_validation_admission.errors import FreshValidationAdmissionError
from backend.services.engine.fresh_validation_admission.evaluator import evaluate_admission
from backend.services.engine.fresh_validation_admission.models import CandidateEvidence
from backend.services.engine.fresh_validation_admission.policy import default_admission_policy, validate_admission_policy
from backend.services.engine.research_campaign.memory import sanitize_memory
from tools.quantmind2.fresh_validation_admission import run


def evidence(n=1, family=None, **changes):
    values = dict(factor_instance_id=f"fi_{n:064x}", campaign_id="rc_"+"1"*64,
        template_id=f"ft_{n:064x}", family_id=family or f"family-{n}", study_id="fos_"+f"{n:064x}",
        trial_id="fot_"+f"{n:064x}", development_result_id="der_"+f"{n:064x}",
        research_entry_status="research_registered", campaign_artifact_valid=True,
        optimization_artifact_valid=True, development_artifact_valid=True,
        no_label_leakage=True, no_frozen_access=True, development_period_contaminated=True,
        orientation_frozen_before_development=True, factor_values_valid=True,
        constant_output=False, infinity_count=0,
        metrics_summary={"date_count_valid":242,"median_daily_observations":300,
            "factor_finite_coverage":1.0,"mean_rank_ic":0.04-n/1000,
            "rank_icir":0.3-n/1000,"rank_ic_positive_rate":0.6})
    values.update(changes); return CandidateEvidence(**values)


def test_policy_identity_and_safety_gates_cannot_be_disabled():
    policy=default_admission_policy(); assert validate_admission_policy(policy)==policy
    with pytest.raises(FreshValidationAdmissionError): validate_admission_policy(replace(policy,no_frozen_access_required=False))
    with pytest.raises(FreshValidationAdmissionError): validate_admission_policy(replace(policy,minimum_oriented_mean_rank_ic=-1))


@pytest.mark.parametrize("changes,reason", [
    ({"metrics_summary":{"date_count_valid":119,"median_daily_observations":300,"factor_finite_coverage":1.0,"mean_rank_ic":.1,"rank_icir":.2,"rank_ic_positive_rate":.6}},"INSUFFICIENT_VALID_RANK_IC_DATES"),
    ({"metrics_summary":{"date_count_valid":242,"median_daily_observations":99,"factor_finite_coverage":1.0,"mean_rank_ic":.1,"rank_icir":.2,"rank_ic_positive_rate":.6}},"INSUFFICIENT_MEDIAN_DAILY_OBSERVATIONS"),
    ({"metrics_summary":{"date_count_valid":242,"median_daily_observations":300,"factor_finite_coverage":.59,"mean_rank_ic":.1,"rank_icir":.2,"rank_ic_positive_rate":.6}},"FACTOR_FINITE_COVERAGE_BELOW_GATE"),
    ({"metrics_summary":{"date_count_valid":242,"median_daily_observations":300,"factor_finite_coverage":1.0,"mean_rank_ic":-.01,"rank_icir":.2,"rank_ic_positive_rate":.6}},"DEVELOPMENT_MEAN_RANK_IC_BELOW_GATE"),
    ({"metrics_summary":{"date_count_valid":242,"median_daily_observations":300,"factor_finite_coverage":1.0,"mean_rank_ic":.1,"rank_icir":None,"rank_ic_positive_rate":.6}},"DEVELOPMENT_RANK_ICIR_NULL"),
    ({"metrics_summary":{"date_count_valid":242,"median_daily_observations":300,"factor_finite_coverage":1.0,"mean_rank_ic":.1,"rank_icir":.2,"rank_ic_positive_rate":.49}},"DEVELOPMENT_RANK_IC_POSITIVE_RATE_BELOW_GATE"),
    ({"constant_output":True},"CONSTANT_OUTPUT"), ({"no_frozen_access":False},"FROZEN_ACCESS_DETECTED"),
    ({"orientation_frozen_before_development":False},"ORIENTATION_NOT_FROZEN_BEFORE_DEVELOPMENT")])
def test_first_failure_is_deterministic(changes, reason):
    row=evaluate_admission(default_admission_policy(),[evidence(**changes)]).candidates[0]
    assert not row.admitted and row.reasons==(reason,)


def test_total_family_and_stable_ordering_use_signed_metrics():
    items=[evidence(i, family=("same" if i in (1,2) else f"f{i}")) for i in range(1,6)]
    result=evaluate_admission(default_admission_policy(),items)
    assert [x.rank for x in result.candidates]==[1,2,3,4,5]
    assert len(result.admitted_factor_instance_ids)==3
    assert result.candidates[1].reasons==("FAMILY_CANDIDATE_BUDGET_EXCEEDED",)
    negative=evaluate_admission(default_admission_policy(),[evidence(metrics_summary={"date_count_valid":242,"median_daily_observations":300,"factor_finite_coverage":1.0,"mean_rank_ic":-.03,"rank_icir":-.1,"rank_ic_positive_rate":.45})])
    assert negative.rejected_factor_instance_ids


def test_immutable_artifact_exact_replay_and_tamper(tmp_path):
    result=evaluate_admission(default_admission_policy(),[evidence()])
    first=publish_admission_result(tmp_path,result); second=publish_admission_result(tmp_path,result)
    assert first.result_id==second.result_id and second.exact_existing
    path=Path(second.artifact_path)/"admitted.json"; path.write_text('{}')
    with pytest.raises(FreshValidationAdmissionError): validate_admission_result(tmp_path,result.result_id)


def test_sanitized_memory_exposes_outcome_only():
    memory=sanitize_memory([],[],[{"factor_instance_id":"fi_"+"1"*64,"admitted":False}])
    assert memory["fresh_validation_feedback"]==[{"factor_instance_id":"fi_"+"1"*64,"outcome":"not_advanced_to_fresh_validation"}]
    text=json.dumps(memory).lower(); assert "rank_ic" not in text and "frozen_result" not in text


def test_real_sibling_artifacts_reconcile_and_admit_exactly(tmp_path):
    first=run(tmp_path); second=run(tmp_path)
    registry=first["registry"]; admission=first["admission"]
    assert registry.registry_snapshot_id=="frs_f0a08cc472270cf80f2ae8c1141de17871dacbe2edccba8eb4ffe05ca45d3ba4"
    assert len(registry.entries)==19 and len(admission.candidates)==5
    assert len(admission.admitted_factor_instance_ids)==3 and len(admission.rejected_factor_instance_ids)==2
    external=next(x for x in admission.candidates if x.factor_instance_id=="fi_207c3b82f4b9f3a77e064513ad03a64e6e2d69dc939e6fc1e68aa4fc8fad0549")
    assert external.metrics_summary["mean_rank_ic"]==-0.03098286034429056
    assert external.reasons==("DEVELOPMENT_MEAN_RANK_IC_BELOW_GATE",)
    assert all(x.status.value=="research_registered" for x in registry.entries if x.research_evidence)
    assert not any(x.status.value in {"promotion_candidate","approved","active"} for x in registry.entries)
    assert second["registry"].exact_existing and second["admission"].exact_existing and second["reconciliation"].exact_existing
    root=Path(__file__).resolve().parents[3]
    policy_schema=json.loads((root/"docs/quantmind2/implementation/schemas/fresh_validation_admission_policy_v1.schema.json").read_text())
    reconciliation_schema=json.loads((root/"docs/quantmind2/implementation/schemas/registry_reconciliation_v1.schema.json").read_text())
    entry_schema=json.loads((root/"docs/quantmind2/implementation/schemas/factor_registry_entry_v1.schema.json").read_text())
    Draft202012Validator(policy_schema).validate(json.loads((Path(admission.artifact_path)/"policy.json").read_text()))
    rec_path=Path(first["reconciliation"].artifact_path)/"reconciliation.json"
    Draft202012Validator(reconciliation_schema).validate(json.loads(rec_path.read_text()))
    agent_entry=next(x for x in registry.entries if x.fresh_validation_admission)
    from backend.services.engine.factor_registry.parser import entry_payload
    Draft202012Validator(entry_schema).validate(entry_payload(agent_entry))
