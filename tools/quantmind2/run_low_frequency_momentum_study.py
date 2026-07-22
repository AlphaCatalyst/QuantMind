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

from backend.services.engine.low_frequency_momentum.artifact import validate_artifact  # noqa: E402
from backend.services.engine.low_frequency_momentum.engine import (  # noqa: E402
    _execution_protocol, _signal_spec, _source_matrix, execute_study, replay_study,
)
from backend.services.engine.low_frequency_momentum.protocol import (  # noqa: E402
    ANNUAL_PERIODS, ELIGIBILITY, FULL_PERIOD, PROTOCOLS, REPORT_PERIODS, SIGNALS,
)
from backend.services.engine.tushare_agent_experiment.data import load_authority_bundle  # noqa: E402


INSPECT = {
    "inspect-signal": "low_frequency_momentum_signal_spec",
    "inspect-annual-result": "low_frequency_momentum_annual_result",
    "inspect-turnover": "low_frequency_momentum_study",
    "inspect-holdings": "low_frequency_momentum_study",
    "inspect-candidate": "low_frequency_momentum_candidate_lock",
    "inspect-report": "low_frequency_momentum_report",
    "inspect-assessment": "low_frequency_momentum_assessment",
}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="QM2 low-frequency momentum and turnover-control study")
    value.add_argument("--artifact-runtime-mode", choices=("store_required",), default="store_required")
    value.add_argument("--store-root", type=Path)
    value.add_argument("--work-root", type=Path, default=Path("/private/tmp/qm2-r1-008"))
    commands = value.add_subparsers(dest="command", required=True)
    for command in ("validate-signal-specs", "validate-protocol", "plan", "execute", "validate-study"):
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
        if args.command == "validate-signal-specs":
            source = bundle(args)
            matrix, dataset = _source_matrix(source, args.work_root / "validation-source")
            result = {name: _signal_spec(name, matrix, dataset, source.authority)[0] for name in SIGNALS}
            result = {"status": "valid", "signal_count": len(result),
                      "quality": {name: value["quality"] for name, value in result.items()}}
        elif args.command == "validate-protocol":
            result = {"status": "valid", "protocol": _execution_protocol()}
        elif args.command == "plan":
            result = {"status": "planned", "signals": SIGNALS, "protocols": PROTOCOLS,
                      "annual_periods": ANNUAL_PERIODS, "full_period": FULL_PERIOD,
                      "report_periods": REPORT_PERIODS, "eligibility": ELIGIBILITY,
                      "expected_annual_qlib_calls": 32, "expected_full_period_qlib_calls": 8,
                      "agent_calls": 0, "factor_optimization_calls": 0,
                      "strategy_optimization_calls": 0, "combined_optimization_calls": 0,
                      "network_calls": 0, "third_frequency_tested": False}
        elif args.command == "execute":
            result = execute_study(repository_root=ROOT, work_root=args.work_root, store_root=args.store_root)
        elif args.command == "validate-study":
            result = replay_study(repository_root=ROOT, work_root=args.work_root, store_root=args.store_root)
        else:
            result = inspect(args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error_code": type(exc).__name__, "safe_summary": str(exc)[:500]},
                         ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
