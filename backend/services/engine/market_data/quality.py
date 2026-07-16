from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import pandas as pd

from .models import DailyBarsRequest


@dataclass(frozen=True)
class QualityIssue:
    code: str
    severity: str
    count: int
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity, "count": self.count, "message": self.message}


def evaluate_daily_bars(frame: pd.DataFrame, request: DailyBarsRequest) -> dict[str, Any]:
    issues: list[QualityIssue] = []

    def add(code: str, severity: str, mask_or_count: Any, message: str) -> None:
        count = int(mask_or_count.sum()) if hasattr(mask_or_count, "sum") else int(mask_or_count)
        if count:
            issues.append(QualityIssue(code, severity, count, message))

    if frame.empty:
        add("EMPTY_RESULT", "error", 1, "Provider returned no daily bars")
    else:
        add("DUPLICATE_KEY", "error", frame.duplicated(["symbol", "trade_date"]), "Duplicate primary key")
        for column in ("open", "high", "low", "close", "volume", "amount"):
            add(
                "NON_FINITE_VALUE",
                "error",
                ~frame[column].map(lambda value: isinstance(value, (int, float)) and math.isfinite(value)),
                f"{column} contains null, NaN, Infinity, or a non-numeric value",
            )
        add("DATE_OUT_OF_RANGE", "error", frame["trade_date"].map(lambda d: d < request.start_date or d > request.end_date), "Date outside request")
        add("HIGH_BELOW_LOW", "error", frame["high"] < frame["low"], "High is below low")
        add("OPEN_OUTSIDE_RANGE", "error", (frame["open"] < frame["low"]) | (frame["open"] > frame["high"]), "Open outside high-low")
        add("CLOSE_OUTSIDE_RANGE", "error", (frame["close"] < frame["low"]) | (frame["close"] > frame["high"]), "Close outside high-low")
        add("NEGATIVE_VOLUME", "error", frame["volume"] < 0, "Negative volume")
        add("NEGATIVE_AMOUNT", "error", frame["amount"] < 0, "Negative amount")
        present = set(frame["symbol"])
        add("MISSING_SYMBOL", "error", len(set(request.symbols) - present), "Requested symbol has no rows")
        add("NON_WEEKDAY_RECORD", "warning", frame["trade_date"].map(lambda d: d.weekday() >= 5), "No authoritative calendar; weekend row observed")
        for symbol, group in frame.groupby("symbol", sort=False):
            weekdays = pd.bdate_range(group["trade_date"].min(), group["trade_date"].max()).date
            missing = len(set(weekdays) - set(group["trade_date"]))
            add("DATE_GAP_UNVERIFIED", "warning", missing, f"Weekday gaps for {symbol}; authoritative calendar unavailable")
    summary = {level: sum(item.count for item in issues if item.severity == level) for level in ("error", "warning", "info")}
    return {
        "status": "error" if summary["error"] else "warning" if summary["warning"] else "passed",
        "summary": summary,
        "issues": [item.to_dict() for item in issues],
        "calendar_validation": "weekday-only-unverified-v1",
    }
