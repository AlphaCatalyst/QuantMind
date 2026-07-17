from .enums import RegistryStatus


def promotion_gate(validation_metrics, frozen_metrics, policy):
    reasons = []
    checks = (
        (frozen_metrics["date_count_valid"] >= policy.minimum_frozen_valid_dates, "frozen_valid_dates_below_policy"),
        (frozen_metrics["median_daily_observations"] >= policy.minimum_frozen_median_daily_observations, "frozen_median_observations_below_policy"),
        (frozen_metrics["mean_rank_ic"] >= policy.minimum_oriented_frozen_mean_rank_ic, "frozen_mean_rank_ic_below_policy"),
        (frozen_metrics["rank_icir"] >= policy.minimum_oriented_frozen_rank_icir, "frozen_rank_icir_below_policy"),
        (frozen_metrics["rank_ic_positive_rate"] >= policy.minimum_oriented_frozen_rank_ic_positive_rate, "frozen_positive_rate_below_policy"),
        ((validation_metrics["mean_rank_ic"] > 0) == (frozen_metrics["mean_rank_ic"] > 0), "validation_frozen_sign_mismatch"),
    )
    for passed, reason in checks:
        if not passed:
            reasons.append(reason)
    return not reasons, tuple(reasons)


def derive_status(*, has_validation, validation_passed, selected, frozen_metrics, validation_metrics, policy, invalidated=False):
    if invalidated:
        return RegistryStatus.INVALIDATED, ("evidence_invalidated",)
    if not has_validation:
        return RegistryStatus.RESEARCH_REGISTERED, ("validation_evidence_absent",)
    if not validation_passed:
        return RegistryStatus.VALIDATION_REJECTED, ("validation_gate_failed",)
    if not selected:
        return RegistryStatus.VALIDATION_PASSED_NOT_SELECTED, ("not_in_immutable_frozen_selection",)
    if frozen_metrics is None:
        return RegistryStatus.RESEARCH_REGISTERED, ("selected_frozen_evidence_absent",)
    passed, reasons = promotion_gate(validation_metrics, frozen_metrics, policy)
    if passed:
        return RegistryStatus.PROMOTION_CANDIDATE, ("all_machine_promotion_gates_passed",)
    return RegistryStatus.FROZEN_REJECTED, reasons
