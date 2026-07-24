from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from backend.services.engine.tushare_cutover.canonical import hash_payload


FEATURE_CATALOG_ID = "tfc3_b903c85e328d359181c18ce3444d458a41ee970be8b2f6b79eff83cc6d523aea"
PRIMITIVE_CATALOG_ID = "tpc2_b9f6112bec9f5524d8d14eb0ff8d40244c0e143557d49c1676c2630686387208"
SEEDS = (20260701, 20260702, 20260703)


@dataclass(frozen=True)
class FixedConfigurationModelSpecV1:
    program_name: str = "fixed_configuration_model_alpha_program_001"
    provider_id: str = "tushare-pro-v1"
    model_type: str = "lightgbm"
    label_name: str = "model_label"
    feature_catalog_id: str = FEATURE_CATALOG_ID
    primitive_catalog_id: str = PRIMITIVE_CATALOG_ID
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "objective": "regression",
        "metric": "l2",
        "boosting_type": "gbdt",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "max_depth": -1,
        "min_data_in_leaf": 50,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "lambda_l1": 0.0,
        "lambda_l2": 0.0,
        "verbosity": -1,
        "num_threads": 1,
        "deterministic": True,
        "force_col_wise": True,
    })
    number_of_boosting_rounds: int = 200
    early_stopping_policy: str = "disabled_fixed_rounds"
    seeds: tuple[int, ...] = SEEDS
    preprocessing: str = "same-date cross-sectional 5*MAD winsor then population zscore; missing->0"
    score_construction: str = "equal-weight mean of three seed predictions"
    strategy_protocol: dict[str, Any] = field(default_factory=lambda: {
        "topk": 20,
        "n_drop": 5,
        "rebalance_interval": 10,
        "weighting": "equal_weight",
        "signal_lag": 1,
        "execution": "open",
        "benchmark": "CSI300",
    })

    def payload(self) -> dict[str, Any]:
        if self.model_type != "lightgbm" or self.label_name != "model_label":
            raise ValueError("only the existing LightGBM/model_label chain is authorized")
        if self.seeds != SEEDS or self.early_stopping_policy != "disabled_fixed_rounds":
            raise ValueError("fixed seed and early-stopping contracts changed")
        if self.number_of_boosting_rounds <= 0:
            raise ValueError("fixed boosting rounds must be positive")
        stable = asdict(self) | {
            "schema_version": "fixed-configuration-model-spec-v1",
            "evidence_semantics": "retrospective_research_only",
            "model_hyperparameter_optimization_calls": 0,
            "strategy_optimization_calls": 0,
            "combined_optimization_calls": 0,
            "promotion_writes": 0,
        }
        return stable | {"model_spec_id": "fcms1_" + hash_payload(stable)}


@dataclass(frozen=True)
class ModelFeatureBundleSpecV1:
    model_spec_id: str
    bundle_name: str
    candidate_feature_names: tuple[str, ...]
    selection_rule: str
    training_only_selection: bool

    def payload(self) -> dict[str, Any]:
        if self.bundle_name not in {
            "existing_technical_core",
            "expanded_technical_space",
            "combined_decorrelated_technical",
        }:
            raise ValueError("unregistered model Feature Bundle")
        if not self.candidate_feature_names:
            raise ValueError("Feature Bundle cannot be empty")
        if self.bundle_name == "combined_decorrelated_technical" and not self.training_only_selection:
            raise ValueError("Bundle C must select members on each training fold")
        stable = asdict(self) | {
            "schema_version": "model-feature-bundle-spec-v1",
            "provider_id": "tushare-pro-v1",
            "frozen_before_training": True,
            "label_used_for_membership": False,
            "performance_used_for_membership": False,
            "promotion_writes": 0,
        }
        return stable | {"bundle_id": "mfbs1_" + hash_payload(stable)}


