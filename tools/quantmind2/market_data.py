#!/usr/bin/env python3
"""Audit, probe, create, validate, and inspect QuantMind Dataset Snapshots."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.market_data.errors import MarketDataError  # noqa: E402
from backend.services.engine.market_data.models import AdjustmentMode, DailyBarsRequest  # noqa: E402
from backend.services.engine.market_data.providers import FakeMarketDataProvider, TongDaXinProvider  # noqa: E402
from backend.services.engine.market_data.snapshot import DatasetSnapshotService  # noqa: E402


def _provider(name: str):  # noqa: ANN202
    if name == "tongdaxin":
        return TongDaXinProvider()
    if name == "fake":
        return FakeMarketDataProvider()
    raise MarketDataError("unknown provider")


def _request(args: argparse.Namespace) -> DailyBarsRequest:
    return DailyBarsRequest(
        tuple(item.strip() for item in args.symbols.split(",") if item.strip()),
        date.fromisoformat(args.start), date.fromisoformat(args.end),
        adjustment_mode=AdjustmentMode(args.adjustment),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("audit")
    probe = commands.add_parser("probe")
    probe.add_argument("--provider", required=True, choices=("tongdaxin", "fake"))
    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("--provider", required=True, choices=("tongdaxin", "fake"))
    snapshot.add_argument("--symbols", required=True)
    snapshot.add_argument("--start", required=True)
    snapshot.add_argument("--end", required=True)
    snapshot.add_argument("--adjustment", required=True, choices=tuple(item.value for item in AdjustmentMode))
    snapshot.add_argument("--output-root", required=True, type=Path)
    for name in ("validate", "inspect"):
        command = commands.add_parser(name)
        command.add_argument("--snapshot-id", required=True)
        command.add_argument("--output-root", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "audit":
            result = {
                "status": "audited",
                "authoritative_target": "dataset_snapshot",
                "current_sources": ["remote_postgresql_push", "csmar_and_local_parquet", "qlib_binary", "legacy_tqcenter_scripts"],
                "training_source": "db/feature_snapshots/model_features_YYYY.parquet",
                "backtest_source": "QLIB_DATA_PATH or db/qlib_data",
                "tongdaxin_adapter": "optional proprietary tqcenter client",
            }
        elif args.command == "probe":
            result = _provider(args.provider).probe().to_dict()
        elif args.command == "snapshot":
            result = DatasetSnapshotService(args.output_root).create(_provider(args.provider), _request(args))
            result = {key: value for key, value in result.items() if key != "manifest"}
        else:
            service = DatasetSnapshotService(args.output_root)
            validation = service.validate(args.snapshot_id)
            if args.command == "validate":
                result = validation
            else:
                manifest = json.loads((args.output_root / "snapshots" / args.snapshot_id / "manifest.json").read_text())
                result = {
                    "snapshot_id": manifest["snapshot_id"], "provider_id": manifest["provider_id"],
                    "date_range": manifest["date_range"], "symbols": manifest["request"]["symbols"],
                    "rows": manifest["row_count"], "fields": [item["name"] for item in manifest["field_schema"]],
                    "quality": manifest["quality_summary"],
                }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        return 0
    except (MarketDataError, ValueError, OSError) as exc:
        print(json.dumps({"status": "error", "error_type": type(exc).__name__, "message": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
