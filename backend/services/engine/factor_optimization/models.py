from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

from backend.services.engine.factor_dsl.models import FactorTemplate

from .enums import ParameterRole, StudyStatus, TrialStatus


@dataclass(frozen=True)
class SearchSpace:
    kind: str
    values: Tuple[float, ...]
    source: Mapping[str, Any]


@dataclass(frozen=True)
class OptimizationBudget:
    max_trials: int
    max_failed_trials: int
    stop_on_first_error: bool


@dataclass(frozen=True)
class QualityGate:
    minimum_finite_coverage: float = 0.60
    minimum_median_daily_finite_symbols: int = 20
    minimum_date_count: int = 20
    minimum_symbol_count: int = 20


@dataclass(frozen=True)
class FactorOptimizationSpec:
    schema_version: str
    name: str
    description: str
    template: FactorTemplate
    snapshot_id: str
    parameter_roles: Mapping[str, ParameterRole]
    search_spaces: Mapping[str, SearchSpace]
    budget: OptimizationBudget
    quality_gate: QualityGate
    candidate_ordering: str


@dataclass(frozen=True)
class PlannedTrial:
    trial_id: str
    ordinal: int
    parameters: Mapping[str, float]
    factor_instance_id: str


@dataclass(frozen=True)
class FactorOptimizationStudy:
    study_id: str
    template_id: str
    snapshot_id: str
    trials: Tuple[PlannedTrial, ...]
    spec: FactorOptimizationSpec


@dataclass(frozen=True)
class MechanicalMetrics:
    row_count: int
    non_null_count: int
    null_count: int
    finite_coverage: float
    symbol_count: int
    date_count: int
    warmup_periods: int
    warmup_date_count: int
    median_daily_finite_symbols: float
    minimum_daily_finite_symbols: int
    maximum_daily_finite_symbols: int
    daily_coverage_median: float
    daily_coverage_minimum: float
    global_mean: Optional[float]
    global_std: Optional[float]
    global_min: Optional[float]
    global_max: Optional[float]
    unique_finite_count: int
    constant_output: bool
    infinity_count: int


@dataclass(frozen=True)
class FactorOptimizationTrial:
    trial_id: str
    ordinal: int
    parameters: Mapping[str, float]
    factor_instance_id: str
    status: TrialStatus
    factor_values_id: Optional[str]
    parquet_sha256: Optional[str]
    metrics: Optional[MechanicalMetrics]
    eligible_for_validation: bool
    ineligibility_reasons: Tuple[str, ...]
    error_code: Optional[str]


@dataclass(frozen=True)
class FactorOptimizationResult:
    study_id: str
    result_id: str
    status: StudyStatus
    trials: Tuple[FactorOptimizationTrial, ...]
    validation_candidate_order: Tuple[str, ...]
    study_manifest_hash: str
    artifact_path: str
    exact_existing: bool
