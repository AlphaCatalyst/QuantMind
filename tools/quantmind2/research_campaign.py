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
from backend.services.engine.artifact_runtime import (
    inspect_campaign_replay,
    prepare_campaign_config,
    publish_campaign_execution,
    replay_research_campaign,
)
from backend.services.engine.artifact_runtime.cli import add_runtime_arguments, runtime_context_from_args
from backend.services.engine.artifact_runtime.enums import ArtifactRuntimeMode
from backend.services.engine.artifact_runtime.errors import ArtifactResolutionError

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
    add_runtime_arguments(parser)
    sub = parser.add_subparsers(dest="command", required=True)
    goal = sub.add_parser("validate-goal"); goal.add_argument("goal")
    for name in ("plan", "execute"):
        item = sub.add_parser(name); item.add_argument("goal"); item.add_argument("--runtime-root")
        item.add_argument("--agent", choices=("baseline", "codex"), default="baseline")
        item.add_argument("--codex-executable", default="codex"); item.add_argument("--model", default="gpt-5.6-terra")
        item.add_argument("--timeout", type=int, default=180)
    for name in ("validate-campaign", "inspect", "inspect-memory"):
        item = sub.add_parser(name); item.add_argument("campaign_id"); item.add_argument("--runtime-root")
    args = parser.parse_args(argv)
    runtime = runtime_context_from_args(args)
    if args.command == "validate-goal":
        parsed = parse_goal(args.goal); _json({"status": "valid", "goal_id": parsed.goal_id}); return 0
    if args.command in {"plan", "execute"}:
        parsed = parse_goal(args.goal); budget = ResearchCampaignBudget()
        if args.runtime_root is None:
            args.runtime_root = str(runtime.cache_root / "campaign-execution")
        config = _config(args); agent = _agent(args)
        planned_id = campaign_id(parsed, budget, config, agent.provider_id, agent.model_id)
        if args.command == "plan":
            _json({"campaign_id": planned_id,
                "agent": {"provider_id": agent.provider_id, "model_id": agent.model_id}, "budget": asdict(budget),
                "development_protocol": "adaptive-development-2025-v1-contaminated",
                "registry_snapshot_id": config.registry_snapshot_id, "agent_called": False}); return 0
        if runtime.policy.mode is not ArtifactRuntimeMode.LEGACY_LOCAL:
            try:
                _json(inspect_campaign_replay(replay_research_campaign(runtime, planned_id)))
                return 0
            except ArtifactResolutionError:
                pass
            config = prepare_campaign_config(
                runtime,
                snapshot_id=DEFAULTS["snapshot_id"],
                validation_dataset_id=DEFAULTS["validation_dataset_id"],
                registry_snapshot_id=DEFAULTS["registry_snapshot_id"],
                execution_root=args.runtime_root,
            )
            completed = run_campaign(parsed, budget, agent, config)
            _json(publish_campaign_execution(runtime, config, completed))
            return 0
        _json(run_campaign(parsed, budget, agent, config)); return 0
    if runtime.policy.mode is not ArtifactRuntimeMode.LEGACY_LOCAL:
        replay = replay_research_campaign(runtime, args.campaign_id)
        if args.command == "inspect-memory":
            memory = json.loads((replay.resolved.materialized_root / "sanitized_memory.json").read_text())
            _json(memory); return 0
        payload = inspect_campaign_replay(replay)
        payload["status"] = "valid" if args.command == "validate-campaign" else "inspected"
        _json(payload); return 0
    if args.runtime_root is None:
        raise SystemExit("legacy_local Campaign access requires --runtime-root")
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
