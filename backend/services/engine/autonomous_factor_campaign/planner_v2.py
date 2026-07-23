from __future__ import annotations

from collections import Counter

from .planner import THEME_FEATURES


V2_PRIORITY = (
    "volume_price_confirmation", "volatility_conditioned_trend",
    "liquidity_normalized_trend", "pullback_continuation",
    "multi_horizon_trend", "cross_family_simple_hybrid",
    "path_quality", "drawdown_recovery", "residual_relative_strength",
    "momentum_acceleration",
)
V1_SATURATED = {"drawdown_recovery", "residual_relative_strength", "momentum_acceleration"}


def plan_next_round_v2(memory: dict, round_number: int) -> dict:
    attempted = Counter(memory.get("families_attempted", []))
    frozen = set(memory.get("temporarily_frozen_families", []))
    theme = next(
        (
            name for name in V2_PRIORITY
            if name not in frozen
            and attempted[name] < (1 if name in V1_SATURATED else 3)
            and attempted[name] < 3
        ),
        None,
    )
    if theme is None:
        return {"status": "search_space_exhausted", "round_number": round_number}
    return {
        "status": "planned", "round_number": round_number, "theme": theme,
        "allowed_features": list(THEME_FEATURES[theme]),
        "reason": "v2_underexplored_family_priority",
        "input_evidence_partitions": ["development", "adaptive_discovery"],
        "uses_locked_holdout_evidence": False,
        "uses_contaminated_report_evidence": False,
        "uses_fresh_forward_evidence": False,
        "manual_planning": False,
    }


def early_stop_reason_v2(memory: dict, usage: dict, budget: dict) -> str | None:
    bounds = {
        "rounds": "maximum_rounds", "agent_calls": "maximum_agent_calls",
        "proposals": "maximum_proposals", "admitted_templates": "maximum_admitted_templates",
        "local_rescue_trials": "maximum_local_rescue_trials",
        "discovery_qlib_calls": "maximum_discovery_qlib_calls",
    }
    if any(usage[name] >= budget[bound] for name, bound in bounds.items()):
        return "budget_exhausted"
    if memory.get("consecutive_no_admission", 0) >= 3:
        return "novelty_exhausted"
    if memory.get("consecutive_no_development_improvement", 0) >= 4:
        return "development_improvement_exhausted"
    return "search_space_exhausted" if memory.get("search_space_exhausted") else None
