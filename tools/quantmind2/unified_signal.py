#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.unified_signal import build_unified_signal, parse_spec, validate_signal_artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="QuantMind 2.0 Unified Signal v1")
    parser.add_argument("--artifact-runtime-mode", default="store_required", choices=["store_required"])
    parser.add_argument("--store-root", default="~/.quantmind2/artifact-store/v1")
    parser.add_argument("--cache-root", default=".quantmind2-cache")
    commands = parser.add_subparsers(dest="command", required=True)
    validate_spec = commands.add_parser("validate-spec")
    validate_spec.add_argument("spec")
    build = commands.add_parser("build")
    build.add_argument("spec")
    build.add_argument("--source-map", required=True, help="JSON map of source artifact ID to verified materialized directory")
    build.add_argument("--output-root", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("path")
    validate.add_argument("artifact_id")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("path")
    args = parser.parse_args()
    if args.command == "validate-spec":
        result = {"status": "valid", "unified_signal_spec_id": __import__("backend.services.engine.unified_signal.service", fromlist=["signal_spec_id"]).signal_spec_id(parse_spec(json.loads(Path(args.spec).read_text())))}
    elif args.command == "build":
        spec = parse_spec(json.loads(Path(args.spec).read_text()))
        sources = {key: Path(value) for key, value in json.loads(Path(args.source_map).read_text()).items()}
        result = build_unified_signal(spec, sources, Path(args.output_root))
    elif args.command == "validate":
        result = validate_signal_artifact(Path(args.path), args.artifact_id)
    else:
        root = Path(args.path)
        result = {"manifest": json.loads((root / "manifest.json").read_text()), "quality": json.loads((root / "quality.json").read_text())}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
