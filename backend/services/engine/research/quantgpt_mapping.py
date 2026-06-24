from __future__ import annotations

import math
import re
from datetime import date
from typing import Any

from backend.services.engine.research.schemas import (
    FactorValueRow,
    FactorValuesParseResult,
    QuantGPTCandidateMetrics,
    QuantGPTContractError,
    QuantGPTEvaluation,
)
from backend.shared.stock_utils import StockCodeUtil


_PREFIX_SYMBOL_RE = re.compile(r"^(SH|SZ|BJ)\d{6}$")
_QUANTGPT_DOTTED_RE = re.compile(r"^(sh|sz|bj)\.(\d{6})$", re.IGNORECASE)


def normalize_quantgpt_symbol(symbol: Any) -> str:
    raw = str(symbol or "").strip()
    dotted = _QUANTGPT_DOTTED_RE.match(raw)
    if dotted:
        raw = f"{dotted.group(1)}{dotted.group(2)}"
    normalized = StockCodeUtil.to_prefix(raw)
    if not _PREFIX_SYMBOL_RE.match(normalized):
        raise QuantGPTContractError(f"invalid symbol: {symbol!r}")
    return normalized


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _result_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result")
    if result is None and any(
        key in payload for key in ("backtest_summary", "scoring", "stock_factor_data")
    ):
        result = payload
    if not isinstance(result, dict):
        raise QuantGPTContractError("completed QuantGPT payload missing result object")
    return result


def parse_evaluation_payload(payload: dict[str, Any]) -> QuantGPTEvaluation:
    status = payload.get("status")
    if not isinstance(status, str) or not status:
        raise QuantGPTContractError("QuantGPT evaluation payload missing status")

    task_id = payload.get("task_id") or payload.get("candidate_id")
    expression = payload.get("expression")
    if status != "completed":
        return QuantGPTEvaluation(
            task_id=str(task_id) if task_id else None,
            expression=str(expression) if expression else None,
            status=status,
            metrics=None,
            params={},
            report_url=None,
            raw_payload=payload,
        )

    result = _result_payload(payload)
    backtest_summary = result.get("backtest_summary") or {}
    scoring = result.get("scoring") or {}
    anti_overfit = result.get("anti_overfit") or {}
    params = result.get("params") or {}
    stock_factor_data = result.get("stock_factor_data") or {}
    stocks = stock_factor_data.get("stocks") or []

    invalid_symbol_count = 0
    normalized_stocks: list[dict[str, Any]] = []
    if isinstance(stocks, list):
        for row in stocks:
            if not isinstance(row, dict):
                invalid_symbol_count += 1
                continue
            try:
                normalized_symbol = normalize_quantgpt_symbol(row.get("stock_code"))
            except QuantGPTContractError:
                invalid_symbol_count += 1
                continue
            normalized = dict(row)
            normalized["symbol"] = normalized_symbol
            normalized_stocks.append(normalized)

    metrics = QuantGPTCandidateMetrics(
        score=_safe_float(scoring.get("score") or result.get("score")),
        grade=(
            scoring.get("grade")
            or scoring.get("rating")
            or (result.get("interpretation") or {}).get("rating")
        ),
        rank_ic_mean=_safe_float(backtest_summary.get("rank_ic_mean")),
        ic_ir=_safe_float(backtest_summary.get("ic_ir")),
        turnover=_safe_float(backtest_summary.get("turnover")),
        wq_fitness=_safe_float(backtest_summary.get("wq_fitness")),
        monotonicity_score=_safe_float(backtest_summary.get("monotonicity_score")),
        anti_overfit_score=_safe_float(anti_overfit.get("score")),
        coverage_days=_safe_int(result.get("trading_days") or params.get("trading_days")),
        total_stock_count=_safe_int(
            stock_factor_data.get("total_stock_count") or params.get("stock_count")
        ),
        raw={
            "backtest_summary": backtest_summary,
            "scoring": scoring,
            "anti_overfit": anti_overfit,
        },
    )
    return QuantGPTEvaluation(
        task_id=str(task_id) if task_id else None,
        expression=str(expression or params.get("expression") or ""),
        status=status,
        metrics=metrics,
        params=dict(params),
        report_url=result.get("report_url"),
        invalid_symbol_count=invalid_symbol_count,
        normalized_stock_factor_data=normalized_stocks,
        raw_payload=payload,
    )


