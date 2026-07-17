from .canonical import hash_payload
from .models import AdmissionCandidateResult, FreshValidationAdmissionResult
from .policy import policy_payload, validate_admission_policy


_SAFETY_CHECKS = (
    ("research_entry_status", lambda x: x == "research_registered", "RESEARCH_ENTRY_STATUS_INVALID"),
    ("campaign_artifact_valid", bool, "CAMPAIGN_ARTIFACT_INVALID"),
    ("optimization_artifact_valid", bool, "OPTIMIZATION_ARTIFACT_INVALID"),
    ("development_artifact_valid", bool, "DEVELOPMENT_ARTIFACT_INVALID"),
    ("no_label_leakage", bool, "LABEL_LEAKAGE_DETECTED"),
    ("no_frozen_access", bool, "FROZEN_ACCESS_DETECTED"),
    ("development_period_contaminated", bool, "DEVELOPMENT_PERIOD_NOT_CONTAMINATED"),
    ("orientation_frozen_before_development", bool, "ORIENTATION_NOT_FROZEN_BEFORE_DEVELOPMENT"),
    ("factor_values_valid", bool, "FACTOR_VALUES_INVALID"),
    ("constant_output", lambda x: x is False, "CONSTANT_OUTPUT"),
    ("infinity_count", lambda x: x == 0, "INFINITY_PRESENT"),
)


def _primary_gate_failure(item, policy):
    for name, predicate, reason in _SAFETY_CHECKS:
        if not predicate(getattr(item, name)): return reason
    metrics = item.metrics_summary
    checks = (
        (metrics.get("date_count_valid", 0) >= policy.minimum_valid_rank_ic_dates, "INSUFFICIENT_VALID_RANK_IC_DATES"),
        (metrics.get("median_daily_observations", 0) >= policy.minimum_median_daily_observations, "INSUFFICIENT_MEDIAN_DAILY_OBSERVATIONS"),
        (metrics.get("factor_finite_coverage", 0) >= policy.minimum_factor_finite_coverage, "FACTOR_FINITE_COVERAGE_BELOW_GATE"),
        (metrics.get("mean_rank_ic") is not None and metrics["mean_rank_ic"] >= policy.minimum_oriented_mean_rank_ic,
         "DEVELOPMENT_MEAN_RANK_IC_BELOW_GATE"),
        (not policy.require_rank_icir_not_null or metrics.get("rank_icir") is not None, "DEVELOPMENT_RANK_ICIR_NULL"),
        (metrics.get("rank_ic_positive_rate") is not None and
         metrics["rank_ic_positive_rate"] >= policy.minimum_oriented_rank_ic_positive_rate,
         "DEVELOPMENT_RANK_IC_POSITIVE_RATE_BELOW_GATE"),
    )
    return next((reason for passed, reason in checks if not passed), None)


def _order_key(item):
    metrics = item.metrics_summary; rank_icir = metrics.get("rank_icir")
    return (-metrics.get("mean_rank_ic", float("-inf")), rank_icir is None,
            -(rank_icir if rank_icir is not None else 0.0),
            -metrics.get("rank_ic_positive_rate", float("-inf")),
            -metrics.get("factor_finite_coverage", float("-inf")), item.factor_instance_id)


def candidate_payload(item):
    return {"factor_instance_id": item.factor_instance_id, "campaign_id": item.campaign_id,
        "template_id": item.template_id, "study_id": item.study_id, "trial_id": item.trial_id,
        "development_result_id": item.development_result_id, "policy_id": item.policy_id,
        "metrics_summary": dict(item.metrics_summary), "admitted": item.admitted,
        "reasons": list(item.reasons), "rank": item.rank}


def evaluate_admission(policy, evidence):
    validate_admission_policy(policy); ordered = sorted(evidence, key=_order_key)
    rows = []; admitted = 0; families = {}
    for rank, item in enumerate(ordered, 1):
        reason = _primary_gate_failure(item, policy)
        if reason is None and families.get(item.family_id, 0) >= policy.maximum_candidates_per_family:
            reason = "FAMILY_CANDIDATE_BUDGET_EXCEEDED"
        if reason is None and admitted >= policy.maximum_admitted_candidates:
            reason = "TOTAL_CANDIDATE_BUDGET_EXCEEDED"
        is_admitted = reason is None
        if is_admitted:
            admitted += 1; families[item.family_id] = families.get(item.family_id, 0) + 1
        rows.append(AdmissionCandidateResult(item.factor_instance_id, item.campaign_id,
            item.template_id, item.study_id, item.trial_id, item.development_result_id,
            policy.policy_id, dict(item.metrics_summary), is_admitted, (() if is_admitted else (reason,)), rank))
    stable = {"schema_version": "fresh-validation-admission-result-v1",
              "policy": policy_payload(policy), "candidates": [candidate_payload(x) for x in rows]}
    result_id = "fvar_" + hash_payload(stable)
    return FreshValidationAdmissionResult(result_id, policy, tuple(rows),
        tuple(x.factor_instance_id for x in rows if x.admitted),
        tuple(x.factor_instance_id for x in rows if not x.admitted))
