#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.artifact_runtime import (  # noqa: E402
    inspect_campaign_replay,
    inspect_optimization_replay,
    publish_domain_artifact,
    publish_existing_artifact,
    recover_research_state,
    replay_optimization_study,
    replay_research_campaign,
    resolve_artifact,
)
from backend.services.engine.artifact_runtime.cli import (  # noqa: E402
    BASELINE_INVENTORY_ID,
    add_runtime_arguments,
    runtime_context_from_args,
    safe_error_payload,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QuantMind Artifact-backed Runtime v1")
    add_runtime_arguments(parser)
    commands = parser.add_subparsers(dest="command", required=True)
    resolve = commands.add_parser("resolve")
    resolve.add_argument("--artifact-kind", required=True)
    resolve.add_argument("--artifact-id", required=True)
    publish = commands.add_parser("publish")
    publish.add_argument("--artifact-kind", required=True)
    publish.add_argument("--artifact-id", required=True)
    publish.add_argument("--staging-root", required=True)
    publish.add_argument("--lineage", action="append", default=[])
    replay = commands.add_parser("replay")
    replay.add_argument("--artifact-kind", choices=("factor_optimization", "research_campaign"), required=True)
    replay.add_argument("--artifact-id", required=True)
    commands.add_parser("recover-state")
    existing = commands.add_parser("publish-existing")
    existing.add_argument("--artifact-kind", required=True)
    existing.add_argument("--artifact-id", required=True)
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        context = runtime_context_from_args(args, inventory_id=BASELINE_INVENTORY_ID)
        if args.command == "resolve":
            payload = resolve_artifact(context, args.artifact_kind, args.artifact_id).safe_summary()
        elif args.command == "publish":
            payload = publish_domain_artifact(
                context, args.artifact_kind, args.artifact_id, args.staging_root,
                lineage=tuple(args.lineage),
            ).safe_summary()
        elif args.command == "publish-existing":
            payload = publish_existing_artifact(
                context, args.artifact_kind, args.artifact_id
            ).safe_summary()
        elif args.command == "replay":
            if args.artifact_kind == "research_campaign":
                payload = inspect_campaign_replay(
                    replay_research_campaign(context, args.artifact_id)
                )
            else:
                payload = inspect_optimization_replay(
                    replay_optimization_study(context, args.artifact_id)
                )
        else:
            payload = recover_research_state(context, ROOT).to_dict()
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps(
            safe_error_payload(exc), ensure_ascii=False, sort_keys=True
        ), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
