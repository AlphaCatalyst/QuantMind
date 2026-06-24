"""Engine-side factor value store accessors."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from sqlalchemy import text

from backend.shared.database_manager_v2 import get_session
from backend.shared.stock_utils import StockCodeUtil


_PREFIX_SYMBOL_RE = re.compile(r"^(SH|SZ|BJ)[0-9]{6}$")


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _json_array(value: Any) -> str:
    return json.dumps(value or [], ensure_ascii=False, default=str)


def _row_to_run(row: Any, *, prefix: str = "") -> dict[str, Any]:
    data = dict(row)
    return {
        "id": data[f"{prefix}id"],
        "candidateId": data[f"{prefix}candidate_id"],
        "status": data.get(f"{prefix}status") or "pending",
        "params": data.get(f"{prefix}params_json") or {},
        "metrics": data.get(f"{prefix}metrics_json"),
        "gateDecision": data.get(f"{prefix}gate_decision_json") or {},
        "reportUrl": data.get(f"{prefix}report_url"),
        "errorMessage": data.get(f"{prefix}error_message"),
        "startedAt": _iso(data.get(f"{prefix}started_at")),
        "completedAt": _iso(data.get(f"{prefix}completed_at")),
        "createdAt": _iso(data.get(f"{prefix}created_at")),
        "updatedAt": _iso(data.get(f"{prefix}updated_at")),
    }


def _row_to_factor_value(row: Any) -> dict[str, Any]:
    data = dict(row)
    return {
        "candidateId": data["candidate_id"],
        "runId": data["run_id"],
        "tradeDate": _iso(data.get("trade_date")),
        "symbol": data["symbol"],
        "factorValue": _float_or_none(data.get("factor_value")),
        "source": data.get("source") or "unknown",
        "createdAt": _iso(data.get("created_at")),
    }


def _normalize_factor_value_rows(rows: Iterable[Any]) -> tuple[list[dict[str, Any]], int]:
    normalized: list[dict[str, Any]] = []
    invalid_symbol_count = 0
    for row in rows or []:
        data = dict(row)
        symbol = StockCodeUtil.to_prefix(str(data.get("symbol") or "").strip())
        factor_value = _float_or_none(data.get("factor_value"))
        trade_date = data.get("trade_date")
        if not symbol or not _PREFIX_SYMBOL_RE.match(symbol):
            invalid_symbol_count += 1
            continue
        if factor_value is None or trade_date is None:
            continue
        normalized.append(
            {
                "trade_date": _iso(trade_date),
                "symbol": symbol,
                "factor_value": factor_value,
            }
        )
    return normalized, invalid_symbol_count


async def upsert_factor_values(
    session,
    *,
    tenant_id: str,
    user_id: str,
    candidate_id: str,
    run_id: str,
    rows: Iterable[Any],
    source: str,
) -> dict[str, Any]:
    """Normalize and idempotently upsert factor values for one evaluation run."""
    normalized_rows, invalid_symbol_count = _normalize_factor_value_rows(rows)
    if not normalized_rows:
        return {
            "inserted_values": 0,
            "invalid_symbol_count": invalid_symbol_count,
            "source": source,
        }
    result = await session.execute(
        text(
            """
            WITH incoming AS (
                SELECT
                    :candidate_id AS candidate_id,
                    :run_id AS run_id,
                    :tenant_id AS tenant_id,
                    :user_id AS user_id,
                    x.trade_date::date AS trade_date,
                    x.symbol AS symbol,
                    x.factor_value::double precision AS factor_value,
                    :data_source AS source
                FROM jsonb_to_recordset(CAST(:values_json AS JSONB))
                    AS x(trade_date TEXT, symbol TEXT, factor_value DOUBLE PRECISION)
            ),
            upserted AS (
                INSERT INTO qm_factor_values (
                    candidate_id, run_id, tenant_id, user_id, trade_date, symbol,
                    factor_value, source, created_at
                )
                SELECT
                    candidate_id, run_id, tenant_id, user_id, trade_date, symbol,
                    factor_value, source, NOW()
                FROM incoming
                ON CONFLICT (run_id, trade_date, symbol)
                DO UPDATE SET
                    factor_value = EXCLUDED.factor_value,
                    source = EXCLUDED.source
                RETURNING 1
            )
            SELECT COUNT(*) AS inserted_values FROM upserted
            """
        ),
        {
            "candidate_id": candidate_id,
            "run_id": run_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "values_json": _json_array(normalized_rows),
            "data_source": source,
        },
    )
    inserted = int((result.mappings().one()).get("inserted_values") or 0)
    return {
        "inserted_values": inserted,
        "invalid_symbol_count": invalid_symbol_count,
        "source": source,
    }


async def upsert_factor_values_from_select(
    session,
    *,
    tenant_id: str,
    user_id: str,
    candidate_id: str,
    run_id: str,
    values_select_sql: str,
    values_params: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    """Idempotently upsert factor values produced by a trusted SQL SELECT."""
    result = await session.execute(
        text(
            f"""
            WITH incoming AS (
                {values_select_sql}
            ),
            normalized AS (
                SELECT
                    trade_date::date AS trade_date,
                    symbol::text AS symbol,
                    factor_value::double precision AS factor_value
                FROM incoming
                WHERE symbol ~ '^(SH|SZ|BJ)[0-9]{{6}}$'
                  AND factor_value IS NOT NULL
                  AND trade_date IS NOT NULL
            ),
            invalid AS (
                SELECT COUNT(*) AS invalid_symbol_count
                FROM incoming
                WHERE symbol IS NULL OR symbol !~ '^(SH|SZ|BJ)[0-9]{{6}}$'
            ),
            upserted AS (
                INSERT INTO qm_factor_values (
                    candidate_id, run_id, tenant_id, user_id, trade_date, symbol,
                    factor_value, source, created_at
                )
                SELECT
                    :candidate_id, :run_id, :tenant_id, :user_id, trade_date,
                    symbol, factor_value, :data_source, NOW()
                FROM normalized
                ON CONFLICT (run_id, trade_date, symbol)
                DO UPDATE SET
                    factor_value = EXCLUDED.factor_value,
                    source = EXCLUDED.source
                RETURNING 1
            )
            SELECT
                (SELECT COUNT(*) FROM upserted) AS inserted_values,
                (SELECT invalid_symbol_count FROM invalid) AS invalid_symbol_count
            """
        ),
        {
            **values_params,
            "candidate_id": candidate_id,
            "run_id": run_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "data_source": source,
        },
    )
    row = result.mappings().one()
    return {
        "inserted_values": int(row.get("inserted_values") or 0),
        "invalid_symbol_count": int(row.get("invalid_symbol_count") or 0),
        "source": source,
    }


async def list_factor_run_values(
    tenant_id: str,
    user_id: str,
    run_id: str,
    *,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 100), 1000))
    offset = max(0, int(offset or 0))
    params = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "run_id": run_id,
        "limit": limit,
        "offset": offset,
    }
    async with get_session(read_only=True) as session:
        run = (
            (
                await session.execute(
                    text(
                        """
                        SELECT *
                        FROM qm_factor_candidate_runs
                        WHERE id = :run_id
                          AND tenant_id = :tenant_id
                          AND user_id = :user_id
                        """
                    ),
                    params,
                )
            )
            .mappings()
            .first()
        )
        if not run:
            raise LookupError("factor evaluation run not found")
        summary = (
            (
                await session.execute(
                    text(
                        """
                        SELECT
                            COUNT(*) AS total,
                            COUNT(DISTINCT trade_date) AS trade_date_count,
                            COUNT(DISTINCT symbol) AS symbol_count,
                            MIN(trade_date) AS min_trade_date,
                            MAX(trade_date) AS max_trade_date,
                            MIN(factor_value) AS min_factor_value,
                            MAX(factor_value) AS max_factor_value,
                            COUNT(*) FILTER (WHERE factor_value IS NULL) AS null_value_count,
                            COUNT(*) FILTER (
                                WHERE symbol !~ '^(SH|SZ|BJ)[0-9]{6}$'
                            ) AS invalid_symbol_count,
                            COUNT(DISTINCT COALESCE(source, 'unknown')) AS source_count
                        FROM qm_factor_values
                        WHERE run_id = :run_id
                          AND tenant_id = :tenant_id
                          AND user_id = :user_id
                        """
                    ),
                    params,
                )
            )
            .mappings()
            .one()
        )
        invalid_symbol_rows = (
            (
                await session.execute(
                    text(
                        """
                        SELECT DISTINCT symbol
                        FROM qm_factor_values
                        WHERE run_id = :run_id
                          AND tenant_id = :tenant_id
                          AND user_id = :user_id
                          AND symbol !~ '^(SH|SZ|BJ)[0-9]{6}$'
                        ORDER BY symbol ASC
                        LIMIT 20
                        """
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        source_distribution_rows = (
            (
                await session.execute(
                    text(
                        """
                        SELECT COALESCE(source, 'unknown') AS source, COUNT(*) AS count
                        FROM qm_factor_values
                        WHERE run_id = :run_id
                          AND tenant_id = :tenant_id
                          AND user_id = :user_id
                        GROUP BY COALESCE(source, 'unknown')
                        ORDER BY count DESC, source ASC
                        LIMIT 10
                        """
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        recent_date_distribution_rows = (
            (
                await session.execute(
                    text(
                        """
                        SELECT trade_date, COUNT(*) AS count
                        FROM qm_factor_values
                        WHERE run_id = :run_id
                          AND tenant_id = :tenant_id
                          AND user_id = :user_id
                        GROUP BY trade_date
                        ORDER BY trade_date DESC
                        LIMIT 10
                        """
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        rows = (
            (
                await session.execute(
                    text(
                        """
                        SELECT *
                        FROM qm_factor_values
                        WHERE run_id = :run_id
                          AND tenant_id = :tenant_id
                          AND user_id = :user_id
                        ORDER BY trade_date DESC, symbol ASC
                        LIMIT :limit OFFSET :offset
                        """
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
    total = int(summary.get("total") or 0)
    return {
        "run": _row_to_run(run),
        "summary": {
            "total": total,
            "tradeDateCount": int(summary.get("trade_date_count") or 0),
            "symbolCount": int(summary.get("symbol_count") or 0),
            "minTradeDate": _iso(summary.get("min_trade_date")),
            "maxTradeDate": _iso(summary.get("max_trade_date")),
            "minFactorValue": _float_or_none(summary.get("min_factor_value")),
            "maxFactorValue": _float_or_none(summary.get("max_factor_value")),
            "nullValueCount": int(summary.get("null_value_count") or 0),
            "invalidSymbolCount": int(summary.get("invalid_symbol_count") or 0),
            "sourceCount": int(summary.get("source_count") or 0),
            "invalidSymbolSamples": [
                str(row.get("symbol"))
                for row in invalid_symbol_rows
                if row.get("symbol") is not None
            ],
            "sourceDistribution": [
                {
                    "source": str(row.get("source") or "unknown"),
                    "count": int(row.get("count") or 0),
                }
                for row in source_distribution_rows
            ],
            "recentDateDistribution": [
                {
                    "tradeDate": _iso(row.get("trade_date")),
                    "count": int(row.get("count") or 0),
                }
                for row in recent_date_distribution_rows
            ],
        },
        "items": [_row_to_factor_value(row) for row in rows],
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(rows),
            "hasMore": offset + len(rows) < total,
        },
    }
