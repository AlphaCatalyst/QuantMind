from __future__ import annotations

from backend.services.engine.research.schemas import (
    PromotionDecision,
    PromotionPolicy,
    QuantGPTCandidateMetrics,
)


def evaluate_promotion_eligibility(
    metrics: QuantGPTCandidateMetrics,
    *,
    policy: PromotionPolicy | None = None,
    max_existing_feature_corr: float | None = None,
) -> PromotionDecision:
    policy = policy or PromotionPolicy()
    reasons: list[str] = []

    if metrics.rank_ic_mean is None:
        reasons.append("missing_rank_ic_mean")
    elif abs(metrics.rank_ic_mean) < policy.min_abs_rank_ic:
        reasons.append("rank_ic_mean_below_threshold")

    if metrics.ic_ir is None:
        reasons.append("missing_ic_ir")
    elif metrics.ic_ir < policy.min_ic_ir:
        reasons.append("ic_ir_below_threshold")

    if metrics.turnover is None:
        reasons.append("missing_turnover")
    elif metrics.turnover > policy.max_turnover:
        reasons.append("turnover_above_threshold")

    if metrics.monotonicity_score is None:
        reasons.append("missing_monotonicity_score")
    elif metrics.monotonicity_score < policy.min_monotonicity_score:
        reasons.append("monotonicity_below_threshold")

    if metrics.anti_overfit_score is None:
        reasons.append("missing_anti_overfit_score")
    elif metrics.anti_overfit_score < policy.min_anti_overfit_score:
        reasons.append("anti_overfit_below_threshold")

    if metrics.coverage_days is None:
        reasons.append("missing_coverage_days")
    elif metrics.coverage_days < policy.min_coverage_days:
        reasons.append("coverage_days_below_threshold")

    if (
        max_existing_feature_corr is not None
        and max_existing_feature_corr > policy.max_existing_feature_corr
    ):
        reasons.append("existing_feature_correlation_above_threshold")

    return PromotionDecision(eligible=not reasons, reasons=reasons)
