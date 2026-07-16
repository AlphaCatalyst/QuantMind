import re

import numpy as np
import pandas as pd

from backend.shared.feature_preprocess import cs_zscore_with_mad_series

from .canonical import hash_payload
from .errors import LabelContractError
from .models import LabelContract


LABEL_CONTRACT_VERSION = "1.0.0"
LABEL_ENGINE_VERSION = "production-label-parity-v1"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def production_label_contract(horizon=1):
    if isinstance(horizon, bool) or not isinstance(horizon, int) or not 1 <= horizon <= 30:
        raise LabelContractError("horizon must be an integer in 1..30")
    return LabelContract(
        LABEL_CONTRACT_VERSION,
        f"tradable_return_t1_open_to_t{horizon}_close",
        ("symbol", "trade_date", "open", "close", "factor"),
        "T feature observation after market data for trade_date T",
        "T+1 observed trading row open",
        f"T+{horizon} observed trading row close",
        horizon,
        f"adjusted_close[T+{horizon}] / adjusted_open[T+1] - 1",
        "open and close are multiplied by the same-row factor before return calculation",
        "retain open-limit extreme labels; sample_weight=0.5 when next adjusted open move is >=9.5% or <=-9.5%; production prefix symbols make the intended 20% STAR/GEM branch unreachable",
        "next_open<=0 or unavailable entry/exit produces null; null labels are excluded",
        "per-date MAD clip at 5x median absolute deviation, then sample-std z-score; all-null or MAD=0 becomes 0.0",
        "float64 artifact derived from production float32 source inputs",
        "model_label",
    )


def label_contract_payload(contract):
    return dict(contract.__dict__)


def label_contract_id(contract):
    return "lc_" + hash_payload({"label_contract": label_contract_payload(contract), "label_engine_version": LABEL_ENGINE_VERSION})


def build_production_labels(frame, contract):
    required = set(contract.source_columns)
    if required - set(frame.columns):
        raise LabelContractError(f"label inputs missing: {sorted(required-set(frame.columns))}")
    data = frame[list(contract.source_columns)].copy()
    data["trade_date"] = pd.to_datetime(data["trade_date"], errors="coerce")
    if data["trade_date"].isna().any() or data.duplicated(["symbol", "trade_date"]).any():
        raise LabelContractError("label input keys are invalid or duplicated")
    for name in ("open", "close", "factor"):
        data[name] = pd.to_numeric(data[name], errors="coerce").astype("float32")
    data = data[data["close"] > 0].copy()
    symbols = data["symbol"].astype(str).str.zfill(6)
    data = data[~(symbols.str.match(r"^SH9\d{5}$", na=False) | symbols.str.match(r"^SZ2\d{5}$", na=False))]
    data = data.sort_values(["symbol", "trade_date"], kind="mergesort").reset_index(drop=True)
    grouped = data.groupby("symbol", sort=False)
    horizon = contract.horizon
    future_close = grouped["close"].shift(-horizon) * grouped["factor"].shift(-horizon)
    next_open = grouped["open"].shift(-1) * grouped["factor"].shift(-1)
    current_close = data["close"] * data["factor"]
    # Exact production behavior: real symbols are prefix-form, so these tests are false.
    production_symbols = data["symbol"].astype(str).str.zfill(6)
    is_star_gem = production_symbols.str.startswith(("688", "300"))
    limit_threshold = np.where(is_star_gem, 0.195, 0.095)
    open_move = next_open / current_close - 1
    is_extreme = (open_move >= limit_threshold) | (open_move <= -limit_threshold)
    raw = np.where(next_open > 0, future_close / next_open - 1, np.nan)
    data["raw_label"] = pd.Series(raw, index=data.index, dtype="float64")
    data["sample_weight"] = np.where(is_extreme, 0.5, 1.0).astype("float64")
    data["entry_trade_date"] = grouped["trade_date"].shift(-1)
    data["exit_trade_date"] = grouped["trade_date"].shift(-horizon)
    data["model_label"] = data.groupby("trade_date")["raw_label"].transform(
        lambda series: cs_zscore_with_mad_series(series, mad_multiplier=5.0)
    ).astype("float64")
    return data[["symbol", "trade_date", "entry_trade_date", "exit_trade_date", "raw_label", "model_label", "sample_weight"]].sort_values(
        ["trade_date", "symbol"], kind="mergesort"
    ).reset_index(drop=True)
