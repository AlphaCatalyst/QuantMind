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
from backend.services.engine.market_data.feature_snapshot import (  # noqa: E402
    LegacyFeatureSnapshotService,
)
from backend.services.engine.market_data.legacy_models import (  # noqa: E402
    LegacyFeatureRequest,
    LegacyFeatureSourceBinding,
)
from backend.services.engine.market_data.models import AdjustmentMode, DailyBarsRequest  # noqa: E402
from backend.services.engine.market_data.providers import (  # noqa: E402
    FakeMarketDataProvider,
    LegacyFeatureProvider,
    TongDaXinProvider,
)
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


def _legacy_provider(args: argparse.Namespace) -> LegacyFeatureProvider:
    binding = LegacyFeatureSourceBinding(
        source_id=args.source_id,
        local_root=args.source_root,
        loader_id="docker-training-load-local-parquet-v1",
    )
    return LegacyFeatureProvider(
        binding,
        args.catalog_path
        or ROOT / "config" / "features" / "model_training_feature_catalog_v1.json",
    )


def _legacy_years(value: str) -> tuple[int, ...]:
    return tuple(int(item.strip()) for item in value.split(",") if item.strip())


def _legacy_request(args: argparse.Namespace) -> LegacyFeatureRequest:
    symbols = tuple(item.strip() for item in (args.symbols or "").split(",") if item.strip())
    columns = tuple(item.strip() for item in (args.columns or "").split(",") if item.strip())
    return LegacyFeatureRequest(
        source_id=args.source_id,
        years=_legacy_years(args.years),
        start_date=date.fromisoformat(args.start),
        end_date=date.fromisoformat(args.end),
        symbols=symbols,
        columns=columns,
        include_labels=bool(args.include_labels),
        symbol_limit=None if symbols else args.symbol_limit,
    )


def _add_legacy_binding(command: argparse.ArgumentParser, *, years: bool = True) -> None:
    command.add_argument("--source-id", required=True)
    command.add_argument("--source-root", required=True, type=Path)
    command.add_argument("--catalog-path", type=Path)
    if years:
        command.add_argument("--years", required=True)


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
    legacy_audit = commands.add_parser("legacy-audit")
    _add_legacy_binding(legacy_audit)
    legacy_probe = commands.add_parser("legacy-probe")
    _add_legacy_binding(legacy_probe, years=False)
    legacy_snapshot = commands.add_parser("legacy-snapshot")
    _add_legacy_binding(legacy_snapshot)
    legacy_snapshot.add_argument("--start", required=True)
    legacy_snapshot.add_argument("--end", required=True)
    legacy_snapshot.add_argument("--symbols")
    legacy_snapshot.add_argument("--symbol-limit", type=int, default=100)
    legacy_snapshot.add_argument("--columns")
    legacy_snapshot.add_argument("--include-labels", action="store_true")
    legacy_snapshot.add_argument("--output-root", required=True, type=Path)
    legacy_validate = commands.add_parser("legacy-validate")
    _add_legacy_binding(legacy_validate, years=False)
    legacy_validate.add_argument("--snapshot-id", required=True)
    legacy_validate.add_argument("--output-root", required=True, type=Path)
    legacy_inspect = commands.add_parser("legacy-inspect")
    legacy_inspect.add_argument("--snapshot-id", required=True)
    legacy_inspect.add_argument("--output-root", required=True, type=Path)
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
        elif args.command in {"validate", "inspect"}:
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
        elif args.command == "legacy-probe":
            result = _legacy_provider(args).probe().to_dict()
        elif args.command == "legacy-audit":
            provider = _legacy_provider(args)
            inventory = provider.discover(_legacy_years(args.years))
            result = {
                "status": "audited",
                "production_loader": "docker/training/train.py::_load_local_parquet/load_data",
                "source_id": inventory.source_id,
                "loader_id": inventory.loader_id,
                "files": [
                    {
                        key: item[key]
                        for key in ("file_relative_path", "year", "size_bytes", "sha256", "row_count", "date_min", "date_max", "symbol_count")
                    }
                    for item in inventory.files
                ],
                "feature_count": len(inventory.schema.research_feature_columns),
                "label_columns": list(inventory.schema.label_columns),
                "unknown_columns": list(inventory.schema.unknown_columns),
            }
        elif args.command == "legacy-snapshot":
            result = LegacyFeatureSnapshotService(args.output_root).create(
                _legacy_provider(args), _legacy_request(args)
            )
            result = {key: value for key, value in result.items() if key != "manifest"}
        elif args.command == "legacy-validate":
            provider = _legacy_provider(args)
            result = LegacyFeatureSnapshotService(args.output_root).validate(
                args.snapshot_id, binding=provider.binding
            )
        else:
            root = args.output_root / "snapshots" / args.snapshot_id
            LegacyFeatureSnapshotService(args.output_root).validate(args.snapshot_id)
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            result = {
                "snapshot_id": manifest["snapshot_id"],
                "dataset_kind": manifest["dataset_kind"],
                "source_id": manifest["source_id"],
                "years": manifest["request"]["years"],
                "date_range": manifest["date_range"],
                "rows": manifest["row_count"],
                "symbols": manifest["symbol_count"],
                "dates": manifest["date_count"],
                "features": manifest["feature_count"],
                "labels": manifest["label_count"],
                "quality": manifest["quality_summary"],
            }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        return 0
    except (MarketDataError, ValueError, OSError) as exc:
        print(json.dumps({"status": "error", "error_type": type(exc).__name__, "message": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
