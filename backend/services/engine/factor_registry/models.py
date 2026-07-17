from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

from .enums import DecisionSource, PromotionAction, RegistryStatus


@dataclass(frozen=True)
class FactorPromotionPolicy:
    policy_id: str
    version: str
    git_evidence_complete: bool
    validation_artifact_valid: bool
    frozen_artifact_required: bool
    no_label_leakage: bool
    development_quarantine_respected: bool
    train_only_orientation: bool
    frozen_candidate_selection_immutable: bool
    frozen_reselection_forbidden: bool
    minimum_frozen_valid_dates: int
    minimum_frozen_median_daily_observations: int
    minimum_oriented_frozen_mean_rank_ic: float
    minimum_oriented_frozen_rank_icir: float
    minimum_oriented_frozen_rank_ic_positive_rate: float
    require_same_oriented_sign_as_validation: bool
    requires_human_approval: bool
    allows_auto_approval: bool
    allows_auto_activation: bool
    rationale: str
    canonical_hash: str


@dataclass(frozen=True)
class RegistryEntry:
    factor_instance_id: str
    template_id: str
    template_name: str
    parameter_values: Mapping[str, float]
    dataset_snapshot_id: str
    factor_values_ids: Tuple[str, ...]
    optimization_study_id: str
    optimization_trial_id: str
    validation_dataset_id: Optional[str]
    validation_result_id: Optional[str]
    candidate_selection_id: Optional[str]
    frozen_result_id: Optional[str]
    orientation: Optional[int]
    status: RegistryStatus
    status_reasons: Tuple[str, ...]
    validation_metrics_summary: Optional[Mapping[str, Any]]
    frozen_metrics_summary: Optional[Mapping[str, Any]]
    evidence_hashes: Mapping[str, str]
    family_id: str
    created_from_protocols: Tuple[str, ...]
    redundancy_group: Optional[str] = None


@dataclass(frozen=True)
class FactorPromotionDecision:
    decision_id: str
    factor_instance_id: str
    registry_snapshot_id: str
    policy_id: str
    action: PromotionAction
    reason: str
    decided_by: str
    decision_source: DecisionSource
    created_at: str
    evidence_hash: str


@dataclass(frozen=True)
class RegistrySnapshot:
    registry_snapshot_id: str
    policy: FactorPromotionPolicy
    entries: Tuple[RegistryEntry, ...]
    decisions: Tuple[FactorPromotionDecision, ...]
    previous_registry_snapshot_id: Optional[str]
    artifact_path: str
    exact_existing: bool
