#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.momentum_factor_iteration.artifact import validate_artifact  # noqa: E402
from backend.services.engine.momentum_factor_iteration.engine import execute_experiment, replay_experiment  # noqa: E402
from backend.services.engine.momentum_factor_iteration.features import catalog_payload, compute_features, quality_report  # noqa: E402
from backend.services.engine.momentum_factor_iteration.protocol import BUDGET, FOLDS, FORMAL_STRATEGY, ROUND_THEMES  # noqa: E402
from backend.services.engine.tushare_agent_experiment.data import load_authority_bundle  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QM2 multi-family Momentum Factor iteration v1")
    parser.add_argument("--artifact-runtime-mode", choices=("store_required",), default="store_required")
    parser.add_argument("--store-root", type=Path)
    parser.add_argument("--work-root", type=Path, default=Path("/private/tmp/qm2-r1-002"))
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate-feature-catalog", "build-features", "plan", "execute", "validate-experiment",
                    "inspect-family", "inspect-candidates", "inspect-ensemble", "inspect-assessment"):
        sub = commands.add_parser(command)
        if command == "inspect-family":
            sub.add_argument("family", nargs="?")
    inspect_round = commands.add_parser("inspect-round")
    inspect_round.add_argument("round_result_id")
    return parser


def _bundle(args):
    return load_authority_bundle(
        authority_path=ROOT / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
        work_root=args.work_root / "cli-authority", store_root=args.store_root,
    )


def _inspect(store, artifact_id: str, root: Path) -> dict:
    descriptor = store.find_by_artifact_id(artifact_id)
    if descriptor is None:
        raise ValueError(f"Artifact not found: {artifact_id}")
    if root.exists():
        shutil.rmtree(root)
    store.materialize_artifact(descriptor.descriptor_id, root)
    validation = validate_artifact(root, artifact_id, descriptor.artifact_kind)
    identity = json.loads((root / "manifest.json").read_text(encoding="utf-8"))["identity"]
    return {"validation": validation, "identity": identity, "descriptor_id": descriptor.descriptor_id}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "plan":
            result = {"status": "planned", "folds": list(FOLDS), "budget": BUDGET.__dict__,
                      "round_themes": ROUND_THEMES, "strategy": FORMAL_STRATEGY}
        elif args.command in {"build-features", "validate-feature-catalog", "inspect-family"}:
            bundle = _bundle(args)
            features = compute_features(bundle.normalized, bundle.benchmark)
            quality = quality_report(features)
            catalog = catalog_payload()
            if args.command == "inspect-family":
                rows = catalog["features"]
                if args.family:
                    rows = [row for row in rows if row["family"] == args.family]
                result = {"status": "valid", "features": rows, "quality": {row["name"]: row for row in quality["rows"] if any(item["name"] == row["name"] for item in rows)}}
            else:
                result = {"status": "valid", "catalog": catalog, "quality": quality}
                if args.command == "build-features":
                    path = args.work_root / "feature-preview" / "features.parquet"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    features.to_parquet(path, index=False, compression="zstd")
                    result.update({"path": str(path), "row_count": len(features), "network_calls": 0})
        elif args.command == "execute":
            result = execute_experiment(repository_root=ROOT, work_root=args.work_root, store_root=args.store_root)
        elif args.command == "validate-experiment":
            result = replay_experiment(repository_root=ROOT, work_root=args.work_root, store_root=args.store_root)
        else:
            bundle = _bundle(args)
            if args.command == "inspect-round":
                result = _inspect(bundle.store, args.round_result_id, args.work_root / "inspect-round")
            else:
                kinds = {"inspect-candidates": "momentum_factor_candidate_lock", "inspect-ensemble": "momentum_factor_ensemble", "inspect-assessment": "momentum_iteration_assessment"}
                result = [_inspect(bundle.store, item.artifact_id, args.work_root / args.command / item.artifact_id)
                          for item in bundle.store.list_by_kind(kinds[args.command])]
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error_code": type(exc).__name__, "safe_summary": str(exc)[:300]}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
