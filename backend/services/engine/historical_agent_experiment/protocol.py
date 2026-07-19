from __future__ import annotations

from dataclasses import asdict, dataclass

from .canonical import hash_payload


@dataclass(frozen=True)
class RoundWindow:
    round_number: int
    research_start: str
    research_end: str
    evaluation_start: str
    evaluation_end: str
    evaluation_label: str


ROUNDS = (
    RoundWindow(1, "2019-01-02", "2020-12-31", "2021-01-04", "2021-12-31", "2021"),
    RoundWindow(2, "2019-01-02", "2021-12-31", "2022-01-04", "2022-12-30", "2022"),
    RoundWindow(3, "2019-01-02", "2022-12-30", "2023-01-03", "2023-12-29", "2023"),
    RoundWindow(4, "2019-01-02", "2023-12-29", "2024-01-02", "2024-12-31", "2024"),
)

BUDGET = {
    "max_agent_calls": 2, "max_proposals": 3, "max_admitted_templates": 2,
    "max_trials_per_template": 6, "max_total_trials": 12, "max_repair_attempts": 1,
}


def fixed_protocol() -> dict:
    stable = {
        "schema_version": "fixed-universe-agent-experiment-protocol-v1",
        "experiment_type": "retrospective_agent_iteration_diagnostic",
        "data_range": ["2019-01-02", "2026-06-23"],
        "rounds": [asdict(item) for item in ROUNDS],
        "budget_per_round": BUDGET,
        "agent": {"provider": "openai_codex_cli", "model": "gpt-5.6-terra"},
        "parameter_selection": {
            "data": "research_window_only",
            "orientation": "sign_of_research_mean_rank_ic",
            "ordering": ["oriented_mean_rank_ic", "oriented_rank_icir", "finite_coverage", "trial_id"],
            "structure_evolution": False,
        },
        "portfolio": {
            "engine": "existing_qlib_backtest_service", "universe": "fixed_100",
            "topk": 20, "n_drop": 5, "weight": "equal", "rebalance": "weekly",
            "rebalance_days": 5, "deal_price": "open", "signal_lag_days": 1,
            "benchmark": "fixed_universe_equal_weight",
            "exchange": "CnExchange", "account": 1000000.0,
        },
        "costs": {
            "commission_rate": 0.00025, "min_commission": 5.0,
            "stamp_duty_rate": 0.0005, "transfer_fee_rate": 0.00001,
            "min_transfer_fee": 0.01, "market_impact": 0.0005,
            "limit_threshold": 0.095, "lot_size": 100,
        },
        "holdouts": [["2025-01-02", "2025-12-30"], ["2026-01-05", "2026-06-23"]],
        "holdout_feedback": "forbidden",
        "promotion_authority": "none",
    }
    return {**stable, "protocol_id": "haep_" + hash_payload(stable)}
