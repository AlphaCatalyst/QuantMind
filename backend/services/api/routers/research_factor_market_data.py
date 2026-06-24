"""Local market data contract for factor research and QuantGPT adapters."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LocalMarketDataContract:
    table: str
    source: str
    required_columns: tuple[str, ...] = (
        "trade_date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
    )


def safe_local_market_table_name(name: str | None) -> str:
    table = str(name or "").strip() or "stock_daily_latest"
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        raise ValueError("invalid factor research data table")
    return table


def local_market_data_contract(name: str | None = None) -> LocalMarketDataContract:
    table = safe_local_market_table_name(name)
    return LocalMarketDataContract(table=table, source=f"local_{table}")


def prefix_symbol_sql(column: str = "symbol") -> str:
    column_expr = str(column or "symbol").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_\\.]*", column_expr):
        raise ValueError("invalid symbol column")
    return f"""CASE
                    WHEN UPPER({column_expr}) ~ '^[0-9]{{6}}\\.(SH|SS)$' THEN 'SH' || LEFT({column_expr}, 6)
                    WHEN UPPER({column_expr}) ~ '^[0-9]{{6}}\\.SZ$' THEN 'SZ' || LEFT({column_expr}, 6)
                    WHEN UPPER({column_expr}) ~ '^[0-9]{{6}}\\.BJ$' THEN 'BJ' || LEFT({column_expr}, 6)
                    ELSE UPPER({column_expr})
                END"""


def build_local_ohlcv_base_cte(
    table: str | None,
    *,
    cte_name: str = "base",
) -> str:
    contract = local_market_data_contract(table)
    return f"""
        {cte_name} AS (
            SELECT
                trade_date::date AS trade_date,
                {prefix_symbol_sql("symbol")} AS symbol,
                open::double precision AS open,
                high::double precision AS high,
                low::double precision AS low,
                close::double precision AS close,
                volume::double precision AS volume,
                (close::double precision * volume::double precision) AS amount,
                close::double precision AS vwap
            FROM {contract.table}
            WHERE trade_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
              AND open IS NOT NULL
              AND high IS NOT NULL
              AND low IS NOT NULL
              AND close IS NOT NULL
              AND volume IS NOT NULL
              AND volume > 0
        )
        """


def build_factor_values_cte(table: str | None, raw_value_sql: str) -> str:
    return f"""
        WITH {build_local_ohlcv_base_cte(table, cte_name="base").strip()},
        raw AS (
            SELECT
                trade_date,
                symbol,
                {raw_value_sql} AS raw_value,
                (
                    LEAD(close, :holding_period) OVER (PARTITION BY symbol ORDER BY trade_date)
                    / NULLIF(LEAD(close, 1) OVER (PARTITION BY symbol ORDER BY trade_date), 0)
                    - 1
                ) AS forward_return
            FROM base AS b
        ),
        ranked AS (
            SELECT
                trade_date,
                symbol,
                PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY raw_value) AS factor_value,
                forward_return
            FROM raw
            WHERE raw_value IS NOT NULL
              AND forward_return IS NOT NULL
        )
        """