def parse_factor_values_payload(payload: dict[str, Any]) -> FactorValuesParseResult:
    data = payload.get("data")
    rows: list[FactorValueRow] = []
    invalid_symbol_count = 0

    if isinstance(data, list):
        for day_payload in data:
            if not isinstance(day_payload, dict):
                raise QuantGPTContractError("factor values day item must be an object")
            trade_date_raw = day_payload.get("date") or day_payload.get("trade_date")
            if not trade_date_raw:
                raise QuantGPTContractError("factor values day item missing date")
            try:
                trade_date = date.fromisoformat(str(trade_date_raw))
            except ValueError as exc:
                raise QuantGPTContractError(
                    f"invalid factor values date: {trade_date_raw!r}"
                ) from exc

            values = day_payload.get("values")
            if not isinstance(values, dict):
                raise QuantGPTContractError(
                    "factor values day item missing values object"
                )
            for symbol, factor_value in values.items():
                parsed_value = _safe_float(factor_value)
                if parsed_value is None:
                    continue
                try:
                    normalized_symbol = normalize_quantgpt_symbol(symbol)
                except QuantGPTContractError:
                    invalid_symbol_count += 1
                    continue
                rows.append(
                    FactorValueRow(
                        trade_date=trade_date,
                        symbol=normalized_symbol,
                        factor_value=parsed_value,
                    )
                )
    else:
        result = (
            payload.get("result") if isinstance(payload.get("result"), dict) else payload
        )
        stock_factor_data = (
            result.get("stock_factor_data") if isinstance(result, dict) else None
        )
        if not isinstance(stock_factor_data, dict):
            raise QuantGPTContractError(
                "QuantGPT factor values payload missing data list or stock_factor_data object"
            )
        stocks = stock_factor_data.get("stocks")
        if not isinstance(stocks, list):
            raise QuantGPTContractError("stock_factor_data missing stocks list")
        trade_date_raw = (
            stock_factor_data.get("rebalance_date")
            or stock_factor_data.get("trade_date")
            or payload.get("trade_date")
        )
        if not trade_date_raw:
            raise QuantGPTContractError("stock_factor_data missing rebalance_date")
        try:
            trade_date = date.fromisoformat(str(trade_date_raw))
        except ValueError as exc:
            raise QuantGPTContractError(
                f"invalid factor values date: {trade_date_raw!r}"
            ) from exc

        for item in stocks:
            if not isinstance(item, dict):
                raise QuantGPTContractError(
                    "stock_factor_data stock item must be an object"
                )
            symbol = item.get("stock_code") or item.get("symbol")
            factor_value = item.get("factor_value")
            parsed_value = _safe_float(factor_value)
            if parsed_value is None:
                continue
            try:
                normalized_symbol = normalize_quantgpt_symbol(symbol)
            except QuantGPTContractError:
                invalid_symbol_count += 1
                continue
            rows.append(
                FactorValueRow(
                    trade_date=trade_date,
                    symbol=normalized_symbol,
                    factor_value=parsed_value,
                )
            )

    result_payload = (
        payload.get("result") if isinstance(payload.get("result"), dict) else {}
    )
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    if not params and isinstance(result_payload.get("params"), dict):
        params = result_payload["params"]

    return FactorValuesParseResult(
        expression=payload.get("expression") or params.get("expression"),
        universe=payload.get("universe") or params.get("universe"),
        start_date=payload.get("start_date") or params.get("start_date"),
        end_date=payload.get("end_date") or params.get("end_date"),
        rows=rows,
        invalid_symbol_count=invalid_symbol_count,
        raw_payload=payload,
    )
