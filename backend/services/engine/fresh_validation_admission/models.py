from dataclasses import dataclass
from typing import Any, Mapping, Tuple


@dataclass(frozen=True)
class FreshValidationAdmissionPolicy:
    policy_id: str
    version: str
    research_entry_status_required: bool
    campaign_artifact_valid_required: bool
    optimization_artifact_valid_required: bool
    development_artifact_valid_required: bool
    no_label_leakage_required: bool
    no_frozen_access_required: bool
    development_period_contaminated_required: bool
    orientation_frozen_before_development_required: bool
    factor_values_valid_required: bool
    non_constant_output_required: bool
    zero_infinity_count_required: bool
    minimum_valid_rank_ic_dates: int
    minimum_median_daily_observations: int
    minimum_factor_finite_coverage: float
    minimum_oriented_mean_rank_ic: float
    minimum_oriented_rank_ic_positive_rate: float
    require_rank_icir_not_null: bool
    maximum_admitted_candidates: int
    maximum_candidates_per_family: int
    canonical_hash: str


@dataclass(frozen=True)
class CandidateEvidence:
    factor_instance_id: str
    campaign_id: str
    template_id: str
    family_id: str
    study_id: str
    trial_id: str
    development_result_id: str
    research_entry_status: str
    campaign_artifact_valid: bool
    optimization_artifact_valid: bool
    development_artifact_valid: bool
    no_label_leakage: bool
    no_frozen_access: bool
    development_period_contaminated: bool
    orientation_frozen_before_development: bool
    factor_values_valid: bool
    constant_output: bool
    infinity_count: int
    metrics_summary: Mapping[str, Any]


@dataclass(frozen=True)
class AdmissionCandidateResult:
    factor_instance_id: str
    campaign_id: str
    template_id: str
    study_id: str
    trial_id: str
    development_result_id: str
    policy_id: str
    metrics_summary: Mapping[str, Any]
    admitted: bool
    reasons: Tuple[str, ...]
    rank: int


@dataclass(frozen=True)
class FreshValidationAdmissionResult:
    result_id: str
    policy: FreshValidationAdmissionPolicy
    candidates: Tuple[AdmissionCandidateResult, ...]
    admitted_factor_instance_ids: Tuple[str, ...]
    rejected_factor_instance_ids: Tuple[str, ...]
    artifact_path: str = ""
    exact_existing: bool = False