@dataclass(frozen=True)
class PurgedWalkForwardSpecV1:
    label_horizon_sessions: int = 1
    purge_sessions: int = 10
    embargo_sessions: int = 0
    folds: tuple[dict[str, str], ...] = (
        {"fold_id": "fold_1", "train_start": "2019-01-02", "train_end": "2020-12-31",
         "test_start": "2021-01-04", "test_end": "2021-12-31"},
        {"fold_id": "fold_2", "train_start": "2019-01-02", "train_end": "2021-12-31",
         "test_start": "2022-01-04", "test_end": "2022-12-30"},
        {"fold_id": "fold_3", "train_start": "2019-01-02", "train_end": "2022-12-30",
         "test_start": "2023-01-03", "test_end": "2023-12-29"},
        {"fold_id": "fold_4", "train_start": "2019-01-02", "train_end": "2023-12-29",
         "test_start": "2024-01-02", "test_end": "2024-12-31"},
    )

    def payload(self) -> dict[str, Any]:
        if self.purge_sessions < max(self.label_horizon_sessions, 10):
            raise ValueError("walk-forward purge is below the frozen minimum")
        stable = asdict(self) | {
            "schema_version": "purged-walk-forward-spec-v1",
            "provider_id": "tushare-pro-v1",
            "outer_test_used_for_training": False,
            "outer_test_used_for_preprocessing_fit": False,
            "outer_test_used_for_feature_selection": False,
            "promotion_writes": 0,
        }
        return stable | {"walk_forward_spec_id": "pwfs1_" + hash_payload(stable)}


@dataclass(frozen=True)
class ModelFoldResultV1:
    model_spec_id: str
    bundle_id: str
    walk_forward_spec_id: str
    fold_id: str
    train_range: tuple[str, str]
    test_range: tuple[str, str]
    selected_features: tuple[str, ...]
    metrics: dict[str, Any]

    def payload(self) -> dict[str, Any]:
        stable = asdict(self) | {
            "schema_version": "model-fold-result-v1",
            "provider_id": "tushare-pro-v1",
            "outer_test_used_for_selection": False,
            "promotion_writes": 0,
        }
        return stable | {"fold_result_id": "mfr1_" + hash_payload(stable)}


@dataclass(frozen=True)
class ModelStabilityAssessmentV1:
    model_spec_id: str
    bundle_id: str
    fold_result_ids: tuple[str, ...]
    feature_importance: dict[str, Any]
    seed_stability: dict[str, Any]
    fold_stability: dict[str, Any]
    concentration_gate: dict[str, Any]

    def payload(self) -> dict[str, Any]:
        stable = asdict(self) | {
            "schema_version": "model-stability-assessment-v1",
            "provider_id": "tushare-pro-v1",
            "shap_used": False,
            "promotion_writes": 0,
        }
        return stable | {"stability_assessment_id": "msa1_" + hash_payload(stable)}


@dataclass(frozen=True)
class RetrospectiveModelCandidateV1:
    candidate_id: str
    bundle_id: str
    model_spec_id: str
    walk_forward_spec_id: str
    label_id: str
    feature_catalog_id: str
    fold_model_ids: tuple[str, ...]
    seed_model_ids: tuple[str, ...]
    prediction_artifact_ids: tuple[str, ...]
    strategy_result_ids: tuple[str, ...]
    annual_metrics: tuple[dict[str, Any], ...]
    statistical_test: dict[str, Any]
    model_stability: dict[str, Any]
    search_exposure: dict[str, Any]
    project_contamination_ledger_id: str
    historical_data_max: str = "2024-12-31"

    def payload(self) -> dict[str, Any]:
        stable = asdict(self) | {
            "schema_version": "retrospective-model-candidate-v1",
            "provider_id": "tushare-pro-v1",
            "status": "retrospective_model_candidate",
            "worth_fresh_observation": True,
            "registry_write": False,
            "promotion_writes": 0,
        }
        expected = "rmc1_" + hash_payload({key: value for key, value in stable.items() if key != "candidate_id"})
        if self.candidate_id != expected:
            raise ValueError("retrospective model Candidate identity mismatch")
        return stable
