from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple


@dataclass(frozen=True)
class LabelContract:
    label_contract_version: str
    label_name: str
    source_columns: Tuple[str, ...]
    observation_time: str
    entry_time: str
    exit_time: str
    horizon: int
    calculation: str
    adjustment_semantics: str
    tradability_policy: str
    missing_policy: str
    cross_sectional_transform: str
    dtype: str
    validation_label_column: str


@dataclass(frozen=True)
class FrozenTestAccessContext:
    protocol_id: str
    validation_dataset_id: str
    candidate_selection_id: str
    access_reason: str
    requested_by: str


@dataclass(frozen=True)
class SplitMetrics:
    date_count_total: int
    date_count_valid: int
    observation_count: int
    mean_ic: Optional[float]
    std_ic: Optional[float]
    icir: Optional[float]
    ic_positive_rate: Optional[float]
    mean_rank_ic: Optional[float]
    std_rank_ic: Optional[float]
    rank_icir: Optional[float]
    rank_ic_positive_rate: Optional[float]
    median_daily_coverage: float
    minimum_daily_coverage: float
    median_daily_observations: float
    minimum_daily_observations: int
    factor_finite_coverage: float
    label_finite_coverage: float
    constant_output: bool


@dataclass(frozen=True)
class ValidationTrialResult:
    study_id: str
    trial_id: str
    template_id: str
    parameters: Mapping[str, float]
    factor_instance_id: str
    factor_values_id: str
    factor_values_parquet_sha256: str
    orientation: Optional[int]
    orientation_source: str
    train_raw_metrics: SplitMetrics
    train_oriented_metrics: Optional[SplitMetrics]
    validation_raw_metrics: SplitMetrics
    validation_oriented_metrics: Optional[SplitMetrics]
    eligible_for_selection: bool
    ineligibility_reasons: Tuple[str, ...]
    validation_rank: Optional[int]
    selected_for_frozen: bool


@dataclass(frozen=True)
class FactorValidationSpec:
    schema_version: str
    name: str
    description: str
    validation_dataset_id: str
    optimization_study_ids: Tuple[str, ...]
    trial_ids: Tuple[str, ...]
    metrics: Tuple[str, ...]
    minimum_requirements: Mapping[str, Any]
    candidate_selection: Mapping[str, Any]
    frozen_test_policy: Mapping[str, Any]
