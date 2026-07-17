from dataclasses import asdict

from .canonical import hash_payload
from .errors import FreshValidationAdmissionError
from .models import FreshValidationAdmissionPolicy


VERSION = "1.0.0"
_SAFETY = ("research_entry_status_required", "campaign_artifact_valid_required",
    "optimization_artifact_valid_required", "development_artifact_valid_required",
    "no_label_leakage_required", "no_frozen_access_required",
    "development_period_contaminated_required", "orientation_frozen_before_development_required",
    "factor_values_valid_required", "non_constant_output_required", "zero_infinity_count_required")


def policy_payload(policy): return asdict(policy)


def default_admission_policy():
    body = {"version": VERSION, **{name: True for name in _SAFETY},
        "minimum_valid_rank_ic_dates": 120, "minimum_median_daily_observations": 100,
        "minimum_factor_finite_coverage": 0.60, "minimum_oriented_mean_rank_ic": 0.00,
        "minimum_oriented_rank_ic_positive_rate": 0.50, "require_rank_icir_not_null": True,
        "maximum_admitted_candidates": 3, "maximum_candidates_per_family": 1}
    digest = hash_payload(body)
    return FreshValidationAdmissionPolicy(policy_id="fvap_" + digest, canonical_hash=digest, **body)


def validate_admission_policy(policy):
    if not isinstance(policy, FreshValidationAdmissionPolicy) or policy.version != VERSION:
        raise FreshValidationAdmissionError("Fresh Validation admission policy/version is invalid")
    if any(getattr(policy, name) is not True for name in _SAFETY):
        raise FreshValidationAdmissionError("Fresh Validation safety gates cannot be disabled")
    body = {key: value for key, value in asdict(policy).items() if key not in {"policy_id", "canonical_hash"}}
    digest = hash_payload(body)
    if policy.policy_id != "fvap_" + digest or policy.canonical_hash != digest:
        raise FreshValidationAdmissionError("Fresh Validation admission policy identity is invalid")
    expected = default_admission_policy()
    if policy != expected:
        raise FreshValidationAdmissionError("Fresh Validation admission v1 thresholds are frozen")
    return policy
