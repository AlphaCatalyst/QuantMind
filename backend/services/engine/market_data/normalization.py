from __future__ import annotations

import math

import pandas as pd

from .errors import NormalizationError
from .models import DAILY_FIELDS, DailyBarsBatch
from .symbol import normalize_symbol


NORMALIZATION_VERSION = "daily-bars-normalization-v1"
CANONICAL_UNITS = {"price": "CNY/share", "volume": "share", "amount": "CNY"}


def normalize_daily_bars(batch: DailyBarsBatch) -> pd.DataFrame:
    if tuple(batch.source_fields) != DAILY_FIELDS:
        raise NormalizationError("provider daily-bar schema drift")
    if dict(batch.units) != CANONICAL_UNITS:
        raise NormalizationError("provider units are not explicitly canonical")
    frame = pd.DataFrame(batch.rows)
    if frame.empty:
        return pd.DataFrame(columns=DAILY_FIELDS)
    if tuple(frame.columns) != DAILY_FIELDS:
        raise NormalizationError("daily-bar row fields differ from v1 schema")
    try:
        frame["symbol"] = frame["symbol"].map(normalize_symbol)
        dates = pd.to_datetime(frame["trade_date"], errors="raise")
        if dates.dt.tz is not None:
            raise NormalizationError("trade_date must not contain timezone/time")
        if any(item.time().isoformat() != "00:00:00" for item in dates):
            raise NormalizationError("trade_date contains time-of-day")
        frame["trade_date"] = dates.dt.date
        for column in ("open", "high", "low", "close", "volume", "amount"):
            frame[column] = pd.to_numeric(frame[column], errors="raise").astype("float64")
            if not frame[column].map(math.isfinite).all():
                raise NormalizationError(f"{column} contains NaN or Infinity")
    except NormalizationError:
        raise
    except Exception as exc:
        raise NormalizationError("daily-bar value normalization failed") from exc
    if frame.duplicated(["symbol", "trade_date"]).any():
        raise NormalizationError("duplicate symbol and trade_date")
    return frame.sort_values(["symbol", "trade_date"], kind="mergesort").reset_index(drop=True)
