from __future__ import annotations


TASK_ID = "QM2-R1-008"
SOURCE_CATALOG_ID = "mfc1_51dc0901c6d01ce07eec6228f881d49bb57ade13c8b6a7adb85bf14ae633b47c"
SOURCE_DATASET_ID = "mfd1_9bb7172510693b69deaedf0d211bce79dcad8a0178a34d70a4a01f654c08db2c"
GOVERNANCE_DECISION_ID = "ogd1_7de0ba81247dc226aa305c42f2e893225a0906cfae0d30f881b3c7d5f911f7f5"
LIFECYCLE_POLICY = {
    "policy_id": "fulp_60672b83e8fc37c84e0eb749162845d246b2fa3365d9d4740d1fe183a6a632a",
    "locked_member_count": 100,
    "minimum_observable_instruments": 25,
}

ANNUAL_PERIODS = {
    "2021": ("2021-01-04", "2021-12-31"),
    "2022": ("2022-01-04", "2022-12-30"),
    "2023": ("2023-01-03", "2023-12-29"),
    "2024": ("2024-01-02", "2024-12-31"),
}
FULL_PERIOD = ("2021-01-04", "2024-12-31")
REPORT_PERIODS = {
    "2025": ("2025-01-02", "2025-12-30"),
    "2026H1": ("2026-01-05", "2026-06-23"),
}
QUALITY_PERIOD = ("2019-01-02", "2026-06-23")

SIGNALS = {
    "classic_long_term_skip_recent": {
        "economic_hypothesis": "Long-term trend excluding the most recent 20 sessions reduces reversal and chase noise.",
        "canonical_formula": "cs_rank(momentum_120_20)",
        "canonical_ast": {"type": "cs_rank", "input": {"type": "feature", "name": "momentum_120_20"}},
        "input_features": ("momentum_120_20",),
        "fixed_weights": {},
    },
    "dual_horizon_skip_recent_consensus": {
        "economic_hypothesis": "Medium and long relative strength must agree instead of relying on one accidental horizon.",
        "canonical_formula": "0.5*cs_zscore(momentum_60_10)+0.5*cs_zscore(momentum_120_20)",
        "canonical_ast": {"type": "add", "left": {"type": "multiply", "left": 0.5, "right": {"type": "cs_zscore", "input": {"type": "feature", "name": "momentum_60_10"}}}, "right": {"type": "multiply", "left": 0.5, "right": {"type": "cs_zscore", "input": {"type": "feature", "name": "momentum_120_20"}}}},
        "input_features": ("momentum_60_10", "momentum_120_20"),
        "fixed_weights": {"momentum_60_10": 0.5, "momentum_120_20": 0.5},
    },
    "path_quality_long_term_momentum": {
        "economic_hypothesis": "Long-term trend combined with signed path efficiency reduces dependence on isolated price impulses.",
        "canonical_formula": "0.5*cs_zscore(momentum_120_20)+0.5*cs_zscore(momentum_efficiency_60)",
        "canonical_ast": {"type": "add", "left": {"type": "multiply", "left": 0.5, "right": {"type": "cs_zscore", "input": {"type": "feature", "name": "momentum_120_20"}}}, "right": {"type": "multiply", "left": 0.5, "right": {"type": "cs_zscore", "input": {"type": "feature", "name": "momentum_efficiency_60"}}}},
        "input_features": ("momentum_120_20", "momentum_efficiency_60"),
        "fixed_weights": {"momentum_120_20": 0.5, "momentum_efficiency_60": 0.5},
    },
    "residual_absolute_momentum_consensus": {
        "economic_hypothesis": "Absolute and beta-residual trend must agree, reducing momentum explained only by CSI300 exposure.",
        "canonical_formula": "0.5*cs_zscore(momentum_120_20)+0.5*cs_zscore(residual_momentum_60)",
        "canonical_ast": {"type": "add", "left": {"type": "multiply", "left": 0.5, "right": {"type": "cs_zscore", "input": {"type": "feature", "name": "momentum_120_20"}}}, "right": {"type": "multiply", "left": 0.5, "right": {"type": "cs_zscore", "input": {"type": "feature", "name": "residual_momentum_60"}}}},
        "input_features": ("momentum_120_20", "residual_momentum_60"),
        "fixed_weights": {"momentum_120_20": 0.5, "residual_momentum_60": 0.5},
    },
}

PROTOCOLS = {
    "B0": {"topk": 20, "n_drop": 5, "rebalance_interval": 5, "weighting": "equal_weight", "signal_lag": 1, "execution_price": "open", "benchmark": "CSI300"},
    "L1": {"topk": 20, "n_drop": 5, "rebalance_interval": 10, "weighting": "equal_weight", "signal_lag": 1, "execution_price": "open", "benchmark": "CSI300"},
}

ELIGIBILITY = {
    "complete_years": 4,
    "minimum_coverage": 0.90,
    "minimum_positive_rankic_years": 3,
    "minimum_median_rankic": 0.003,
    "minimum_worst_rankic": -0.008,
    "minimum_positive_excess_years": 3,
    "minimum_median_excess": 0.0,
    "minimum_worst_excess": -0.10,
    "maximum_median_turnover": 30.0,
    "minimum_turnover_reduction": 0.30,
    "minimum_cost_reduction": 0.25,
    "maximum_best10_contribution": 0.35,
    "maximum_existing_factor_correlation": 0.85,
}

COMPLETENESS_REQUIRED = {
    "low_frequency_momentum_signal_spec": ("signal_spec_id", "name", "economic_hypothesis", "canonical_formula", "canonical_ast", "input_feature_ids", "fixed_weights", "orientation", "universe_id", "dataset_id", "date_range", "missing_policy", "signal_lag", "structural_fingerprint"),
    "low_frequency_execution_protocol": ("baseline_protocol", "low_frequency_protocol", "comparison_only_baseline", "candidate_protocol", "strategy_optimization_allowed"),
    "low_frequency_momentum_annual_result": ("signal_spec_id", "protocol_id", "year", "date_range", "metrics", "quality", "holding_metrics"),
    "low_frequency_momentum_candidate_lock": ("signal_spec_id", "signal_artifact_id", "economic_hypothesis", "canonical_formula", "input_features", "fixed_weights", "protocol_id", "annual_2021_2024_metrics", "full_period_metrics", "baseline_comparison", "turnover_reduction", "cost_reduction", "concentration", "existing_factor_correlations", "eligibility_evidence", "status"),
    "low_frequency_momentum_report": ("candidate_lock_id", "period", "date_range", "protocol_results", "not_used_for_selection", "not_fresh_validation"),
    "low_frequency_momentum_assessment": ("study_id", "signal_results", "candidate_lock_ids", "classification", "questions", "execution_counts"),
    "low_frequency_momentum_study": ("task_id", "spec_id", "signal_spec_ids", "protocol_id", "annual_result_ids", "candidate_lock_ids", "report_ids", "assessment_id", "execution_counts"),
}
