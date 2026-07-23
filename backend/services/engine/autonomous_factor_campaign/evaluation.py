from __future__ import annotations

from statistics import median
from typing import Any

import numpy as np
import pandas as pd
import shutil

from backend.services.engine.default_first_momentum_search.engine import (
    _clean_result,
    _development_gate,
    _selection_key,
    local_rescue_eligible,
)
from backend.services.engine.momentum_factor_iteration.engine import _existing_four
from backend.services.engine.default_first_momentum_search.protocol import (
    ANNUAL_PERIODS,
    DEVELOPMENT_PERIOD,
    LIFECYCLE_POLICY,
    REPORT_PERIODS,
)
from backend.services.engine.factor_dsl import parse_template
from backend.services.engine.optimization_governance.engine import local_factor_neighborhood
from backend.services.engine.tushare_agent_experiment.evaluation import (
    FormalQlibRunner,
    factor_values,
    group_diagnostics,
    oriented_signal,
    split_metrics,
)
from backend.services.engine.tushare_cutover.canonical import hash_payload


def cheap_screen(values: pd.DataFrame, matrix: pd.DataFrame, orientation: int) -> dict[str, Any]:
    metrics = split_metrics(values, matrix, *DEVELOPMENT_PERIOD, orientation)
    diagnostics = group_diagnostics(values, matrix, *DEVELOPMENT_PERIOD, orientation)
    selected = values[values["trade_date"].between(*DEVELOPMENT_PERIOD)].copy()
    numeric = pd.to_numeric(selected["factor_value"], errors="coerce")
    infinity = int(np.isinf(numeric.to_numpy(dtype=float, na_value=np.nan)).sum())
    selected["score"] = numeric * orientation
    ranks = selected.groupby("trade_date")["score"].rank(pct=True, method="average")
    selected["rank"] = ranks
    def lag_corr(periods: int) -> float | None:
        shifted = selected.sort_values(["symbol", "trade_date"]).groupby("symbol")["rank"].shift(periods)
        valid = selected["rank"].notna() & shifted.notna()
        return None if valid.sum() < 2 else float(selected.loc[valid, "rank"].corr(shifted[valid], method="spearman"))
    turnover_proxy = selected.sort_values(["symbol", "trade_date"]).groupby("symbol")["rank"].diff().abs().mean()
    passed = (
        (metrics.get("factor_finite_coverage") or 0.0) >= .90
        and infinity == 0
        and (
            (metrics.get("mean_rank_ic") or -999.0) >= -.002
            or (diagnostics.get("top_bottom_return") or 0.0) > 0
            or (diagnostics.get("group_monotonicity") or -999.0) > 0
        )
    )
    return {
        "passed": passed, "metrics": metrics, "diagnostics": diagnostics,
        "infinity_count": infinity, "pit_violation_count": 0,
        "score_autocorrelation": {"1": lag_corr(1), "5": lag_corr(5), "10": lag_corr(10)},
        "score_turnover_proxy": None if pd.isna(turnover_proxy) else float(turnover_proxy),
    }


def signal_similarity(left: pd.DataFrame, right: pd.DataFrame) -> dict[str, float | None]:
    merged = left.merge(right, on=["symbol", "trade_date"], suffixes=("_left", "_right"))
    if len(merged) < 2:
        return {"pearson": None, "spearman": None, "rank_overlap": None}
    x, y = merged["factor_value_left"], merged["factor_value_right"]
    pearson = x.corr(y, method="pearson")
    spearman = x.corr(y, method="spearman")
    overlaps = []
    for _, group in merged.groupby("trade_date"):
        count = max(1, int(np.ceil(len(group) * .2)))
        a = set(group.nlargest(count, "factor_value_left")["symbol"])
        b = set(group.nlargest(count, "factor_value_right")["symbol"])
        overlaps.append(len(a & b) / max(1, len(a | b)))
    return {
        "pearson": None if pd.isna(pearson) else float(pearson),
        "spearman": None if pd.isna(spearman) else float(spearman),
        "rank_overlap": float(np.mean(overlaps)) if overlaps else None,
    }


