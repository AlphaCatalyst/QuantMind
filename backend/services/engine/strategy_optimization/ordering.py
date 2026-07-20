from __future__ import annotations

from typing import Any


def ordering_key(trial: dict[str, Any]) -> tuple[Any, ...]:
    metrics = trial["metrics"]
    full = metrics["full_period"]
    return (
        -metrics["positive_excess_year_count"], -metrics["median_annual_net_excess"],
        -metrics["worst_annual_net_excess"], -full["sharpe_ratio"],
        abs(full["maximum_drawdown"]), full["turnover"], full["transaction_cost"],
        trial["trial_id"],
    )


def rank_trials(trials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible = [trial for trial in trials if trial["metrics"].get("eligible")]
    return sorted(eligible, key=ordering_key)


def parameter_sensitivity(trials: list[dict[str, Any]], selected: dict[str, Any]) -> dict[str, Any]:
    base = selected["metrics"]["median_annual_net_excess"]
    dimensions = {"topk": [], "n_drop": [], "rebalance_interval": []}
    for name in dimensions:
        peers = [item for item in trials if item["metrics"].get("eligible") and all(
            item[key] == selected[key] for key in dimensions if key != name
        )]
        dimensions[name] = [item["metrics"]["median_annual_net_excess"] - base for item in peers]
    maximum_neighbor_loss = max(
        (-min(values) if values else 0.0) for values in dimensions.values()
    )
    label = "parameter_robust" if maximum_neighbor_loss <= 0.02 else "parameter_sensitive" if maximum_neighbor_loss <= 0.05 else "parameter_unstable"
    return {
        "method": "one_dimension_neighbor_median_annual_excess_delta_v1",
        "topk_sensitivity": dimensions["topk"], "n_drop_sensitivity": dimensions["n_drop"],
        "rebalance_sensitivity": dimensions["rebalance_interval"],
        "maximum_neighbor_loss": maximum_neighbor_loss, "stability_label": label,
    }
