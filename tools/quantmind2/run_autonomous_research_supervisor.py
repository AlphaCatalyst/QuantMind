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
from backend.services.engine.autonomous_research_supervisor import (  # noqa: E402
    create_supervisor_spec,
    execute_supervisor,
    run_multi_horizon_model_cycle,
    run_next_cross_sectional_alpha_batch,
    run_next_rolling_blind_batch,
    run_next_model_cycle,
    replay_next_research_cycle,
    replay_supervisor,
    run_next_research_cycle,
    validate_next_research_cycle,
    validate_supervisor,
)
from backend.services.engine.fresh_model_cohort import (  # noqa: E402
    inspect_artifact as inspect_fresh_model_artifact,
    replay_heartbeat as replay_fresh_model_heartbeat,
    run_fresh_heartbeat,
)


COMMANDS = (
    "create-spec", "validate-spec", "plan", "execute", "run-research-cycle",
    "update-market-data", "update-fresh-observations", "evaluate-fresh-cohorts",
    "inspect-ledger", "inspect-research-queue", "inspect-candidate",
    "inspect-fresh-lock", "inspect-cohort", "inspect-fresh-status",
    "pause", "resume", "validate-supervisor", "replay",
    "run-next-research-cycle", "inspect-research-space",
    "run-next-model-cycle", "inspect-model-candidate", "inspect-model-fresh-lock",
    "run-multi-horizon-model-cycle",
    "run-fresh-heartbeat", "replay-fresh-heartbeat",
    "inspect-model-cohort", "inspect-fresh-model",
    "inspect-fresh-predictions", "inspect-fresh-labels",
    "inspect-fresh-strategy", "inspect-fresh-multiple-testing",
    "run-next-rolling-blind-batch", "inspect-blind-windows",
    "run-next-cross-sectional-alpha-batch",
    "inspect-batch-lock", "inspect-blind-result", "inspect-blind-survivor",
    "inspect-search-exposure",
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="QuantMind autonomous research supervisor")
    value.add_argument("--store-root", type=Path)
    value.add_argument("--work-root", type=Path, default=Path("/private/tmp/qm2-r2-005-supervisor"))
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("create-spec")
    heartbeat = commands.add_parser("run-fresh-heartbeat")
    heartbeat.add_argument("--requested-through-date")
    commands.add_parser("replay-fresh-heartbeat")
    for name in (
        "validate-spec", "plan", "execute", "run-research-cycle",
        "update-market-data", "update-fresh-observations",
        "evaluate-fresh-cohorts", "pause", "resume",
        "validate-supervisor", "replay", "run-next-research-cycle",
        "run-next-model-cycle",
        "run-multi-horizon-model-cycle",
        "run-next-rolling-blind-batch",
        "run-next-cross-sectional-alpha-batch",
    ):
        command = commands.add_parser(name)
        command.add_argument(
            "--supervisor-spec-id", "--supervisor-id",
            dest="supervisor_spec_id", required=True,
        )
    for name in (
        "inspect-ledger", "inspect-research-queue", "inspect-candidate",
        "inspect-fresh-lock", "inspect-cohort", "inspect-fresh-status",
        "inspect-research-space",
        "inspect-model-candidate", "inspect-model-fresh-lock",
        "inspect-model-cohort", "inspect-fresh-model",
        "inspect-fresh-predictions", "inspect-fresh-labels",
        "inspect-fresh-strategy", "inspect-fresh-multiple-testing",
        "inspect-blind-windows", "inspect-batch-lock", "inspect-blind-result",
        "inspect-blind-survivor", "inspect-search-exposure",
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
            result = create_supervisor_spec(**common)
        elif args.command == "validate-spec":
            result = _repository(args).identity(args.supervisor_spec_id) | {
                "supervisor_spec_id": args.supervisor_spec_id, "status": "valid",
            }
        elif args.command in {"execute", "run-research-cycle", "resume"}:
            result = execute_supervisor(supervisor_spec_id=args.supervisor_spec_id, **common)
        elif args.command == "run-next-research-cycle":
            result = run_next_research_cycle(
                supervisor_spec_id=args.supervisor_spec_id, **common
            )
        elif args.command == "run-next-model-cycle":
            result = run_next_model_cycle(
                supervisor_spec_id=args.supervisor_spec_id, **common
            )
        elif args.command == "run-multi-horizon-model-cycle":
            result = run_multi_horizon_model_cycle(
                supervisor_spec_id=args.supervisor_spec_id, **common
            )
        elif args.command == "run-next-rolling-blind-batch":
            result = run_next_rolling_blind_batch(
                supervisor_spec_id=args.supervisor_spec_id, **common
            )
        elif args.command == "run-next-cross-sectional-alpha-batch":
            result = run_next_cross_sectional_alpha_batch(
                supervisor_spec_id=args.supervisor_spec_id, **common
            )
        elif args.command == "run-fresh-heartbeat":
            result = run_fresh_heartbeat(
                requested_through_date=args.requested_through_date,
                **common,
            )
        elif args.command == "replay-fresh-heartbeat":
            result = replay_fresh_model_heartbeat(**common)
        elif args.command == "validate-supervisor":
            result = validate_supervisor(
                supervisor_spec_id=args.supervisor_spec_id,
                work_root=args.work_root,
                store_root=args.store_root,
            )
        elif args.command == "replay":
            try:
                result = replay_next_research_cycle(
                    supervisor_spec_id=args.supervisor_spec_id, **common
                )
            except ValueError:
                result = replay_supervisor(
                    supervisor_spec_id=args.supervisor_spec_id,
                    work_root=args.work_root,
                    store_root=args.store_root,
                )
        elif args.command == "plan":
            result = {
                "status": "planned",
                "supervisor_spec_id": args.supervisor_spec_id,
                "next_phase": "project_contamination_ledger_then_research_queue",
            }
        elif args.command == "pause":
            result = {
                "status": "paused",
                "supervisor_spec_id": args.supervisor_spec_id,
                "side_effects": 0,
            }
        elif args.command in {
            "update-market-data", "update-fresh-observations",
            "evaluate-fresh-cohorts",
        }:
            result = {
                "status": "not_required_no_active_fresh_candidates",
                "supervisor_spec_id": args.supervisor_spec_id,
                "tushare_calls": 0,
                "network_calls": 0,
                "fresh_observation_writes": 0,
            }
        elif args.command in {
            "inspect-model-cohort", "inspect-fresh-model",
            "inspect-fresh-predictions", "inspect-fresh-labels",
            "inspect-fresh-strategy", "inspect-fresh-multiple-testing",
        }:
            result = inspect_fresh_model_artifact(
                artifact_id=args.artifact_id,
                **common,
            )
        else:
            result = _repository(args).identity(args.artifact_id) | {"artifact_id": args.artifact_id}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({
            "status": "blocked",
            "error_code": type(exc).__name__,
            "safe_summary": str(exc)[:300],
        }, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
