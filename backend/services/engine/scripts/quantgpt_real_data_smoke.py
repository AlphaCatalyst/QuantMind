from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from io import StringIO

from backend.services.engine.research.quantgpt_mapping import normalize_quantgpt_symbol


@dataclass(frozen=True)
class SmokeResult:
    status: str
    source: str
    symbol_count: int
    row_count: int
    normalized_symbol_rate: float
    non_empty_value_rate: float
    start_date: str | None
    end_date: str | None
    errors: list[str]


def _run_westock_kline(symbol: str, limit: int) -> str:
    completed = subprocess.run(
        [
            "westock-data",
            "kline",
            symbol.lower(),
            "--period",
            "day",
            "--limit",
            str(limit),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout


def _markdown_table_to_rows(markdown: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    table_lines = [line for line in lines if line.startswith("|") and line.endswith("|")]
    if len(table_lines) < 3:
        return []
    header = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
    data_lines = [
        line
        for line in table_lines[2:]
        if not re.fullmatch(r"\|[\s:\-|]+\|", line)
    ]
    csv_text = "\n".join(
        ",".join(cell.strip() for cell in line.strip("|").split("|"))
        for line in data_lines
    )
    reader = csv.reader(StringIO(csv_text))
    return [dict(zip(header, row, strict=False)) for row in reader]


def run_smoke(symbols: list[str], limit: int) -> SmokeResult:
    errors: list[str] = []
    total_rows = 0
    normalized_symbols = 0
    non_empty_values = 0
    dates: list[str] = []

    for symbol in symbols:
        try:
            normalized = normalize_quantgpt_symbol(symbol)
        except Exception as exc:
            errors.append(f"{symbol}: invalid input symbol: {exc}")
            continue

        try:
            rows = _markdown_table_to_rows(_run_westock_kline(normalized, limit))
        except Exception as exc:
            errors.append(f"{normalized}: westock-data kline failed: {exc}")
            continue

        if not rows:
            errors.append(f"{normalized}: no kline rows returned")
            continue

        for row in rows:
            total_rows += 1
            try:
                normalize_quantgpt_symbol(row.get("code") or normalized)
                normalized_symbols += 1
            except Exception:
                errors.append(f"{normalized}: invalid output symbol {row.get('code')!r}")
            close_value = row.get("close") or row.get("last") or row.get("price")
            if close_value not in (None, "", "nan", "NaN"):
                non_empty_values += 1
            row_date = row.get("date") or row.get("time")
            if row_date:
                dates.append(str(row_date)[:10])

    normalized_rate = normalized_symbols / total_rows if total_rows else 0.0
    non_empty_rate = non_empty_values / total_rows if total_rows else 0.0
    status = (
        "passed"
        if total_rows > 0 and normalized_rate == 1.0 and non_empty_rate >= 0.9
        else "failed"
    )
    return SmokeResult(
        status=status,
        source="westock-data",
        symbol_count=len(symbols),
        row_count=total_rows,
        normalized_symbol_rate=round(normalized_rate, 6),
        non_empty_value_rate=round(non_empty_rate, 6),
        start_date=min(dates) if dates else None,
        end_date=max(dates) if dates else None,
        errors=errors,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only QuantGPT integration smoke test with real market data."
    )
    parser.add_argument(
        "--symbols",
        default="SH600519,SZ000001,SH600000",
        help="Comma-separated symbols in QuantMind prefix format.",
    )
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    symbols = [item.strip() for item in args.symbols.split(",") if item.strip()]
    result = run_smoke(symbols=symbols, limit=args.limit)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
