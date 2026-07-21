from __future__ import annotations

from dataclasses import dataclass

from backend.services.engine.momentum_factor_iteration.protocol import ELIGIBILITY, FOLDS, FORMAL_STRATEGY


TASK_ID = "QM2-R1-003"
DATASET_KIND = "momentum_feature_matrix_v1"
SOURCE_EXPERIMENT_ID = "mfi1_87177b7c06420e65159d3f5bdafee8149cdb3290c32f08712cd73e59a4e19dee"
SOURCE_CATALOG_ID = "mfc1_51dc0901c6d01ce07eec6228f881d49bb57ade13c8b6a7adb85bf14ae633b47c"
SOURCE_DATASET_ID = "mfd1_9bb7172510693b69deaedf0d211bce79dcad8a0178a34d70a4a01f654c08db2c"
UNRECOVERABLE_FACTOR_ID = "fi_167187d1947cc577474aa1a36333cf2a128c15d8e79242b0c9ad3307670e332a"

SUBFAMILIES = {
    1: "classic_skip_recent",
    2: "multi_horizon_consensus",
    3: "path_quality_skip_recent",
    4: "relative_residual_skip_recent",
    5: "risk_adjusted_skip_recent",
    6: "failure_driven_hybrid",
}

FEATURES = {
    1: ("momentum_20_5", "momentum_60_5", "momentum_60_10", "momentum_120_20"),
    2: ("momentum_20_5", "momentum_60_10", "momentum_120_20"),
    3: ("momentum_60_10", "momentum_120_20", "momentum_efficiency_20", "momentum_efficiency_60", "positive_day_ratio_20", "positive_day_ratio_60", "trend_slope_quality_20", "trend_slope_quality_60"),
    4: ("momentum_60_10", "momentum_120_20", "relative_momentum_20", "relative_momentum_60", "relative_momentum_120", "residual_momentum_20", "residual_momentum_60", "residual_momentum_120"),
    5: ("momentum_60_10", "momentum_120_20", "vol_adjusted_momentum_20", "vol_adjusted_momentum_60", "downside_adjusted_momentum_20", "downside_adjusted_momentum_60", "idio_adjusted_momentum_20", "idio_adjusted_momentum_60"),
    6: ("momentum_20_5", "momentum_60_10", "momentum_120_20", "momentum_efficiency_60", "relative_momentum_60", "residual_momentum_60", "downside_adjusted_momentum_60", "distance_to_high_60", "amount_confirmed_momentum_60"),
}


@dataclass(frozen=True)
class Budget:
    rounds: int = 6
    max_agent_calls_per_round: int = 2
    max_proposals_per_round: int = 4
    max_admitted_templates_per_round: int = 3
    max_trials_per_template: int = 8
    max_trials_per_round: int = 24
    max_total_agent_calls: int = 12
    max_total_templates: int = 18
    max_total_trials: int = 144


BUDGET = Budget()
REPORT_PERIODS = {
    "2025": ("2025-01-02", "2025-12-31"),
    "2026H1": ("2026-01-05", "2026-06-23"),
}

COMPLETENESS_REQUIRED = {
    "research_agent_raw_response": ("agent_call_id", "provider", "model", "prompt_hash", "raw_response_blob_id", "raw_response_hash", "research_decision_id"),
    "research_proposal": ("research_decision_id", "proposal_id", "proposal_payload", "rationale"),
    "factor_template_definition": ("factor_template_id", "template_name", "canonical_dsl", "canonical_ast", "input_features", "parameter_schema", "orientation_policy", "structural_fingerprint", "economic_hypothesis", "source_proposal_id"),
    "factor_optimization_trial_detail": ("trial_id", "factor_template_id", "research_fold", "parameters", "factor_instance_id", "factor_value_artifact_id", "trial_metrics", "failure_reason", "selected"),
    "factor_fold_candidate_lock": ("fold_id", "research_period", "evaluation_period", "selected_trial_id", "selected_parameters", "factor_instance_id", "factor_value_artifact_id", "orientation", "unified_signal_id", "selection_metrics"),
    "factor_candidate_eligibility_evidence": ("four_fold_metrics", "parameter_neighborhood_results", "turnover", "transaction_cost", "best_10_days_contribution", "return_without_best_10_days", "old_factor_correlations", "regime_metrics", "gate_results", "gate_failure_reasons"),
}

__all__ = ["BUDGET", "COMPLETENESS_REQUIRED", "DATASET_KIND", "ELIGIBILITY", "FEATURES", "FOLDS", "FORMAL_STRATEGY", "REPORT_PERIODS", "SOURCE_CATALOG_ID", "SOURCE_DATASET_ID", "SOURCE_EXPERIMENT_ID", "SUBFAMILIES", "TASK_ID", "UNRECOVERABLE_FACTOR_ID"]
