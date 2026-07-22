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

from backend.services.engine.momentum_tail_alpha.artifact import validate_artifact  # noqa: E402
from backend.services.engine.momentum_tail_alpha.engine import (  # noqa: E402
    diagnostic_spec, execute_diagnostic, recover_source, replay_diagnostic,
)
from backend.services.engine.tushare_agent_experiment.data import load_authority_bundle  # noqa: E402


INSPECT = {
    "inspect-quantiles": "momentum_quantile_return_report",
    "inspect-tail": "momentum_quantile_return_report",
    "inspect-2023": "momentum_quantile_return_report",
    "inspect-style": "momentum_tail_style_exposure",
    "inspect-transition": "momentum_rank_transition_report",
    "inspect-report": "momentum_tail_alpha_diagnostic",
    "inspect-classification": "momentum_tail_signal_classification",
}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="QM2 Signal-D tail-alpha diagnostic")
    value.add_argument("--artifact-runtime-mode", choices=("store_required",), default="store_required")
    value.add_argument("--store-root", type=Path)
    value.add_argument("--work-root", type=Path, default=Path("/private/tmp/qm2-r1-009"))
    commands = value.add_subparsers(dest="command", required=True)
    for command in ("validate-spec", "execute", "validate-study"):
        commands.add_parser(command)
    for command in INSPECT:
        item = commands.add_parser(command)
        item.add_argument("artifact_id")
    return value


def bundle(args):
    return load_authority_bundle(authority_path=ROOT / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
                                 work_root=args.work_root / "cli-authority", store_root=args.store_root)


def inspect(args) -> dict:
    source = bundle(args)
    expected = INSPECT[args.command]
    descriptor = source.store.find_by_artifact_id(args.artifact_id)
    if descriptor is None or descriptor.artifact_kind != expected:
        raise ValueError(f"Artifact not found with expected kind {expected}: {args.artifact_id}")
    destination = args.work_root / "inspect" / expected / args.artifact_id
    if destination.exists():
        shutil.rmtree(destination)
    source.store.materialize_artifact(descriptor.descriptor_id, destination)
    validation = validate_artifact(destination, args.artifact_id, expected)
    identity = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))["identity"]
    return {"status": "valid", "descriptor_id": descriptor.descriptor_id,
            "validation": validation, "identity": identity}


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "validate-spec":
            source = bundle(args)
            study, signal, _, _ = recover_source(source, args.work_root / "source")
            result = {"status": "valid", "spec": diagnostic_spec(study, signal)}
        elif args.command == "execute":
            result = execute_diagnostic(repository_root=ROOT, work_root=args.work_root, store_root=args.store_root)
        elif args.command == "validate-study":
            result = replay_diagnostic(repository_root=ROOT, work_root=args.work_root, store_root=args.store_root)
        else:
            result = inspect(args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error_code": type(exc).__name__,
                          "safe_summary": str(exc)[:500]}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
