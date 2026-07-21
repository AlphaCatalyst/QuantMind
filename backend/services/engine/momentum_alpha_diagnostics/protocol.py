from __future__ import annotations

SOURCE_EXPERIMENT_ID = "srme1_072b0d1a70762482c5fac657568a80b2b01de92e08442b29d1c60a6704d1ab3c"
CANDIDATE_A = "srmcl1_56201db3ca8a2b4ccd88be58abfddc127d4c077e16407c400a3f4312edd9f95b"
CANDIDATE_B = "srmcl1_4e0abd499038faf0ecc9f178b89712d7055790e91d3e391f41a0e338352c80b4"
ENSEMBLE_ID = "srmen1_7200c57baf718a80992e812e28de0241a479f443e5e64bb2581830fecbe25ab2"

PERIODS = {
    "2019-2024": ("2019-01-02", "2024-12-31"),
    "2021": ("2021-01-04", "2021-12-31"),
    "2022": ("2022-01-04", "2022-12-30"),
    "2023": ("2023-01-03", "2023-12-29"),
    "2024": ("2024-01-02", "2024-12-31"),
    "2025": ("2025-01-02", "2025-12-31"),
    "2026H1": ("2026-01-05", "2026-06-23"),
}
QLIB_PERIODS = {key: PERIODS[key] for key in ("2019-2024", "2025", "2026H1")}
STYLE_COLUMNS = (
    "style_beta_20", "style_beta_60", "style_idio_vol_20",
    "style_idio_vol_60", "log_circ_mv", "amount_ratio_20",
    "volatility_20", "volatility_60", "distance_to_high_60",
)
ARTIFACT_FILES = {
    "momentum_semantic_audit": ("semantic_audit.json",),
    "momentum_cross_sectional_diagnostic": (
        "cross_sectional_metrics.parquet", "quantile_returns.parquet",
        "horizon_decay.json",
    ),
    "momentum_alpha_decomposition": (
        "beta_decomposition.parquet", "stock_contributions.parquet",
        "day_contributions.parquet", "cost_attribution.json",
        "regime_metrics.json", "correlations.json",
    ),
    "momentum_style_exposure_report": (
        "style_exposures.parquet", "holding_concentration.parquet",
    ),
    "momentum_failure_classification": (
        "failure_classification.json", "decision.json", "summary.json",
    ),
}

FORMAL_STRATEGY = {
    "topk": 20, "n_drop": 5, "rebalance_frequency": 5,
    "prediction_lag_sessions": 1, "deal_price": "open",
    "benchmark": "CSI300", "exchange": "CnExchange",
}
