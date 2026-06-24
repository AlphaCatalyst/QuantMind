from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from io import StringIO

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.services.engine.research.quantgpt_mapping import normalize_quantgpt_symbol


@dataclass(frozen=True)
class SmokeResult:
    status: str
    source: str
    symbol_count: int
    row_count: int
    normalized_symbol_rate: float
    non_empty_value_rate: float
    repeat_count: int
    reproducible: bool
    start_date: str | None
    end_date: str | None
    fingerprints: dict[str, str]
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
    table_lines = [
        line for line in lines if line.startswith("|") and line.endswith("|")
    ]
    if len(table_lines) < 3:
        return []
    header = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
    data_lines = [
        line for line in table_lines[2:] if not re.fullmatch(r"\|[\s:\-|]+\|", line)
    ]
    csv_text = "\n".join(
        ",".join(cell.strip() for cell in line.strip("|").split("|"))
        for line in data_lines
    )
    reader = csv.reader(StringIO(csv_text))
    return [dict(zip(header, row, strict=False)) for row in reader]


def _normalized_ohlcv_rows(
    symbol: str, rows: list[dict[str, str]]
) -> list[dict[str, str]]:
    normalized_symbol = normalize_quantgpt_symbol(symbol)
    normalized_rows: list[dict[str, str]] = []
    for row in rows:
        row_date = str(row.get("date") or row.get("time") or "")[:10]
        if not row_date:
            continue
        normalized_rows.append(
            {
                "date": row_date,
                "symbol": normalized_symbol,
                "open": str(row.get("open") or "").strip(),
                "high": str(row.get("high") or "").strip(),
                "low": str(row.get("low") or "").strip(),
                "close": str(
                    row.get("close") or row.get("last") or row.get("price") or ""
                ).strip(),
                "volume": str(row.get("volume") or "").strip(),
            }
        )
    return sorted(normalized_rows, key=lambda item: item["date"])


def _ohlcv_fingerprint(symbol: str, rows: list[dict[str, str]]) -> str:
    payload = json.dumps(
        _normalized_ohlcv_rows(symbol, rows),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_smoke(symbols: list[str], limit: int, repeat: int = 2) -> SmokeResult:
    errors: list[str] = []
    total_rows = 0
    normalized_symbols = 0
    non_empty_values = 0
    dates: list[str] = []
    fingerprints: dict[str, str] = {}
    reproducible = True
    repeat_count = max(1, int(repeat or 1))

    for symbol in symbols:
        try:
            normalized = normalize_quantgpt_symbol(symbol)
        except Exception as exc:
            errors.append(f"{symbol}: invalid input symbol: {exc}")
            continue

        first_rows: list[dict[str, str]] | None = None
        first_fingerprint: str | None = None
        for attempt in range(repeat_count):
            try:
                rows = _markdown_table_to_rows(_run_westock_kline(normalized, limit))
            except Exception as exc:
                errors.append(f"{normalized}: westock-data kline failed: {exc}")
                reproducible = False
                continue

            if not rows:
                errors.append(f"{normalized}: no kline rows returned")
                reproducible = False
                continue

            fingerprint = _ohlcv_fingerprint(normalized, rows)
            if attempt == 0:
                first_rows = rows
                first_fingerprint = fingerprint
                fingerprints[normalized] = fingerprint
            elif fingerprint != first_fingerprint:
                reproducible = False
                errors.append(f"{normalized}: repeated-run fingerprint mismatch")

        if not first_rows:
            continue

        for row in first_rows:
            total_rows += 1
            try:
                normalize_quantgpt_symbol(row.get("code") or normalized)
                normalized_symbols += 1
            except Exception:
                errors.append(
                    f"{normalized}: invalid output symbol {row.get('code')!r}"
                )
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
        if total_rows > 0
        and normalized_rate == 1.0
        and non_empty_rate >= 0.9
        and reproducible
        else "failed"
    )
    return SmokeResult(
        status=status,
        source="westock-data",
        symbol_count=len(symbols),
        row_count=total_rows,
        normalized_symbol_rate=round(normalized_rate, 6),
        non_empty_value_rate=round(non_empty_rate, 6),
        repeat_count=repeat_count,
        reproducible=reproducible,
        start_date=min(dates) if dates else None,
        end_date=max(dates) if dates else None,
        fingerprints=fingerprints,
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
    parser.add_argument(
        "--repeat",
        type=int,
        default=2,
        help="Repeat each read and compare normalized OHLCV fingerprints.",
    )
    args = parser.parse_args()

    symbols = [item.strip() for item in args.symbols.split(",") if item.strip()]
    result = run_smoke(symbols=symbols, limit=args.limit, repeat=args.repeat)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
