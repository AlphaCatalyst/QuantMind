#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.artifact_runtime import resolve_artifact, resolve_runtime_context
from backend.services.engine.strategy_optimization.artifact import validate_strategy_optimization_artifact
from backend.services.engine.strategy_optimization.engine import execute_study
from backend.services.engine.strategy_optimization.parser import parse_optimization_spec
from backend.services.engine.strategy_optimization.planner import plan_trials, study_id

NORMALIZED_BARS_ID = "tnb_311f8c6f7efe127f0891831502aa41e779c67f24d45a2b772ba80c613a9c73ec"
SOURCE_REGISTRY_ID = "srr_a2d226d4ca751100256a3d6332ed5576c29c40c53a3a78a634fbdffef74ea503"


def _context(args):
    return resolve_runtime_context(explicit_mode=args.artifact_runtime_mode, explicit_store_root=args.store_root, explicit_cache_root=args.cache_root)


def main() -> int:
    parser = argparse.ArgumentParser(description="QuantMind 2.0 Strategy Parameter Optimization v1")
    parser.add_argument("--artifact-runtime-mode", default="store_required", choices=["store_required"])
    parser.add_argument("--store-root", default="~/.quantmind2/artifact-store/v1")
    parser.add_argument("--cache-root", default=".quantmind2-cache/strategy-optimization")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("validate-spec"); p.add_argument("spec")
    p = commands.add_parser("plan"); p.add_argument("spec")
    p = commands.add_parser("execute"); p.add_argument("spec"); p.add_argument("--work-root", required=True); p.add_argument("--normalized-bars-id", default=NORMALIZED_BARS_ID); p.add_argument("--source-registry-id", default=SOURCE_REGISTRY_ID)
    p = commands.add_parser("validate-study"); p.add_argument("study_id")
    p = commands.add_parser("inspect"); p.add_argument("artifact_kind"); p.add_argument("artifact_id")
    p = commands.add_parser("list-trials"); p.add_argument("study_id")
    p = commands.add_parser("inspect-candidate"); p.add_argument("candidate_id")
    args = parser.parse_args()
    if args.command in {"validate-spec", "plan", "execute"}:
        spec = parse_optimization_spec(json.loads(Path(args.spec).read_text()))
    if args.command == "validate-spec":
        result = {"status": "valid", "strategy_optimization_study_id": study_id(spec)}
    elif args.command == "plan":
        trials = plan_trials(spec)
        result = {"strategy_optimization_study_id": study_id(spec), "trial_count": len(trials), "trials": [item.to_dict() for item in trials]}
    elif args.command == "execute":
        result = execute_study(spec, _context(args), Path(args.work_root), normalized_bars_id=args.normalized_bars_id, source_registry_id=args.source_registry_id)
    elif args.command == "validate-study":
        resolved = resolve_artifact(_context(args), "strategy_optimization_study", args.study_id)
        result = validate_strategy_optimization_artifact(resolved.materialized_root, args.study_id, "strategy_optimization_study")
    elif args.command == "list-trials":
        resolved = resolve_artifact(_context(args), "strategy_optimization_study", args.study_id)
        result = json.loads((resolved.materialized_root / "trial_index.json").read_text())
    else:
        kind = "strategy_parameter_candidate_lock" if args.command == "inspect-candidate" else args.artifact_kind
        artifact_id = args.candidate_id if args.command == "inspect-candidate" else args.artifact_id
        resolved = resolve_artifact(_context(args), kind, artifact_id)
        result = {p.name: json.loads(p.read_text()) for p in resolved.materialized_root.glob("*.json")}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
