from __future__ import annotations

from dataclasses import asdict, dataclass

from backend.services.engine.tushare_cutover.canonical import hash_payload


@dataclass(frozen=True)
class Fold:
    number: int
    research_start: str
    research_end: str
    evaluation_start: str
    evaluation_end: str
    evaluation_year: str


FOLDS = (
    Fold(1, "2019-01-02", "2020-12-31", "2021-01-04", "2021-12-31", "2021"),
    Fold(2, "2019-01-02", "2021-12-31", "2022-01-04", "2022-12-30", "2022"),
    Fold(3, "2019-01-02", "2022-12-30", "2023-01-03", "2023-12-29", "2023"),
    Fold(4, "2019-01-02", "2023-12-29", "2024-01-02", "2024-12-31", "2024"),
)

BUDGET = {
    "max_rounds": 6,
    "max_agent_calls_per_round": 2,
    "max_proposals_per_round": 3,
    "max_admitted_templates_per_round": 2,
    "max_trials_per_template": 8,
    "max_trials_per_round": 16,
    "max_repair_attempts": 1,
    "max_agent_calls": 12,
    "max_admitted_templates": 12,
    "max_trials": 96,
}

OPERATORS = (
    "add", "subtract", "multiply", "divide", "negate", "absolute",
    "clip", "lag", "delta", "rolling_mean", "rolling_std",
    "rolling_min", "rolling_max", "cs_rank", "cs_zscore",
)


def fixed_protocol(authority: dict, feature_dataset_id: str, feature_names: tuple[str, ...]) -> dict:
    stable = {
        "schema_version": "expanded-feature-agent-factor-iteration-v2",
        "experiment_type": "retrospective_adaptive_factor_research",
        "provider_id": "tushare-pro-v1",
        "runtime_mode": "store_required",
        "authority_record_id": authority["authority_record_id"],
        "universe_500_id": authority["universe_500"]["universe_lock_id"],
        "universe_100_id": authority["universe_100"]["universe_lock_id"],
        "source_normalized_bars_id": authority["normalized_bars_id"],
        "feature_dataset_v2_id": feature_dataset_id,
        "label_dataset_id": authority["label_dataset_id"],
        "qlib_view_id": authority["qlib_view_id"],
        "feature_names": list(feature_names),
        "folds": [asdict(item) for item in FOLDS],
        "budget": BUDGET,
        "agent": {"provider": "openai_codex_cli", "model": "gpt-5.6-terra"},
        "selection_period": ["2019-01-02", "2024-12-31"],
        "report_only_periods": {
            "2025": ["2025-01-02", "2025-12-30"],
            "2026H1": ["2026-01-05", "2026-06-23"],
        },
        "strategy": {
            "engine": "QlibBacktestService",
            "chain": ["QlibBacktestService", "RedisRecordingStrategy", "SimulatorExecutor", "CnExchange"],
            "universe": "tushare_fixed_100",
            "topk": 20,
            "n_drop": 5,
            "rebalance_trade_dates": 5,
            "weighting": "equal_weight",
            "signal_lag_trade_dates": 1,
            "execution_price": "open",
            "benchmark": "CSI300",
        },
        "fixed_100_benchmark": {
            "canonicality": "noncanonical",
            "usable_for_selection": False,
            "usable_for_agent_feedback": False,
        },
        "predictive_claim": False,
        "usable_for_promotion": False,
        "eligible_for_production": False,
    }
    return stable | {"protocol_id": "afp2_" + hash_payload(stable)}
