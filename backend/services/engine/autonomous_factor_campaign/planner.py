from __future__ import annotations

from collections import Counter

from .models import ROUND_THEMES


THEME_FEATURES = {
    "multi_horizon_trend": ("momentum_20_5", "momentum_60_10", "momentum_120_20", "return_20d", "return_60d", "return_120d"),
    "path_quality": ("momentum_60_10", "momentum_120_20", "momentum_efficiency_20", "momentum_efficiency_60", "positive_day_ratio_20", "positive_day_ratio_60", "trend_slope_quality_20", "trend_slope_quality_60"),
    "momentum_acceleration": ("momentum_20_5", "momentum_60_10", "momentum_acceleration_5_20", "momentum_acceleration_10_40", "momentum_acceleration_20_60"),
    "pullback_continuation": ("momentum_60_10", "momentum_120_20", "distance_to_high_20", "distance_to_high_60", "breakout_strength_60"),
    "drawdown_recovery": ("momentum_60_10", "drawdown_20", "drawdown_60", "distance_to_high_20", "distance_to_high_60"),
    "residual_relative_strength": ("momentum_60_10", "momentum_120_20", "relative_momentum_20", "relative_momentum_60", "relative_momentum_120", "residual_momentum_20", "residual_momentum_60", "residual_momentum_120"),
    "volatility_conditioned_trend": ("momentum_60_10", "momentum_120_20", "volatility_20", "volatility_60", "style_idio_vol_20"),
    "volume_price_confirmation": ("momentum_20_5", "momentum_60_10", "volume_confirmed_momentum_20", "amount_confirmed_momentum_60", "liq_volume_ratio_5"),
    "liquidity_normalized_trend": ("momentum_60_10", "momentum_120_20", "liq_volume_ratio_5", "turnover_rate", "amount_ratio_20"),
    "cross_family_simple_hybrid": ("momentum_60_10", "momentum_120_20", "momentum_efficiency_60", "distance_to_high_60", "residual_momentum_60", "amount_confirmed_momentum_60"),
}


def plan_next_round(memory: dict, round_number: int) -> dict:
    attempted = Counter(memory.get("families_attempted", []))
    repeated = Counter(memory.get("repeated_failures", {}))
    frozen = set(memory.get("temporarily_frozen_families", []))
    preferred = []
    if repeated["high_turnover"]:
        preferred += ["path_quality", "multi_horizon_trend"]
    if repeated["weak_predictive_signal"]:
        preferred += ["drawdown_recovery", "residual_relative_strength"]
    if repeated["duplicate_signal"] or repeated["duplicate_structure"]:
        preferred += ["cross_family_simple_hybrid", "volume_price_confirmation"]
    if repeated["benchmark_only_exposure"]:
        preferred += ["residual_relative_strength"]
    if repeated["annual_instability"]:
        preferred += ["path_quality", "multi_horizon_trend"]
    candidates = preferred + list(ROUND_THEMES)
    theme = next((item for item in candidates if item not in frozen and attempted[item] < 3), None)
    if theme is None:
        return {"status": "search_space_exhausted", "round_number": round_number}
    return {
        "status": "planned", "round_number": round_number, "theme": theme,
        "allowed_features": list(THEME_FEATURES[theme]),
        "reason": "failure_memory_and_underexplored_family_priority",
        "uses_report_period_evidence": False, "uses_fresh_forward_evidence": False,
        "manual_planning": False,
    }


def early_stop_reason(memory: dict, budget_usage: dict, budget: dict) -> str | None:
    mapping = {
        "rounds": "maximum_rounds", "agent_calls": "maximum_agent_calls",
        "proposals": "maximum_proposals", "admitted_templates": "maximum_admitted_templates",
        "local_rescue_trials": "maximum_local_rescue_trials",
        "formal_qlib_calls": "maximum_formal_qlib_calls",
        "candidate_locks": "maximum_candidate_locks",
    }
    if any(budget_usage[key] >= budget[name] for key, name in mapping.items()):
        return "budget_exhausted"
    if budget_usage.get("eligible_candidates", 0) >= budget["maximum_candidate_locks"]:
        return "candidate_capacity_reached"
    if memory.get("consecutive_no_admission", 0) >= 3:
        return "novelty_exhausted"
    if memory.get("consecutive_no_development_improvement", 0) >= 4:
        return "development_improvement_exhausted"
    if memory.get("search_space_exhausted"):
        return "search_space_exhausted"
    return None
