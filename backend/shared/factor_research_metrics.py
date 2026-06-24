"""Prometheus metrics for the factor research pipeline."""

from __future__ import annotations

from collections import Counter
from typing import Any

try:
    from prometheus_client import REGISTRY, Gauge

    def _create_gauge(name: str, documentation: str, labelnames=()):
        collector = REGISTRY._names_to_collectors.get(name)  # type: ignore[attr-defined]
        if collector is not None:
            return collector
        return Gauge(name, documentation, labelnames=labelnames)

    FACTOR_RESEARCH_HEALTH_STATUS = _create_gauge(
        "quantmind_factor_research_health_status",
        "Factor research health status by state (1 current, 0 otherwise)",
        ["status"],
    )
    FACTOR_RESEARCH_ALERTS_TOTAL = _create_gauge(
        "quantmind_factor_research_alerts_total",
        "Current factor research alert count",
    )
    FACTOR_RESEARCH_ALERTS_BY_LEVEL = _create_gauge(
        "quantmind_factor_research_alerts_by_level",
        "Current factor research alert count by level",
        ["level"],
    )
    FACTOR_RESEARCH_INDICATOR_VALUE = _create_gauge(
        "quantmind_factor_research_indicator_value",
        "Current factor research health indicator values",
        ["indicator"],
    )
    FACTOR_RESEARCH_QUOTA_POLICY_VALUE = _create_gauge(
        "quantmind_factor_research_quota_policy_value",
        "Current factor research quota policy values",
        ["quota"],
    )
except Exception:  # pragma: no cover - prometheus is optional
    FACTOR_RESEARCH_HEALTH_STATUS = None
    FACTOR_RESEARCH_ALERTS_TOTAL = None
    FACTOR_RESEARCH_ALERTS_BY_LEVEL = None
    FACTOR_RESEARCH_INDICATOR_VALUE = None
    FACTOR_RESEARCH_QUOTA_POLICY_VALUE = None


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, int | float):
        return float(value)
    return None


def update_factor_research_metrics(health: dict[str, Any]) -> None:
    """Refresh factor research gauges from the latest health payload."""
    if FACTOR_RESEARCH_HEALTH_STATUS is None:
        return

    current_status = str(health.get("status") or "unknown").strip() or "unknown"
    for status in ("healthy", "warning", "critical", "unknown"):
        FACTOR_RESEARCH_HEALTH_STATUS.labels(status=status).set(
            1 if status == current_status else 0
        )

    alerts = health.get("alerts") if isinstance(health.get("alerts"), list) else []
    if FACTOR_RESEARCH_ALERTS_TOTAL is not None:
        FACTOR_RESEARCH_ALERTS_TOTAL.set(len(alerts))

    level_counts = Counter(
        str(alert.get("level") or "unknown").strip() or "unknown"
        for alert in alerts
        if isinstance(alert, dict)
    )
    if FACTOR_RESEARCH_ALERTS_BY_LEVEL is not None:
        for level in ("warning", "critical", "unknown"):
            FACTOR_RESEARCH_ALERTS_BY_LEVEL.labels(level=level).set(
                level_counts.get(level, 0)
            )

    indicators = health.get("indicators")
    if FACTOR_RESEARCH_INDICATOR_VALUE is not None and isinstance(indicators, dict):
        for name, value in indicators.items():
            numeric_value = _numeric(value)
            if numeric_value is not None:
                FACTOR_RESEARCH_INDICATOR_VALUE.labels(indicator=str(name)).set(
                    numeric_value
                )

    quota_policy = health.get("quotaPolicy")
    if FACTOR_RESEARCH_QUOTA_POLICY_VALUE is not None and isinstance(
        quota_policy, dict
    ):
        for name, value in quota_policy.items():
            numeric_value = _numeric(value)
            if numeric_value is not None:
                FACTOR_RESEARCH_QUOTA_POLICY_VALUE.labels(quota=str(name)).set(
                    numeric_value
                )
