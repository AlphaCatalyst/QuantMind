#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.strategy_layer.artifact import validate_strategy_domain_artifact
from backend.services.engine.strategy_layer.result import publish_backtest_result
from backend.services.engine.strategy_layer.service import build_execution_plan, build_portfolio_target, parse_strategy_spec, strategy_spec_id


def main() -> int:
    parser = argparse.ArgumentParser(description="QuantMind 2.0 Strategy Layer v1")
    parser.add_argument("--artifact-runtime-mode", default="store_required", choices=["store_required"])
    parser.add_argument("--store-root", default="~/.quantmind2/artifact-store/v1")
    parser.add_argument("--cache-root", default=".quantmind2-cache")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("validate-spec"); p.add_argument("spec")
    p = commands.add_parser("plan"); p.add_argument("spec"); p.add_argument("--lifecycle-policy-id", required=True); p.add_argument("--termination-policy-id", required=True)
    p = commands.add_parser("build-targets"); p.add_argument("spec"); p.add_argument("signal"); p.add_argument("--output-root", required=True)
    p = commands.add_parser("backtest"); p.add_argument("spec"); p.add_argument("plan"); p.add_argument("target"); p.add_argument("--qlib-results-root", required=True); p.add_argument("--qlib-strategy-key", required=True); p.add_argument("--source-qlib-artifact-id", required=True); p.add_argument("--portfolio-target-artifact-id", required=True); p.add_argument("--output-root", required=True)
    p = commands.add_parser("validate-result"); p.add_argument("path"); p.add_argument("artifact_id"); p.add_argument("--kind", default="strategy_backtest_result")
    p = commands.add_parser("inspect"); p.add_argument("path")
    args = parser.parse_args()
    if args.command == "validate-spec":
        spec = parse_strategy_spec(json.loads(Path(args.spec).read_text())); result = {"status": "valid", "strategy_spec_id": strategy_spec_id(spec)}
    elif args.command == "plan":
        spec = parse_strategy_spec(json.loads(Path(args.spec).read_text())); result = build_execution_plan(spec, signal_artifact_id=spec.unified_signal_id, lifecycle_policy_id=args.lifecycle_policy_id, termination_policy_id=args.termination_policy_id)
    elif args.command == "build-targets":
        spec = parse_strategy_spec(json.loads(Path(args.spec).read_text())); result = build_portfolio_target(pd.read_parquet(args.signal), spec, Path(args.output_root))
    elif args.command == "backtest":
        spec_payload = json.loads(Path(args.spec).read_text()); result = publish_backtest_result(Path(args.output_root), strategy_spec=spec_payload, execution_plan=json.loads(Path(args.plan).read_text()), portfolio_target_path=Path(args.target), qlib_results_root=Path(args.qlib_results_root), qlib_strategy_key=args.qlib_strategy_key, source_qlib_artifact_id=args.source_qlib_artifact_id, portfolio_target_artifact_id=args.portfolio_target_artifact_id)
    elif args.command == "validate-result":
        result = validate_strategy_domain_artifact(Path(args.path), args.artifact_id, args.kind)
    else:
        root = Path(args.path); result = {name: json.loads((root / name).read_text()) for name in ("manifest.json", "canonicality.json", "metrics.json") if (root / name).is_file()}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
