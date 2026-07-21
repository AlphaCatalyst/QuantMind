from __future__ import annotations

from dataclasses import dataclass


DATASET_KIND = "momentum_feature_matrix_v1"
TASK_ID = "QM2-R1-002"
PROTOCOL_VERSION = "momentum-factor-iteration-v1"

FOLDS = (
    {"fold": 1, "research": ("2019-01-01", "2020-12-31"), "evaluation": ("2021-01-01", "2021-12-31")},
    {"fold": 2, "research": ("2019-01-01", "2021-12-31"), "evaluation": ("2022-01-01", "2022-12-31")},
    {"fold": 3, "research": ("2019-01-01", "2022-12-31"), "evaluation": ("2023-01-01", "2023-12-31")},
    {"fold": 4, "research": ("2019-01-01", "2023-12-31"), "evaluation": ("2024-01-01", "2024-12-31")},
)

ROUND_THEMES = {
    1: ("absolute_momentum", "skip_recent_momentum"),
    2: ("relative_momentum", "residual_momentum"),
    3: ("path_quality",),
    4: ("risk_adjusted_momentum",),
    5: ("momentum_acceleration", "breakout", "amount_confirmation"),
    6: (
        "absolute_momentum", "skip_recent_momentum", "relative_momentum",
        "residual_momentum", "path_quality", "risk_adjusted_momentum",
        "momentum_acceleration", "breakout", "amount_confirmation",
    ),
}

ELIGIBILITY = {
    "valid_folds": 4,
    "minimum_coverage": 0.90,
    "maximum_infinite_values": 0,
    "maximum_pit_violations": 0,
    "minimum_positive_rankic_folds": 3,
    "minimum_median_rankic": 0.003,
    "minimum_worst_rankic": -0.008,
    "minimum_positive_excess_folds": 3,
    "minimum_median_excess": 0.0,
    "minimum_worst_excess": -0.10,
    "maximum_median_turnover": 40.0,
    "maximum_median_best10_contribution": 0.35,
    "minimum_parameter_neighborhood_stability": 0.50,
    "maximum_existing_factor_correlation": 0.85,
}


@dataclass(frozen=True)
class IterationBudget:
    rounds: int = 6
    max_agent_calls_per_round: int = 2
    max_proposals_per_round: int = 4
    max_admitted_templates_per_round: int = 3
    max_trials_per_template: int = 8
    max_trials_per_round: int = 24
    max_total_agent_calls: int = 12
    max_total_admitted_templates: int = 18
    max_total_trials: int = 144


BUDGET = IterationBudget()

FORMAL_STRATEGY = {
    "engine": "Qlib",
    "strategy": "TopKDropoutStrategy",
    "topk": 20,
    "n_drop": 5,
    "rebalance_frequency": 5,
    "weighting": "equal",
    "prediction_lag_sessions": 1,
    "deal_price": "open",
    "benchmark": "CSI300",
    "official": True,
}

STABLE_ORDER = (
    "valid_fold_count", "positive_rankic_fold_count", "median_rankic",
    "worst_rankic", "positive_excess_fold_count", "median_excess_return",
    "worst_excess_return", "parameter_neighborhood_stability",
    "regime_robustness", "max_existing_factor_correlation",
    "median_turnover", "median_best10_contribution", "structural_novelty",
    "candidate_id",
)
