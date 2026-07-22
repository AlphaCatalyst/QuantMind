from __future__ import annotations


TASK_ID = "QM2-R1-009"
COMPUTATION_REVISION = 3
SOURCE_STUDY_ID = "lfmsta1_18f3a4add9e0e224a7a8d35133af2dbfa9a23181edc94134d9c2c3738965ff80"
SOURCE_SIGNAL_NAME = "residual_absolute_momentum_consensus"
SOURCE_FORMULA = "0.5*cs_zscore(momentum_120_20)+0.5*cs_zscore(residual_momentum_60)"
PERIODS = {
    "2021": ("2021-01-04", "2021-12-31"),
    "2022": ("2022-01-04", "2022-12-30"),
    "2023": ("2023-01-03", "2023-12-29"),
    "2024": ("2024-01-02", "2024-12-31"),
    "2025": ("2025-01-02", "2025-12-30"),
    "2026H1": ("2026-01-05", "2026-06-23"),
}
RESEARCH_PERIODS = tuple(list(PERIODS)[:4])
REPORT_PERIODS = ("2025", "2026H1")
HORIZONS = (1, 5, 10)
DECAY_HORIZONS = (1, 5, 10, 20, 40)
TOP_NS = (5, 10, 20, 30)
STYLE_COLUMNS = (
    "log_circ_mv", "style_idio_vol_20", "style_idio_vol_60",
    "volatility_20", "volatility_60", "amount_ratio_20",
    "distance_to_high_60", "momentum_120_20", "residual_momentum_60",
)
CLASSIFICATIONS = (
    "broad_monotonic_factor", "tail_selection_overlay", "defensive_relative_factor",
    "regime_specific_factor", "no_reliable_alpha",
)
DECISIONS = (
    "build_momentum_selection_overlay", "retain_for_regime_specific_research",
    "stop_signal_d_research",
)

COMPLETENESS = {
    "momentum_quantile_return_report": ("source_signal_artifact_id", "periods", "horizons"),
    "momentum_rank_transition_report": ("source_signal_artifact_id", "rebalance_interval", "periods"),
    "momentum_tail_style_exposure": ("source_signal_artifact_id", "style_columns", "periods"),
    "momentum_tail_signal_classification": ("source_signal_artifact_id", "primary_classification", "secondary_labels", "research_decision"),
    "momentum_tail_alpha_diagnostic": ("task_id", "source_study_id", "source_signal_artifact_id", "artifact_ids", "classification_id", "execution_counts"),
}
