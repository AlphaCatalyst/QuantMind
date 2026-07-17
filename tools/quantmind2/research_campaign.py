#!/usr/bin/env python3
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path: sys.path.insert(0, str(REPO))

from backend.services.engine.research_campaign import (BaselineResearchAgent, CodexResearchAgent,
    ResearchCampaignBudget, run_campaign, validate_campaign)
from backend.services.engine.research_campaign.artifact import campaign_id
from backend.services.engine.research_campaign.goal import parse_goal
from backend.services.engine.research_campaign.memory import sanitize_memory
from backend.services.engine.research_campaign.models import CampaignConfig
from backend.services.engine.factor_registry import validate_registry_snapshot

DEFAULTS = {
    "snapshot_root": "/private/tmp/qm2-p0-006-validation/snapshots",
    "snapshot_id": "ds_dd1defb79ddf2a81f057be9e34715cb04df340204d68338f73ab1ad4692e338f",
    "validation_root": "/private/tmp/qm2-p0-006-validation/data",
    "validation_dataset_id": "vd_1ac71a8b1bab36f7d4304fe13c14cbb936f073d0426b76e0c73096a819c3ed62",
    "registry_root": "/private/tmp/qm2-p0-007-registry",
    "registry_snapshot_id": "frs_436f4a966ea0c00ee2182c665813cd74cc13bb900a7022604ad9efc26849f2d9",
    "existing_optimization_root": "/private/tmp/qm2-p0-005-optimization",
}


def _json(value): print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def _config(args):
    root = Path(args.runtime_root)
    return CampaignConfig(str(root / "campaign-artifacts"), DEFAULTS["snapshot_root"], DEFAULTS["snapshot_id"],
        DEFAULTS["validation_root"], DEFAULTS["validation_dataset_id"], DEFAULTS["registry_root"],
        DEFAULTS["registry_snapshot_id"], str(root / "factor-values"), str(root / "optimization"),
        DEFAULTS["existing_optimization_root"], str(root / "registry"))


def _agent(args):
    return BaselineResearchAgent() if args.agent == "baseline" else CodexResearchAgent(args.codex_executable, args.model, args.timeout)


def main(argv=None):
    parser = argparse.ArgumentParser(description="QuantMind 2.0 bounded Agent research campaign")
    sub = parser.add_subparsers(dest="command", required=True)
    goal = sub.add_parser("validate-goal"); goal.add_argument("goal")
    for name in ("plan", "execute"):
        item = sub.add_parser(name); item.add_argument("goal"); item.add_argument("--runtime-root", required=True)
        item.add_argument("--agent", choices=("baseline", "codex"), default="baseline")
        item.add_argument("--codex-executable", default="codex"); item.add_argument("--model", default="gpt-5.6-terra")
        item.add_argument("--timeout", type=int, default=180)
    for name in ("validate-campaign", "inspect", "inspect-memory"):
        item = sub.add_parser(name); item.add_argument("campaign_id"); item.add_argument("--runtime-root", required=True)
    args = parser.parse_args(argv)
    if args.command == "validate-goal":
        parsed = parse_goal(args.goal); _json({"status": "valid", "goal_id": parsed.goal_id}); return 0
    if args.command in {"plan", "execute"}:
        parsed = parse_goal(args.goal); budget = ResearchCampaignBudget(); config = _config(args); agent = _agent(args)
        if args.command == "plan":
            _json({"campaign_id": campaign_id(parsed, budget, config, agent.provider_id, agent.model_id),
                "agent": {"provider_id": agent.provider_id, "model_id": agent.model_id}, "budget": asdict(budget),
                "development_protocol": "adaptive-development-2025-v1-contaminated",
                "registry_snapshot_id": config.registry_snapshot_id, "agent_called": False}); return 0
        _json(run_campaign(parsed, budget, agent, config)); return 0
    artifact = validate_campaign(Path(args.runtime_root) / "campaign-artifacts", args.campaign_id)
    if args.command == "validate-campaign":
        memory = json.loads((Path(artifact["path"]) / "memory.json").read_text())
        for study_id in memory.get("optimization_studies", []):
            if not (Path(args.runtime_root) / "optimization" / study_id / "manifest.json").is_file():
                raise SystemExit(f"missing Optimization Study: {study_id}")
        after = artifact["result"]["registry_snapshot_after"]
        registry_root = Path(args.runtime_root) / "registry"
        if after != DEFAULTS["registry_snapshot_id"]: validate_registry_snapshot(registry_root, after)
        _json({"status": "valid", "campaign_id": args.campaign_id, "file_hashes_valid": True,
               "event_count": len(artifact["events"]), "result_id": artifact["result"]["result_id"]}); return 0
    path = Path(artifact["path"])
    if args.command == "inspect-memory":
        memory = json.loads((path / "sanitized_memory.json").read_text()); _json(memory); return 0
    result = artifact["result"]
    _json({key: result[key] for key in ("campaign_id", "provider_id", "model_id", "iterations", "agent_calls",
        "admitted_proposals", "failed_proposals", "total_trials", "failed_trials", "research_registered_added",
        "stop_reason", "registry_snapshot_before", "registry_snapshot_after")}); return 0


if __name__ == "__main__": raise SystemExit(main())
