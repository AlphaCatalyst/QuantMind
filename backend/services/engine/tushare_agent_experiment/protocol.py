from __future__ import annotations

from dataclasses import asdict, dataclass

from backend.services.engine.tushare_cutover.canonical import hash_payload


@dataclass(frozen=True)
class RoundWindow:
    round_number: int
    research_start: str
    research_end: str
    evaluation_start: str
    evaluation_end: str
    evaluation_year: str


ROUNDS = (
    RoundWindow(1, "2019-01-02", "2020-12-31", "2021-01-04", "2021-12-31", "2021"),
    RoundWindow(2, "2019-01-02", "2021-12-31", "2022-01-04", "2022-12-30", "2022"),
    RoundWindow(3, "2019-01-02", "2022-12-30", "2023-01-03", "2023-12-29", "2023"),
    RoundWindow(4, "2019-01-02", "2023-12-29", "2024-01-02", "2024-12-31", "2024"),
)

BUDGET = {
    "max_agent_calls": 2,
    "max_proposals": 3,
    "max_admitted_templates": 2,
    "max_trials_per_template": 6,
    "max_total_trials": 12,
    "max_repair_attempts": 1,
}

FEATURES = (
    "mom_ret_1d",
    "liq_volume_ratio_5",
    "style_beta_20",
    "style_idio_vol_20",
)

OPERATORS = (
    "add",
    "subtract",
    "multiply",
    "divide",
    "negate",
    "absolute",
    "cs_rank",
    "cs_zscore",
    "rolling_mean",
    "rolling_std",
    "rolling_min",
    "rolling_max",
    "delta",
)


def fixed_protocol(authority: dict) -> dict:
    stable = {
        "schema_version": "tushare-fixed100-agent-experiment-protocol-v1",
        "runtime_revision": "qm2-p0-015-r2-compiled-template-public-field",
        "experiment_type": "retrospective_tushare_agent_iteration_diagnostic",
        "provider_id": "tushare-pro-v1",
        "runtime_mode": "store_required",
        "authority_record_id": authority["authority_record_id"],
        "universe_500_id": authority["universe_500"]["universe_lock_id"],
        "universe_100_id": authority["universe_100"]["universe_lock_id"],
        "feature_dataset_id": authority["feature_dataset_id"],
        "label_dataset_id": authority["label_dataset_id"],
        "qlib_view_id": authority["qlib_view_id"],
        "registry_genesis_id": authority["registry_genesis_id"],
        "sanitized_memory_id": authority["sanitized_memory_id"],
        "data_range": ["2019-01-02", "2026-06-23"],
        "warmup_start": "2018-09-01",
        "features": list(FEATURES),
        "rounds": [asdict(item) for item in ROUNDS],
        "budget_per_round": BUDGET,
        "total_budget": {"max_agent_calls": 8, "max_admitted_templates": 8, "max_trials": 48},
        "agent": {"provider": "openai_codex_cli", "model": "gpt-5.6-terra"},
        "parameter_selection": {
            "data": "research_window_only",
            "roles": ["lookback_window", "factor_internal_weight"],
            "orientation": "sign_of_research_mean_rank_ic",
            "structure_evolution": False,
        },
        "portfolio": {
            "engine": "QlibBacktestService",
            "strategy": "TopkDropout",
            "universe": "tushare_fixed_100",
            "topk": 20,
            "n_drop": 5,
            "weight": "equal",
            "rebalance": "weekly",
            "rebalance_days": 5,
            "benchmark": "CSI300",
            "secondary_benchmark": "fixed_100_equal_weight",
            "deal_price": "open",
            "signal_lag_days": 1,
            "exchange": "CnExchange",
            "account": 1_000_000.0,
        },
        "costs": {
            "commission_rate": 0.00025,
            "minimum_commission": 5.0,
            "stamp_duty_rate": 0.0005,
            "transfer_fee_rate": 0.00001,
            "minimum_transfer_fee": 0.01,
            "market_impact": 0.0005,
            "lot_size": 100,
        },
        "holdouts": {
            "2025": ["2025-01-02", "2025-12-30"],
            "2026H1": ["2026-01-05", "2026-06-23"],
        },
        "holdout_feedback": "forbidden",
        "promotion_authority": "none",
    }
    return stable | {"protocol_id": "thp_" + hash_payload(stable)}
