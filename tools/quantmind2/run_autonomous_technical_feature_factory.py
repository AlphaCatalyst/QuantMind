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
from backend.services.engine.autonomous_technical_feature_factory import (  # noqa: E402
    audit_and_build_research_space,
    create_factory_spec,
    execute_factory,
    execute_factory_v2,
    inspect_factory,
    inspect_factory_v2,
    replay_factory,
    replay_factory_v2,
    validate_factory,
    validate_factory_v2,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="QuantMind autonomous technical Terminal Feature Factory")
    value.add_argument("--store-root", type=Path)
    value.add_argument("--work-root", type=Path, default=Path("/private/tmp/qm2-r2-004-feature-factory"))
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("create-spec")
    commands.add_parser("audit-operators")
    commands.add_parser("build-primitives")
    commands.add_parser("create-v2-factory-spec")
    for name in ("validate-spec", "plan", "execute", "resume", "validate-factory", "replay"):
        command = commands.add_parser(name)
        command.add_argument("--factory-spec-id", required=True)
    for name in ("validate-operator", "execute-v2-factory", "inspect-catalog-v3"):
        command = commands.add_parser(name)
        command.add_argument("--factory-spec-id", required=True)
    for name in (
        "inspect-proposal", "inspect-admission", "inspect-feature",
        "inspect-novelty", "inspect-catalog",
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
            result = create_factory_spec(**common)
        elif args.command in {
            "audit-operators", "build-primitives", "create-v2-factory-spec",
        }:
            result = audit_and_build_research_space(**common)
        elif args.command == "execute-v2-factory":
            result = execute_factory_v2(factory_spec_id=args.factory_spec_id, **common)
        elif args.command == "validate-operator":
            result = validate_factory_v2(factory_spec_id=args.factory_spec_id, **common)
        elif args.command == "inspect-catalog-v3":
            result = inspect_factory_v2(factory_spec_id=args.factory_spec_id, **common)
        elif args.command == "validate-spec":
            result = _repository(args).identity(args.factory_spec_id) | {"status": "valid"}
        elif args.command in {"execute", "resume"}:
            result = execute_factory(factory_spec_id=args.factory_spec_id, **common)
        elif args.command == "validate-factory":
            result = validate_factory(factory_spec_id=args.factory_spec_id, **common)
        elif args.command == "replay":
            result = replay_factory(factory_spec_id=args.factory_spec_id, **common)
        elif args.command == "plan":
            result = {
                "status": "planned", "factory_spec_id": args.factory_spec_id,
                "next_phase": "feature_agent_proposal",
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
