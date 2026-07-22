from __future__ import annotations

from dataclasses import dataclass

from backend.services.engine.momentum_factor_iteration.protocol import FORMAL_STRATEGY


TASK_ID = "QM2-R1-007"
DATASET_KIND = "momentum_feature_matrix_v1"
SOURCE_CATALOG_ID = "mfc1_51dc0901c6d01ce07eec6228f881d49bb57ade13c8b6a7adb85bf14ae633b47c"
SOURCE_DATASET_ID = "mfd1_9bb7172510693b69deaedf0d211bce79dcad8a0178a34d70a4a01f654c08db2c"
GOVERNANCE_DECISION_ID = "ogd1_7de0ba81247dc226aa305c42f2e893225a0906cfae0d30f881b3c7d5f911f7f5"

DEVELOPMENT_PERIOD = ("2019-01-02", "2020-12-31")
ANNUAL_PERIODS = {
    "2021": ("2021-01-04", "2021-12-31"),
    "2022": ("2022-01-04", "2022-12-30"),
    "2023": ("2023-01-03", "2023-12-29"),
    "2024": ("2024-01-02", "2024-12-31"),
}
REPORT_PERIODS = {
    "2025": ("2025-01-02", "2025-12-30"),
    "2026H1": ("2026-01-05", "2026-06-23"),
}

ROUND_THEMES = {
    1: "multi_horizon_consensus",
    2: "momentum_persistence_and_path_quality",
    3: "momentum_surprise_and_acceleration",
    4: "pullback_continuation_and_breakout_semantics",
    5: "residual_relative_strength_and_beta_reduction",
    6: "failure_driven_simple_hybrid",
}

ROUND_FEATURES = {
    1: ("momentum_20_5", "momentum_60_10", "momentum_120_20", "return_20d", "return_60d", "return_120d"),
    2: ("momentum_20_5", "momentum_60_10", "momentum_120_20", "momentum_efficiency_20", "momentum_efficiency_60", "positive_day_ratio_20", "positive_day_ratio_60", "trend_slope_quality_20", "trend_slope_quality_60"),
    3: ("momentum_20_5", "momentum_60_10", "return_20d", "return_60d", "momentum_acceleration_5_20", "momentum_acceleration_10_40", "momentum_acceleration_20_60"),
    4: ("momentum_60_10", "momentum_120_20", "distance_to_high_20", "distance_to_high_60", "breakout_strength_60", "momentum_efficiency_60"),
    5: ("momentum_60_10", "momentum_120_20", "relative_momentum_20", "relative_momentum_60", "relative_momentum_120", "residual_momentum_20", "residual_momentum_60", "residual_momentum_120"),
    6: ("momentum_20_5", "momentum_60_10", "momentum_120_20", "momentum_efficiency_60", "positive_day_ratio_60", "momentum_acceleration_20_60", "distance_to_high_60", "residual_momentum_60", "amount_confirmed_momentum_60"),
}

DEFAULT_GATE = {
    "minimum_mean_rank_ic": 0.0,
    "minimum_rank_ic_positive_rate": 0.50,
    "minimum_finite_coverage": 0.90,
    "maximum_turnover": 45.0,
    "maximum_infinity_count": 0,
    "maximum_pit_violations": 0,
}
NEAR_GATE = {"minimum_mean_rank_ic": -0.002, "minimum_rank_ic_positive_rate": 0.45}
ELIGIBILITY = {
    "complete_years": 4, "minimum_coverage": 0.90, "maximum_infinity_count": 0,
    "maximum_pit_violations": 0, "minimum_positive_rankic_years": 3,
    "minimum_median_rankic": 0.003, "minimum_worst_rankic": -0.008,
    "minimum_positive_excess_years": 3, "minimum_median_excess": 0.0,
    "minimum_worst_excess": -0.10, "maximum_median_turnover": 40.0,
    "maximum_median_best10_contribution": 0.35, "maximum_old_factor_correlation": 0.85,
}

OPERATORS = ("add", "subtract", "multiply", "divide", "negate", "absolute", "delta",
             "rolling_mean", "rolling_std", "rolling_min", "rolling_max", "cs_rank", "cs_zscore")
LIFECYCLE_POLICY = {
    "policy_id": "fulp_60672b83e8fc37c84e0eb749162845d246b2fa3365d9d4740d1fe183a6a632a",
    "locked_member_count": 100, "minimum_observable_instruments": 25,
}


@dataclass(frozen=True)
class Budget:
    rounds: int = 6
    max_agent_calls_per_round: int = 1
    max_proposals_per_round: int = 3
    max_admitted_templates_per_round: int = 2
    max_repair_attempts_per_call: int = 1
    max_total_agent_calls: int = 6
    max_total_templates: int = 12
    max_parameters_per_template: int = 2
    max_local_trials_per_template: int = 7


BUDGET = Budget()


COMPLETENESS_REQUIRED = {
    "default_parameter_evaluation": ("factor_template_id", "agent_default_parameters", "development_period", "metrics", "qlib", "default_candidate_passed", "local_rescue_eligible"),
    "local_factor_rescue_study": ("factor_template_id", "agent_default_parameters", "parameter_neighborhood", "trial_count", "trials", "selected_parameters", "optimization_rescued"),
    "development_parameter_lock": ("factor_template_id", "factor_instance_id", "agent_default_parameters", "selected_parameters", "optimization_mode", "optimization_rescued", "development_metrics", "orientation"),
    "default_first_momentum_annual_evaluation": ("development_lock_id", "year", "selected_parameters", "metrics", "qlib", "regime_metrics"),
    "default_first_momentum_eligibility_evidence": ("development_lock_id", "annual_evaluation_ids", "annual_metrics", "gate_results", "gate_failure_reasons", "standalone_eligible"),
    "default_first_momentum_candidate_lock": ("factor_template_id", "factor_instance_id", "template_name", "momentum_family", "canonical_dsl", "canonical_ast", "input_features", "agent_default_parameters", "selected_parameters", "optimization_mode", "optimization_rescued", "development_metrics", "annual_2021_2024_metrics", "orientation", "factor_value_artifact_id", "unified_signal_id", "turnover", "cost", "concentration", "old_factor_correlations", "structural_fingerprint", "economic_hypothesis", "status"),
    "default_first_momentum_report": ("candidate_lock_id", "period", "date_range", "metrics", "qlib", "regime_metrics", "not_used_for_selection", "not_fresh_validation"),
    "default_first_momentum_assessment": ("round_results", "default_passed_candidates", "optimization_rescued_candidates", "candidate_lock_ids", "comparison", "questions", "execution_counts"),
    "default_first_momentum_experiment": ("task_id", "spec_id", "governance_decision_id", "catalog_id", "feature_dataset_id", "artifact_ids", "candidate_lock_ids", "report_ids", "assessment_id", "execution_counts"),
}


__all__ = ["ANNUAL_PERIODS", "BUDGET", "COMPLETENESS_REQUIRED", "DATASET_KIND", "DEFAULT_GATE",
           "DEVELOPMENT_PERIOD", "ELIGIBILITY", "FORMAL_STRATEGY", "GOVERNANCE_DECISION_ID",
           "LIFECYCLE_POLICY", "NEAR_GATE", "OPERATORS", "REPORT_PERIODS", "ROUND_FEATURES",
           "ROUND_THEMES", "SOURCE_CATALOG_ID", "SOURCE_DATASET_ID", "TASK_ID"]