class CampaignEvaluator:
    def __init__(self, *, bundle, matrix: pd.DataFrame, contract, work_root):
        self.bundle = bundle
        self.matrix = matrix
        self.contract = contract
        self.work_root = work_root
        self.qlib = FormalQlibRunner(bundle.qlib_view, bundle.normalized, work_root / "qlib-cache")
        self.qlib.service.initialize()
        from qlib.config import C
        C.kernels = 1
        self.known_values: list[tuple[str, pd.DataFrame]] = []
        old_four, _, _ = _existing_four(bundle, work_root / "existing-factor-correlation")
        for factor_id, frame in old_four.items():
            self.known_values.append((
                factor_id,
                frame.rename(columns={"old_score": "factor_value"})[
                    ["symbol", "trade_date", "factor_value"]
                ],
            ))
        for descriptor in bundle.store.list_by_kind("skip_recent_momentum_candidate_lock"):
            target = work_root / "existing-factor-correlation" / descriptor.artifact_id
            if target.exists():
                shutil.rmtree(target)
            bundle.store.materialize_artifact(descriptor.descriptor_id, target)
            signal = pd.read_parquet(target / "signal.parquet")
            self.known_values.append((
                descriptor.artifact_id,
                signal.rename(columns={"pred": "factor_value"})[
                    ["symbol", "trade_date", "factor_value"]
                ],
            ))

    def evaluate(self, proposal: dict, *, maximum_local_trials: int = 6) -> dict[str, Any]:
        template = parse_template(proposal["template"])
        defaults = proposal["default_parameters"]
        compiled, values = factor_values(template, self.contract, defaults, self.matrix)
        raw_rankic = split_metrics(values, self.matrix, *DEVELOPMENT_PERIOD, 1).get("mean_rank_ic")
        orientation = 1 if raw_rankic is None or raw_rankic >= 0 else -1
        screen = cheap_screen(values, self.matrix, orientation)
        similarities = [
            {"artifact_id": artifact_id} | signal_similarity(values, prior)
            for artifact_id, prior in self.known_values
        ]
        max_spearman = max((abs(row["spearman"]) for row in similarities if row["spearman"] is not None), default=0.0)
        if max_spearman >= .95:
            return {"stage": "signal_duplicate", "passed": False, "failure_codes": ["duplicate_signal"],
                    "cheap_screen": screen, "signal_correlations": similarities, "values": values}
        if not screen["passed"]:
            return {"stage": "cheap_screen", "passed": False, "failure_codes": ["weak_predictive_signal"],
                    "cheap_screen": screen, "signal_correlations": similarities, "values": values}
        default_signal = oriented_signal(values, orientation, self.work_root / "signals" / f"{compiled.factor_instance_id}-default.parquet")
        default_qlib = _clean_result(self.qlib.run(
            default_signal, *DEVELOPMENT_PERIOD, rebalance_days=10, lifecycle_policy=LIFECYCLE_POLICY
        ))
        default_passed, failure_reasons = _development_gate(
            screen["metrics"], default_qlib, screen["diagnostics"], screen["infinity_count"]
        )
        # R2 tightens turnover from the historical R1-007 value of 45 to 40.
        if (default_qlib.get("turnover") or 999.0) > 40:
            default_passed = False
            if "turnover" not in failure_reasons:
                failure_reasons.append("turnover")
        selected = {
            "parameters": defaults, "compiled": compiled, "values": values,
            "metrics": screen["metrics"], "diagnostics": screen["diagnostics"],
            "qlib": default_qlib, "trial_id": "afct1_" + hash_payload({"instance": compiled.factor_instance_id, "parameters": defaults}),
            "default_candidate_passed": default_passed,
        }
        local_rows = []
        rescue_allowed = bool(defaults) and not default_passed and local_rescue_eligible(
            screen["metrics"], screen["diagnostics"], infinity_count=screen["infinity_count"]
        )
        if rescue_allowed:
            legal = {
                name: list(space["values"])
                for name, space in proposal["parameter_search"]["search_space"].items()
            }
            neighborhood = local_factor_neighborhood(defaults, legal)[:7]
            for parameters in neighborhood[1:1 + max(0, maximum_local_trials)]:
                local_compiled, local_values = factor_values(template, self.contract, parameters, self.matrix)
                metrics = split_metrics(local_values, self.matrix, *DEVELOPMENT_PERIOD, orientation)
                diagnostics = group_diagnostics(local_values, self.matrix, *DEVELOPMENT_PERIOD, orientation)
                signal = oriented_signal(local_values, orientation, self.work_root / "signals" / f"{local_compiled.factor_instance_id}-local.parquet")
                qlib = _clean_result(self.qlib.run(signal, *DEVELOPMENT_PERIOD, rebalance_days=10, lifecycle_policy=LIFECYCLE_POLICY))
                infinity = int(np.isinf(pd.to_numeric(local_values["factor_value"], errors="coerce").to_numpy(dtype=float, na_value=np.nan)).sum())
                passed, reasons = _development_gate(metrics, qlib, diagnostics, infinity)
                if (qlib.get("turnover") or 999.0) > 40:
                    passed = False
                    if "turnover" not in reasons:
                        reasons.append("turnover")
                local_rows.append({
                    "parameters": parameters, "compiled": local_compiled, "values": local_values,
                    "metrics": metrics, "diagnostics": diagnostics, "qlib": qlib,
                    "passed": passed, "failure_reasons": reasons,
                    "trial_id": "afct1_" + hash_payload({"instance": local_compiled.factor_instance_id, "parameters": parameters}),
                })
            rescued = next((row for row in sorted(local_rows, key=_selection_key) if row["passed"]), None)
            if rescued is not None:
                selected = rescued | {"default_candidate_passed": False}
        if not (default_passed or selected.get("passed")):
            codes = ["high_turnover" if "turnover" in failure_reasons else "weak_predictive_signal"]
            return {
                "stage": "development", "passed": False, "failure_codes": codes,
                "cheap_screen": screen, "default_qlib": default_qlib,
                "default_failure_reasons": failure_reasons, "local_trials": self._public_trials(local_rows),
                "local_rescue_eligible": rescue_allowed, "signal_correlations": similarities, "values": values,
            }
        annual = []
        for year, period in ANNUAL_PERIODS.items():
            metrics = split_metrics(selected["values"], self.matrix, *period, orientation)
            diagnostics = group_diagnostics(selected["values"], self.matrix, *period, orientation)
            signal = oriented_signal(selected["values"], orientation, self.work_root / "signals" / f"{selected['compiled'].factor_instance_id}-{year}.parquet")
            qlib = _clean_result(self.qlib.run(signal, *period, rebalance_days=10, lifecycle_policy=LIFECYCLE_POLICY))
            annual.append({"year": year, "metrics": metrics, "diagnostics": diagnostics, "qlib": qlib})
        summary = self._annual_summary(annual, max_spearman)
        self.known_values.append((selected["compiled"].factor_instance_id, selected["values"]))
        return {
            "stage": "eligibility", "passed": summary["eligible"],
            "failure_codes": [] if summary["eligible"] else ["annual_instability"],
            "cheap_screen": screen, "default_qlib": default_qlib,
            "default_failure_reasons": failure_reasons, "local_trials": self._public_trials(local_rows),
            "local_rescue_eligible": rescue_allowed, "development_lock": {
                "factor_instance_id": selected["compiled"].factor_instance_id,
                "selected_parameters": selected["parameters"], "orientation": orientation,
                "optimization_mode": "default_parameters" if default_passed else "local_optimization_research",
                "optimization_rescued": not default_passed,
                "development_metrics": selected["metrics"] | selected["diagnostics"] | {"qlib": selected["qlib"]},
            },
            "annual": annual, "summary": summary, "signal_correlations": similarities,
            "values": selected["values"],
        }

    def report(self, result: dict) -> list[dict]:
        lock = result["development_lock"]
        rows = []
        for name, period in REPORT_PERIODS.items():
            metrics = split_metrics(result["values"], self.matrix, *period, lock["orientation"])
            signal = oriented_signal(result["values"], lock["orientation"], self.work_root / "signals" / f"{lock['factor_instance_id']}-{name}.parquet")
            qlib = _clean_result(self.qlib.run(signal, *period, rebalance_days=10, lifecycle_policy=LIFECYCLE_POLICY))
            rows.append({"period": name, "metrics": metrics, "qlib": qlib,
                         "contaminated_report_only": True, "not_used_for_selection": True,
                         "not_fresh_validation": True})
        return rows

    @staticmethod
    def _public_trials(rows):
        return [{key: value for key, value in row.items() if key not in {"compiled", "values"}} for row in rows]

    @staticmethod
    def _annual_summary(rows: list[dict], max_correlation: float) -> dict:
        rankic = [row["metrics"].get("mean_rank_ic") for row in rows]
        excess = [row["qlib"].get("net_excess_csi300") for row in rows]
        turnover = [row["qlib"].get("turnover") for row in rows]
        concentration = [row["qlib"].get("best_10_days_contribution") for row in rows]
        values = {
            "complete_year_count": len(rows),
            "positive_rankic_year_count": sum(value is not None and value > 0 for value in rankic),
            "median_rankic": float(median(rankic)) if None not in rankic else None,
            "worst_rankic": min(rankic) if None not in rankic else None,
            "positive_excess_year_count": sum(value is not None and value > 0 for value in excess),
            "median_excess": float(median(excess)) if None not in excess else None,
            "worst_excess": min(excess) if None not in excess else None,
            "median_turnover": float(median(turnover)) if None not in turnover else None,
            "median_best10_contribution": float(median(concentration)) if None not in concentration else None,
            "maximum_old_factor_correlation": max_correlation,
        }
        checks = {
            "complete_years": len(rows) == 4,
            "coverage": all((row["metrics"].get("factor_finite_coverage") or 0) >= .90 for row in rows),
            "positive_rankic_years": values["positive_rankic_year_count"] >= 3,
            "median_rankic": values["median_rankic"] is not None and values["median_rankic"] >= .003,
            "worst_rankic": values["worst_rankic"] is not None and values["worst_rankic"] >= -.008,
            "positive_excess_years": values["positive_excess_year_count"] >= 3,
            "median_excess": values["median_excess"] is not None and values["median_excess"] > 0,
            "worst_excess": values["worst_excess"] is not None and values["worst_excess"] > -.10,
            "turnover": values["median_turnover"] is not None and values["median_turnover"] <= 30,
            "concentration": values["median_best10_contribution"] is not None and values["median_best10_contribution"] <= .35,
            "independence": max_correlation < .85,
        }
        return values | {"gate_results": checks, "eligible": all(checks.values()),
                         "gate_failure_reasons": [name for name, passed in checks.items() if not passed]}
