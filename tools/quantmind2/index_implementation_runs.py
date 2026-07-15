#!/usr/bin/env python3
"""Validate and index committed QuantMind 2.0 Implementation Runs."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, is_dataclass
from enum import Enum
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.api.project_knowledge.indexing import (  # noqa: E402
    GitSnapshot,
    ImplementationIndexError,
    ImplementationRunPlanner,
    LedgerIndexer,
    bind_repository,
)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (Path, Enum)):
        return str(value.value if isinstance(value, Enum) else value)
    return value


def _plan_summary(plan) -> dict[str, Any]:  # noqa: ANN001
    runs = []
    for analyzed in plan.runs:
        gaps = analyzed.domain_build.gaps if analyzed.domain_build else ()
        runs.append(
            {
                "run_id": analyzed.discovered.run_id,
                "manifest_path": analyzed.discovered.manifest_path,
                "containing_commit": analyzed.evidence.containing_commit,
                "source_status": analyzed.evidence.source_status,
                "resolved_status": analyzed.evidence.resolved_status,
                "validated": analyzed.validated,
                "indexable": analyzed.indexable,
                "mandatory_failures": [
                    check.name
                    for check in analyzed.evidence.checks
                    if check.mandatory and not check.passed
                ],
                "evidence_gaps": [_jsonable(gap) for gap in gaps],
                "errors": list(analyzed.errors),
            }
        )
    return {
        "repository_id": plan.repository_id,
        "ref_commit": plan.ref_commit,
        "discovered": plan.discovered_count,
        "validated": plan.validated_count,
        "indexable": plan.indexable_count,
        "runs": runs,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Git-authoritative Implementation Ledger indexer"
    )
    parser.add_argument("command", choices=("plan", "validate", "status", "index"))
    parser.add_argument("--repository-id", required=True)
    parser.add_argument("--repository-path", required=True)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--run-id")
    parser.add_argument("--output-json", action="store_true")
    return parser


def _emit(payload: Any) -> None:
    print(json.dumps(_jsonable(payload), ensure_ascii=False, indent=2, sort_keys=True))


async def _database_command(command: str, plan) -> Any:  # noqa: ANN001
    # Import persistence only after the complete Git validation pass. This
    # keeps plan/validate independent of SQLAlchemy and guarantees that an
    # invalid plan cannot open a database connection.
    if command == "index":
        bundles = LedgerIndexer.require_indexable(plan)
    else:
        bundles = ()
    from backend.services.api.project_knowledge.repositories import (  # noqa: PLC0415
        ledger_unit_of_work_factory,
    )

    indexer = LedgerIndexer(ledger_unit_of_work_factory)
    if command == "status":
        return await indexer.status(plan)
    return await indexer.index_bundles(
        repository_id=plan.repository_id,
        ref_commit=plan.ref_commit,
        discovered=plan.discovered_count,
        validated=plan.validated_count,
        bundles=bundles,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        binding = bind_repository(args.repository_id, args.repository_path)
        plan = ImplementationRunPlanner(GitSnapshot(binding, args.ref)).plan(args.run_id)
        if args.command == "plan":
            _emit(_plan_summary(plan))
            return 0
        if args.command == "validate":
            summary = _plan_summary(plan)
            summary["valid"] = plan.validated_count == plan.discovered_count
            _emit(summary)
            return 0 if summary["valid"] else 2
        result = asyncio.run(_database_command(args.command, plan))
        _emit(result)
        return 0
    except ImplementationIndexError as exc:
        _emit(
            {
                "error_code": exc.error_code,
                "message": exc.message,
                "run_id": exc.run_id,
                "check": exc.check,
            }
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
