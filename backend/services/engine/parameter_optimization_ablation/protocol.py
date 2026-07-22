from __future__ import annotations

TASK_ID = "QM2-R1-005"
SOURCE_EXPERIMENT_ID = "srme1_072b0d1a70762482c5fac657568a80b2b01de92e08442b29d1c60a6704d1ab3c"
CANDIDATE_A = "srmcl1_56201db3ca8a2b4ccd88be58abfddc127d4c077e16407c400a3f4312edd9f95b"
CANDIDATE_B = "srmcl1_4e0abd499038faf0ecc9f178b89712d7055790e91d3e391f41a0e338352c80b4"
ENSEMBLE_ID = "srmen1_7200c57baf718a80992e812e28de0241a479f443e5e64bb2581830fecbe25ab2"
SOURCE_ASSESSMENT_ID = "srma1_0bcef3268b1aac1e0d96fbd9fc73572e49f212e9bcafb9cd4337b8e6738f96a0"
DATASET_ID = "mfd1_9bb7172510693b69deaedf0d211bce79dcad8a0178a34d70a4a01f654c08db2c"

FOLDS = (
    {"fold": 1, "research": ("2019-01-02", "2020-12-31"), "evaluation": ("2021-01-04", "2021-12-31")},
    {"fold": 2, "research": ("2019-01-02", "2021-12-31"), "evaluation": ("2022-01-04", "2022-12-30")},
    {"fold": 3, "research": ("2019-01-02", "2022-12-30"), "evaluation": ("2023-01-03", "2023-12-29")},
    {"fold": 4, "research": ("2019-01-02", "2023-12-29"), "evaluation": ("2024-01-02", "2024-12-31")},
)
PERIODS = {
    "2019-2024": ("2019-01-02", "2024-12-31"),
    "2025": ("2025-01-02", "2025-12-31"),
    "2026H1": ("2026-01-05", "2026-06-23"),
}
YEAR_PERIODS = {
    "2019": ("2019-01-02", "2019-12-31"), "2020": ("2020-01-02", "2020-12-31"),
    "2021": ("2021-01-04", "2021-12-31"), "2022": ("2022-01-04", "2022-12-30"),
    "2023": ("2023-01-03", "2023-12-29"), "2024": ("2024-01-02", "2024-12-31"),
}

S0 = ((20, 5, 5),)
S1 = ((20, 5, 5), (10, 5, 5), (30, 5, 5), (20, 0, 5),
      (20, 10, 5), (20, 5, 1), (20, 5, 10))
S2 = tuple(
    (topk, n_drop, rebalance)
    for topk in (10, 20, 30)
    for n_drop in (0, 5, 10)
    for rebalance in (1, 5, 10)
    if n_drop < topk
)
STRATEGY_MODES = {"S0": S0, "S1": S1, "S2": S2}
FACTOR_MODES = ("F0", "F1", "F2")
COMBINED_MODES = {"O0": ("F0", "S0"), "O1": ("F1", "S1"), "O2": ("F2", "S2")}

ORDERING = (
    "positive_rankic_year_count", "median_rankic", "worst_rankic",
    "positive_csi300_excess_year_count", "median_csi300_excess",
    "worst_csi300_excess", "maximum_drawdown_abs", "turnover",
    "transaction_cost", "trial_id",
)
FORMAL_STRATEGY = {
    "topk": 20, "n_drop": 5, "rebalance_interval": 5,
    "weighting": "equal_weight", "signal_lag": 1,
    "execution_price": "open", "benchmark": "CSI300",
    "cost_contract": "CnExchange",
}

ARTIFACT_FILES = {
    "parameter_optimization_ablation_spec": (
        "spec.json", "input_candidates.json", "factor_modes.json", "strategy_modes.json",
    ),
    "factor_optimization_ablation": (
        "fold_results.parquet", "trial_metrics.parquet", "parameter_consistency.json",
        "plateau_analysis.json", "period_results.json",
    ),
    "strategy_optimization_ablation": (
        "fold_results.parquet", "trial_metrics.parquet", "parameter_consistency.json",
        "plateau_analysis.json", "period_results.json",
    ),
    "combined_optimization_ablation": (
        "fold_results.parquet", "trial_metrics.parquet", "parameter_consistency.json",
        "plateau_analysis.json", "period_results.json",
    ),
    "optimization_trial_rank_stability": (
        "trial_rank_stability.parquet", "parameter_consistency.json",
    ),
    "optimization_overfit_assessment": (
        "generalization_gap.json", "overfit_classification.json",
        "framework_decision.json", "search_intensity.json",
        "turnover_cost_analysis.json", "summary.json",
    ),
}

LIFECYCLE_POLICY = {
    "policy_id": "fulp_60672b83e8fc37c84e0eb749162845d246b2fa3365d9d4740d1fe183a6a632a",
    "locked_member_count": 100,
    "minimum_observable_instruments": 25,
}
