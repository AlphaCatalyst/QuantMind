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

from backend.services.engine.artifact_store.config import resolve_config  # noqa: E402
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore  # noqa: E402
from backend.services.engine.expanded_factor_iteration.artifact import validate_artifact  # noqa: E402
from backend.services.engine.expanded_factor_iteration.audit import build_existing_factor_audit  # noqa: E402
from backend.services.engine.expanded_factor_iteration.engine import replay_experiment, run_experiment  # noqa: E402
from backend.services.engine.expanded_factor_iteration.features import (  # noqa: E402
    compute_feature_candidates,
    feature_contract,
    quality_and_selection,
)
from backend.services.engine.expanded_factor_iteration.protocol import BUDGET, FOLDS  # noqa: E402
from backend.services.engine.tushare_agent_experiment.data import load_authority_bundle  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QM2 Tushare expanded-feature Agent factor iteration v2")
    parser.add_argument("--artifact-runtime-mode", choices=("store_required",), default="store_required")
    parser.add_argument("--store-root", type=Path)
    parser.add_argument("--work-root", type=Path, default=Path("/private/tmp/qm2-r1-001-v2"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("audit-existing-factors")
    commands.add_parser("validate-feature-catalog")
    commands.add_parser("build-features")
    commands.add_parser("plan")
    commands.add_parser("execute")
    commands.add_parser("validate-experiment")
    inspect_round = commands.add_parser("inspect-round")
    inspect_round.add_argument("round_result_id")
    commands.add_parser("inspect-candidates")
    commands.add_parser("inspect-assessment")
    return parser


def _bundle(args):
    return load_authority_bundle(
        authority_path=ROOT / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
        work_root=args.work_root / "cli-authority",
        store_root=args.store_root,
    )


def _inspect(store, artifact_id: str, root: Path) -> dict:
    descriptor = store.find_by_artifact_id(artifact_id)
    if descriptor is None:
        raise ValueError(f"Artifact not found: {artifact_id}")
    if root.exists():
        shutil.rmtree(root)
    store.materialize_artifact(descriptor.descriptor_id, root)
    validation = validate_artifact(root, artifact_id, descriptor.artifact_kind)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    return {"validation": validation, "identity": manifest["identity"], "descriptor_id": descriptor.descriptor_id}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "plan":
            result = {"status": "planned", "folds": [item.__dict__ for item in FOLDS], "budget": BUDGET}
        elif args.command == "audit-existing-factors":
            bundle = _bundle(args)
            result = build_existing_factor_audit(bundle.store, args.work_root / "audit-cli")
        elif args.command in {"build-features", "validate-feature-catalog"}:
            bundle = _bundle(args)
            candidates = compute_feature_candidates(bundle.normalized, bundle.benchmark)
            quality, selected = quality_and_selection(candidates, 24)
            catalog = feature_contract(selected)
            result = {"status": "valid", "catalog": catalog, "quality": quality}
            if args.command == "build-features":
                output = candidates[candidates["trade_date"].between("2019-01-02", "2026-06-23")][["symbol", "trade_date", *selected]]
                path = args.work_root / "feature-preview" / "features.parquet"
                path.parent.mkdir(parents=True, exist_ok=True)
                output.to_parquet(path, index=False, compression="zstd")
                result.update({"path": str(path), "row_count": len(output), "network_calls": 0})
        elif args.command == "execute":
            result = run_experiment(repository_root=ROOT, work_root=args.work_root, store_root=args.store_root)
        elif args.command == "validate-experiment":
            result = replay_experiment(repository_root=ROOT, work_root=args.work_root, store_root=args.store_root)
        else:
            bundle = _bundle(args)
            if args.command == "inspect-round":
                result = _inspect(bundle.store, args.round_result_id, args.work_root / "inspect-round")
            elif args.command == "inspect-candidates":
                result = [
                    _inspect(bundle.store, item.artifact_id, args.work_root / "inspect-candidates" / item.artifact_id)
                    for item in bundle.store.list_by_kind("agent_factor_candidate_lock")
                ]
            else:
                descriptors = bundle.store.list_by_kind("agent_factor_iteration_assessment")
                result = [
                    _inspect(bundle.store, item.artifact_id, args.work_root / "inspect-assessment" / item.artifact_id)
                    for item in descriptors
                ]
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({
            "status": "blocked",
            "error_code": type(exc).__name__,
            "safe_summary": str(exc)[:300],
        }, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
