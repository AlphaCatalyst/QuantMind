#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.artifact_store.config import resolve_config  # noqa: E402
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore  # noqa: E402
from backend.services.engine.autonomous_factor_campaign.repository import CampaignRepository  # noqa: E402
from backend.services.engine.archetype_alpha_program import (  # noqa: E402
    create_program_spec, execute_program, inspect_program, replay_program,
    resume_program, validate_program,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="QuantMind archetype-aware autonomous Alpha Program")
    value.add_argument("--store-root", type=Path)
    value.add_argument("--work-root", type=Path, default=Path("/private/tmp/qm2-r2-004-alpha-program"))
    commands = value.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-spec")
    create.add_argument("--feature-catalog-v2-id", required=True)
    for name in ("validate-spec", "plan", "execute-program", "resume-program", "validate-program", "replay-program"):
        command = commands.add_parser(name)
        command.add_argument("--program-id", required=True)
    for name in (
        "inspect-lane", "inspect-archetype", "inspect-shortlist",
        "inspect-validation", "inspect-multiple-testing", "inspect-survivor",
        "inspect-near-miss", "inspect-fresh-lock",
    ):
        command = commands.add_parser(name)
        command.add_argument("artifact_id")
    return value


def _repository(args) -> CampaignRepository:
    store = FileSystemResearchArtifactStore(resolve_config(args.store_root))
    store.validate_format()
    return CampaignRepository(store, args.work_root / "domain", args.work_root / "inspect")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    common = {"repository_root": ROOT, "work_root": args.work_root, "store_root": args.store_root}
    try:
        if args.command == "create-spec":
            result = create_program_spec(feature_catalog_v2_id=args.feature_catalog_v2_id, **common)
        elif args.command == "validate-spec":
            result = _repository(args).identity(args.program_id) | {"status": "valid"}
        elif args.command == "execute-program":
            result = execute_program(program_id=args.program_id, **common)
        elif args.command == "resume-program":
            result = resume_program(program_id=args.program_id, **common)
        elif args.command == "validate-program":
            result = validate_program(program_id=args.program_id, **common)
        elif args.command == "replay-program":
            result = replay_program(program_id=args.program_id, **common)
        elif args.command == "plan":
            result = {
                "status": "planned", "program_id": args.program_id,
                "next_phase": "adaptive_research",
            }
        else:
            result = _repository(args).identity(args.artifact_id)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({
            "status": "blocked", "error_code": type(exc).__name__,
            "safe_summary": str(exc)[:300],
        }, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
