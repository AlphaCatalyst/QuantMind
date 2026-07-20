from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from backend.services.engine.tushare_cutover.canonical import hash_payload


@dataclass(frozen=True)
class FixedUniverseLifecyclePolicyV1:
    schema_version: str = "fixed-universe-lifecycle-policy-v1"
    locked_member_count: int = 100
    topk: int = 20
    n_drop: int = 5
    rebalance_days: int = 5
    active_rule: str = "list_date <= date <= delist_date; empty delist_date means open-ended"
    observable_rule: str = "active member with an authoritative normalized market row on date"
    tradable_rule: str = "observable member accepted by the stored tradable flag and Qlib/CnExchange"
    signal_eligible_rule: str = "observable member with a finite locked signal value"
    replacement_rule: str = "forbidden"
    market_fill_rule: str = "forbidden"
    signal_fill_rule: str = "forbidden"
    benchmark_rule: str = "daily equal weight over observable locked members; renormalize to 100 percent"

    @property
    def minimum_observable_instruments(self) -> int:
        return self.topk + self.n_drop

    @property
    def policy_id(self) -> str:
        return "fulp_" + hash_payload(self.payload(include_id=False))

    def payload(self, *, include_id: bool = True) -> dict:
        payload = asdict(self) | {
            "minimum_observable_instruments": self.minimum_observable_instruments,
            "capacity_derivation": "topk + n_drop",
            "set_relations": [
                "tradable subset observable subset active subset locked",
                "signal_eligible subset observable",
            ],
        }
        if include_id:
            payload["policy_id"] = self.policy_id
        return payload


def normalize_symbol(ts_code: str) -> str:
    code, exchange = ts_code.split(".")
    return ("SH" if exchange == "SH" else "SZ") + code


def active_on(row: Mapping, date: pd.Timestamp) -> bool:
    day = date.strftime("%Y%m%d")
    listed = str(row.get("list_date") or "")
    delisted = str(row.get("delist_date") or "")
    return (not listed or listed <= day) and (not delisted or day <= delisted)


def audit_lifecycles(
    universe: pd.DataFrame,
    stock_basic: pd.DataFrame,
    daily: pd.DataFrame,
    adj_factor: pd.DataFrame,
    daily_basic: pd.DataFrame,
    normalized: pd.DataFrame,
    qlib_instruments: Path,
    *,
    period_start: str,
) -> tuple[list[dict], dict]:
    basic = stock_basic.set_index("ts_code", drop=False)
    locked = universe.sort_values("rank", kind="mergesort")
    lines = {}
    for line in Path(qlib_instruments).read_text(encoding="utf-8").splitlines():
        symbol, start, end = line.split("\t")
        lines[symbol] = {"qlib_start_date": start, "qlib_end_date": end}
    audits = []
    start = pd.Timestamp(period_start)
    for row in locked.to_dict("records"):
        ts_code = row["ts_code"]
        symbol = normalize_symbol(ts_code)
        meta = basic.loc[ts_code]
        def last(frame: pd.DataFrame, code_column: str = "ts_code") -> str | None:
            values = frame.loc[frame[code_column] == ts_code, "trade_date"]
            if values.empty:
                return None
            return pd.Timestamp(values.max()).strftime("%Y-%m-%d")
        delist = str(meta.get("delist_date") or "")
        delist_timestamp = pd.to_datetime(delist, format="%Y%m%d") if delist else None
        if delist_timestamp is not None and delist_timestamp < start:
            reason = "DELISTED_BEFORE_PERIOD"
        elif delist_timestamp is not None and delist_timestamp <= pd.Timestamp("2026-06-23"):
            reason = "DELISTED_DURING_PERIOD"
        elif normalized.loc[normalized.symbol == symbol].empty:
            reason = "TUSHARE_SOURCE_ABSENCE"
        else:
            reason = None
        audits.append({
            "rank": int(row["rank"]), "symbol": symbol, "ts_code": ts_code,
            "name": str(meta.get("name") or ""), "list_date": str(meta.get("list_date") or ""),
            "delist_date": delist or None, "list_status": str(meta.get("list_status") or ""),
            "last_market_date": last(normalized, "ts_code"),
            "last_daily_row": last(daily), "last_adj_factor_row": last(adj_factor),
            "last_daily_basic_row": last(daily_basic), "absence_reason": reason,
            **lines.get(symbol, {}),
        })
    contract = {
        "schema_version": "fixed100-qlib-instrument-contract-v1",
        "locked_member_count": len(locked), "instrument_member_count": len(lines),
        "membership_exact": set(lines) == {normalize_symbol(code) for code in locked.ts_code},
        "format": "symbol<TAB>observable_start_date<TAB>observable_end_date",
        "members": [row for row in audits],
    }
    return audits, contract


def daily_member_counts(
    universe: pd.DataFrame,
    stock_basic: pd.DataFrame,
    normalized: pd.DataFrame,
    signals: Mapping[str, pd.DataFrame],
    *, start: str, end: str,
) -> pd.DataFrame:
    dates = sorted(pd.to_datetime(normalized.trade_date.drop_duplicates()))
    dates = [d for d in dates if pd.Timestamp(start) <= d <= pd.Timestamp(end)]
    basic_rows = stock_basic.set_index("ts_code").loc[universe.ts_code].to_dict("index")
    symbol_to_code = {normalize_symbol(code): code for code in universe.ts_code}
    market = normalized.copy()
    market["trade_date"] = pd.to_datetime(market.trade_date)
    market = market[(market.trade_date >= start) & (market.trade_date <= end)]
    signal_maps = {}
    for name, frame in signals.items():
        item = frame.copy()
        item["trade_date"] = pd.to_datetime(item.trade_date)
        signal_maps[name] = item.set_index(["trade_date", "symbol"])["pred"]
    rows = []
    for date in dates:
        active = {normalize_symbol(code) for code, row in basic_rows.items() if active_on(row, date)}
        observed_frame = market[market.trade_date == date]
        observable = set(observed_frame.symbol) & active
        tradable = set(observed_frame.loc[observed_frame.tradable.astype(bool), "symbol"]) & observable
        record = {
            "trade_date": date, "locked_member_count": len(universe),
            "active_member_count": len(active), "observable_member_count": len(observable),
            "tradable_member_count": len(tradable),
            "structurally_inactive_count": len(universe) - len(active),
        }
        for name, indexed in signal_maps.items():
            values = [indexed.get((date, symbol), np.nan) for symbol in observable]
            finite = sum(bool(np.isfinite(value)) for value in values)
            record[f"{name}__signal_eligible_count"] = finite
            record[f"{name}__signal_nan_count"] = len(observable) - finite
            record[f"{name}__signal_nan_ratio"] = 0.0 if not observable else (len(observable) - finite) / len(observable)
        rows.append(record)
    return pd.DataFrame(rows)
