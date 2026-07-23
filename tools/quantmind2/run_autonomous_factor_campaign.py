#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.autonomous_factor_campaign import (  # noqa: E402
    AutonomousFactorCampaignSpecV1,
    create_campaign_spec,
    execute_campaign,
    inspect_campaign,
    replay_campaign,
    resume_campaign,
    validate_campaign,
)
from backend.services.engine.autonomous_factor_campaign.planner import plan_next_round  # noqa: E402
from backend.services.engine.autonomous_factor_campaign.repository import CampaignRepository  # noqa: E402
from backend.services.engine.artifact_store.config import resolve_config  # noqa: E402
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore  # noqa: E402


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="QuantMind 2.0 autonomous bounded factor campaign")
    value.add_argument("--store-root", type=Path)
    value.add_argument("--work-root", type=Path, default=Path("/private/tmp/qm2-r2-001"))
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("create-spec")
    validate_spec = commands.add_parser("validate-spec")
    validate_spec.add_argument("campaign_id")
    plan = commands.add_parser("plan")
    plan.add_argument("campaign_id")
    for name in ("execute", "resume", "pause", "inspect", "inspect-memory", "inspect-budget",
                 "report", "validate-campaign", "replay"):
        command = commands.add_parser(name)
        command.add_argument("--campaign-id", required=True)
    for name in ("inspect-round", "inspect-candidate", "inspect-near-miss"):
        command = commands.add_parser(name)
        command.add_argument("artifact_id")
    return value


def _repository(args) -> CampaignRepository:
    store = FileSystemResearchArtifactStore(resolve_config(args.store_root))
    store.validate_format()
    return CampaignRepository(store, args.work_root / "domain", args.work_root / "inspect")


def _inspect_artifact(args) -> dict:
    return _repository(args).identity(args.artifact_id)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    common = {"repository_root": ROOT, "work_root": args.work_root, "store_root": args.store_root}
    try:
        if args.command == "create-spec":
            result = create_campaign_spec(**common)
        elif args.command == "validate-spec":
            result = _repository(args).find_spec(args.campaign_id) | {"status": "valid"}
        elif args.command == "plan":
            state = inspect_campaign(campaign_id=args.campaign_id, **common)
            result = plan_next_round(state["memory"], state["budget_usage"]["rounds"] + 1)
        elif args.command == "execute":
            result = execute_campaign(campaign_id=args.campaign_id, **common)
        elif args.command == "resume":
            result = resume_campaign(campaign_id=args.campaign_id, **common)
        elif args.command == "pause":
            marker = args.work_root / "pause" / args.campaign_id
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("pause after current round\n", encoding="utf-8")
            state = inspect_campaign(campaign_id=args.campaign_id, **common)
            result = {"status": "pause_requested", "campaign_state": state["state"],
                      "pause_marker": str(marker)}
        elif args.command == "inspect":
            result = inspect_campaign(campaign_id=args.campaign_id, **common)
        elif args.command == "inspect-memory":
            state = inspect_campaign(campaign_id=args.campaign_id, **common)
            result = state["memory"]
        elif args.command == "inspect-budget":
            state = inspect_campaign(campaign_id=args.campaign_id, **common)
            result = state["budget_usage"]
        elif args.command == "report":
            state = inspect_campaign(campaign_id=args.campaign_id, **common)
            result = _repository(args).identity(state["report_id"]) if state.get("report_id") else {"status": "not_available"}
        elif args.command == "validate-campaign":
            result = validate_campaign(campaign_id=args.campaign_id, **common)
        elif args.command == "replay":
            result = replay_campaign(campaign_id=args.campaign_id, **common)
        else:
            result = _inspect_artifact(args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error_code": type(exc).__name__,
                          "safe_summary": str(exc)[:300]}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
