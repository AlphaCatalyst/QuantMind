from __future__ import annotations

import pandas as pd


FORMAL_CHAIN = ("QlibBacktestService", "RedisRecordingStrategy", "SimulatorExecutor", "CnExchange")


def to_qlib_score(signal: pd.DataFrame) -> pd.DataFrame:
    """Map the canonical signal schema to the existing Qlib score contract."""
    if list(signal.columns) != ["symbol", "trade_date", "score"]:
        raise ValueError("canonical unified signal columns are required")
    output = signal.rename(columns={"score": "pred"}).copy()
    output["trade_date"] = pd.to_datetime(output["trade_date"])
    return output.sort_values(["trade_date", "symbol"]).reset_index(drop=True)


def assert_formal_result(result: dict) -> None:
    if result.get("status") != "completed" or tuple(result.get("formal_chain", ())) != FORMAL_CHAIN:
        raise ValueError("formal Qlib result contract failed")
