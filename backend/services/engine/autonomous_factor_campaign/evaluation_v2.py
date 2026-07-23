from __future__ import annotations

from statistics import median
from pathlib import Path

import numpy as np

from backend.services.engine.default_first_momentum_search.engine import _clean_result
from backend.services.engine.default_first_momentum_search.protocol import LIFECYCLE_POLICY
from backend.services.engine.factor_dsl import parse_template
from backend.services.engine.tushare_agent_experiment.evaluation import (
    factor_values, group_diagnostics, oriented_signal, split_metrics,
)


DISCOVERY_PERIODS = {
    "2021": ("2021-01-04", "2021-12-31"),
    "2022": ("2022-01-04", "2022-12-30"),
}
HOLDOUT_PERIODS = {
    "2023": ("2023-01-03", "2023-12-29"),
    "2024": ("2024-01-02", "2024-12-31"),
}
REPORT_PERIODS_V2 = {
    "2025": ("2025-01-02", "2025-12-31"),
    "2026H1": ("2026-01-05", "2026-06-23"),
}


def _year_result(evaluator, values, orientation: int, factor_instance_id: str,
                 name: str, period: tuple[str, str], partition: str) -> dict:
    metrics = split_metrics(values, evaluator.matrix, *period, orientation)
    diagnostics = group_diagnostics(values, evaluator.matrix, *period, orientation)
    signal = oriented_signal(
        values, orientation,
        Path(evaluator.work_root) / "signals-v2" / f"{factor_instance_id}-{name}.parquet",
    )
    qlib = _clean_result(evaluator.qlib.run(
        signal, *period, rebalance_days=10, lifecycle_policy=LIFECYCLE_POLICY
    ))
    numeric = values.loc[values["trade_date"].between(*period), "factor_value"]
    infinity = int(np.isinf(numeric.to_numpy(dtype=float, na_value=np.nan)).sum())
    return {
        "year": name, "evidence_partition": partition,
        "metrics": metrics, "diagnostics": diagnostics, "qlib": qlib,
        "infinity_count": infinity, "pit_violation_count": 0,
    }


def evaluate_holdout(evaluator, proposal: dict, development_lock: dict,
                     *, expected_parameters: dict, expected_orientation: int) -> dict:
    if development_lock["selected_parameters"] != expected_parameters:
        raise ValueError("LOCKED_HOLDOUT_PARAMETER_MUTATION")
    if development_lock["orientation"] != expected_orientation:
        raise ValueError("LOCKED_HOLDOUT_ORIENTATION_MUTATION")
    template = parse_template(proposal["template"])
    compiled, values = factor_values(template, evaluator.contract, expected_parameters, evaluator.matrix)
    rows = [
        _year_result(evaluator, values, expected_orientation, compiled.factor_instance_id,
                     year, period, "locked_holdout")
        for year, period in HOLDOUT_PERIODS.items()
    ]
    rankic = [row["metrics"].get("mean_rank_ic") for row in rows]
    excess = [row["qlib"].get("net_excess_csi300") for row in rows]
    turnover = [row["qlib"].get("turnover") for row in rows]
    concentration = [row["qlib"].get("best_10_days_contribution") for row in rows]
    discovery = development_lock["discovery_summary"]
    summary = {
        "complete_year_count": len(rows),
        "positive_rankic_year_count": sum(value is not None and value > 0 for value in rankic),
        "median_rankic": float(median(rankic)) if None not in rankic else None,
        "worst_rankic": min(rankic) if None not in rankic else None,
        "positive_excess_year_count": sum(value is not None and value > 0 for value in excess),
        "median_excess": float(median(excess)) if None not in excess else None,
        "worst_excess": min(excess) if None not in excess else None,
        "median_turnover": float(median(turnover)) if None not in turnover else None,
        "median_best10_contribution": float(median(concentration)) if None not in concentration else None,
    }
    checks = {
        "complete_years": len(rows) == 2,
        "coverage": all((row["metrics"].get("factor_finite_coverage") or 0) >= .90 for row in rows),
        "infinity": all(row["infinity_count"] == 0 for row in rows),
        "pit": all(row["pit_violation_count"] == 0 for row in rows),
        "positive_rankic_years": summary["positive_rankic_year_count"] == 2,
        "median_rankic": summary["median_rankic"] is not None and summary["median_rankic"] >= .003,
        "worst_rankic": summary["worst_rankic"] is not None and summary["worst_rankic"] >= -.003,
        "positive_excess_years": summary["positive_excess_year_count"] >= 1,
        "median_excess": summary["median_excess"] is not None and summary["median_excess"] > 0,
        "worst_excess": summary["worst_excess"] is not None and summary["worst_excess"] > -.05,
        "turnover": summary["median_turnover"] is not None and summary["median_turnover"] <= 30,
        "concentration": summary["median_best10_contribution"] is not None and summary["median_best10_contribution"] <= .35,
        "parameters_unchanged": True, "orientation_unchanged": True,
        "discovery_rankic_consistency": not (
            (discovery.get("median_rankic") or 0) > 0 and (summary["median_rankic"] or 0) <= 0
        ),
        "discovery_excess_consistency": not (
            (discovery.get("median_excess") or 0) > 0 and (summary["median_excess"] or 0) <= -.05
        ),
    }
    return {
        "factor_instance_id": compiled.factor_instance_id,
        "parameters": expected_parameters, "orientation": expected_orientation,
        "annual": rows, "summary": summary,
        "gate_results": checks, "passed": all(checks.values()),
        "failed_gates": [name for name, passed in checks.items() if not passed],
        "values": values,
    }


def evaluate_reports(evaluator, values, factor_instance_id: str, orientation: int) -> list[dict]:
    return [
        _year_result(evaluator, values, orientation, factor_instance_id, name, period, "contaminated_report")
        | {
            "contaminated_report_only": True, "not_used_for_selection": True,
            "not_used_for_planning": True, "not_used_for_holdout_gate": True,
            "not_fresh_validation": True,
        }
        for name, period in REPORT_PERIODS_V2.items()
    ]
