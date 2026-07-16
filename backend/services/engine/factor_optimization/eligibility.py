def evaluate_eligibility(status, metrics, gate, lineage_valid=True):
    reasons = []
    if status not in {"succeeded", "replayed"}: reasons.append("execution_not_successful")
    if not lineage_valid: reasons.append("lineage_or_key_validation_failed")
    if metrics is None: reasons.append("metrics_unavailable")
    else:
        if metrics.infinity_count: reasons.append("infinity_present")
        if metrics.non_null_count <= 0: reasons.append("empty_output")
        if metrics.constant_output: reasons.append("constant_output")
        if metrics.finite_coverage < gate.minimum_finite_coverage: reasons.append("finite_coverage_below_gate")
        if metrics.median_daily_finite_symbols < gate.minimum_median_daily_finite_symbols: reasons.append("median_daily_finite_symbols_below_gate")
        if metrics.date_count < gate.minimum_date_count: reasons.append("date_count_below_gate")
        if metrics.symbol_count < gate.minimum_symbol_count: reasons.append("symbol_count_below_gate")
    return not reasons, tuple(reasons)


def validation_candidate_order(trials):
    eligible = [trial for trial in trials if trial.eligible_for_validation]
    eligible.sort(key=lambda trial: (-trial.metrics.finite_coverage,
                                     -trial.metrics.median_daily_finite_symbols,
                                     trial.metrics.null_count, trial.metrics.warmup_periods,
                                     trial.trial_id))
    return tuple(trial.trial_id for trial in eligible)
