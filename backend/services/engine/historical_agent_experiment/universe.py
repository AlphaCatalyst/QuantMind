from __future__ import annotations

import pandas as pd

from .canonical import hash_payload


def select_fixed_universe(frame: pd.DataFrame) -> dict:
    required = {"symbol", "trade_date", "style_ln_mv_float"}
    if required - set(frame.columns):
        raise ValueError("fixed-universe source lacks required as-of fields")
    data = frame[list(required)].copy()
    data["trade_date"] = pd.to_datetime(data["trade_date"], errors="raise")
    dates = tuple(sorted(data["trade_date"].drop_duplicates())[:20])
    if len(dates) != 20:
        raise ValueError("2019 source has fewer than 20 observed trading dates")
    observed = data[data["trade_date"].isin(dates)]
    finite = pd.to_numeric(observed["style_ln_mv_float"], errors="coerce")
    observed = observed.assign(_metric=finite)
    grouped = observed.groupby("symbol", sort=True)["_metric"].agg(["count", "mean"])
    eligible = grouped[grouped["count"] >= 15].sort_values(["mean"], ascending=False,
                                                            kind="mergesort")
    symbols = tuple(sorted(eligible.head(100).index.astype(str)))
    if len(symbols) != 100 or len(set(symbols)) != 100:
        raise ValueError("as-of rule did not produce exactly 100 unique symbols")
    identity = {
        "schema_version": "fixed-universe-lock-v1", "selection_scheme": "A",
        "selection_rule": "mean style_ln_mv_float over first 20 observed 2019 dates; >=15 valid dates; descending top100",
        "observable_dates": [item.date().isoformat() for item in dates],
        "minimum_valid_observations": 15, "ranking_field": "style_ln_mv_float",
        "symbols": list(symbols), "replacement_policy": "never",
        "missing_data_policy": "preserve_missing", "annual_reselection": False,
        "survivorship_biased_fixed_universe": False,
    }
    return {**identity, "universe_lock_id": "ful_" + hash_payload(identity)}
