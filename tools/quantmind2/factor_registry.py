#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from backend.services.engine.factor_registry import (  # noqa: E402
    active_factors, apply_decision, build_entries_from_evidence,
    default_promotion_policy, list_by_family, list_by_status,
    load_registry_snapshot, plan_decision, promotion_candidates,
    publish_snapshot, validate_registry_snapshot,
)
from backend.services.engine.factor_registry.decisions import decision_payload  # noqa: E402
from backend.services.engine.factor_registry.errors import FactorRegistryError  # noqa: E402


VALIDATION_RESULT = "fvr_b9f247e42487267754d5e6128beb4f90a379b77853462b6ca25f0f2918c51ab0"
SELECTION = "fvs_f679a63089f076c11315f522f4d59dc8248731863ec6aafc02b70c9762819e9c"
FROZEN = "fvt_734478fcc0291910667321669e5b5293f64594efe6f0e5b1334779f4d921c787"


def _summary(snapshot):
    statuses = {}
    for item in snapshot.entries: statuses[item.status.value] = statuses.get(item.status.value, 0) + 1
    return {"registry_snapshot_id": snapshot.registry_snapshot_id, "policy_id": snapshot.policy.policy_id,
        "entry_count": len(snapshot.entries), "status_counts": dict(sorted(statuses.items())),
        "promotion_candidates": len(promotion_candidates(snapshot)),
        "approved": len(list_by_status(snapshot, "approved")), "active": len(active_factors(snapshot)),
        "families": sorted({x.family_id for x in snapshot.entries}), "exact_existing": snapshot.exact_existing}


def _common(parser):
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--snapshot-id", required=True)


def _parser():
    parser=argparse.ArgumentParser(); commands=parser.add_subparsers(dest="command", required=True)
    build=commands.add_parser("build")
    build.add_argument("--repository-root", default=str(ROOT), type=Path)
    build.add_argument("--optimization-root", required=True, type=Path)
    build.add_argument("--validation-root", required=True, type=Path)
    build.add_argument("--output-root", required=True, type=Path)
    for name in ("validate", "inspect", "list"): _common(commands.add_parser(name))
    validation=commands.choices["validate"]
    validation.add_argument("--repository-root", default=str(ROOT), type=Path)
    validation.add_argument("--optimization-root", required=True, type=Path)
    validation.add_argument("--validation-root", required=True, type=Path)
    listing=commands.choices["list"]; listing.add_argument("--status"); listing.add_argument("--family-id"); listing.add_argument("--template-id")
    for name in ("plan-decision", "apply-decision"):
        cmd=commands.add_parser(name); _common(cmd); cmd.add_argument("--factor-instance-id", required=True)
        cmd.add_argument("--action", required=True); cmd.add_argument("--reason", required=True)
        cmd.add_argument("--decided-by", required=True); cmd.add_argument("--decision-source", required=True)
        cmd.add_argument("--created-at", required=True)
    return parser


def main(argv=None):
    args=_parser().parse_args(argv)
    try:
        if args.command == "build":
            policy=default_promotion_policy(); entries=build_entries_from_evidence(repository_root=args.repository_root,
                optimization_root=args.optimization_root, validation_root=args.validation_root,
                validation_result_id=VALIDATION_RESULT, selection_id=SELECTION, frozen_result_id=FROZEN, policy=policy)
            result=_summary(publish_snapshot(args.output_root, policy, entries))
        else:
            snapshot=load_registry_snapshot(args.output_root, args.snapshot_id)
            if args.command == "validate":
                entries=build_entries_from_evidence(repository_root=args.repository_root,
                    optimization_root=args.optimization_root, validation_root=args.validation_root,
                    validation_result_id=VALIDATION_RESULT, selection_id=SELECTION,
                    frozen_result_id=FROZEN, policy=snapshot.policy)
                if entries != snapshot.entries: raise FactorRegistryError("Registry entries differ from authoritative evidence")
                result={"status":"valid", "evidence":"valid", **_summary(snapshot)}
            elif args.command == "inspect": result={"status":"valid", **_summary(snapshot)}
            elif args.command == "list":
                items=snapshot.entries
                if args.status: items=list_by_status(snapshot,args.status)
                if args.family_id: items=list_by_family(snapshot,args.family_id)
                if args.template_id: items=tuple(x for x in items if x.template_id==args.template_id)
                result={"registry_snapshot_id":snapshot.registry_snapshot_id,"entries":[{"factor_instance_id":x.factor_instance_id,"template_id":x.template_id,"family_id":x.family_id,"status":x.status.value,"parameters":dict(x.parameter_values)} for x in items]}
            else:
                entry=next((x for x in snapshot.entries if x.factor_instance_id==args.factor_instance_id),None)
                if entry is None: raise FactorRegistryError("Factor Instance not found")
                decision=plan_decision(entry=entry,registry_snapshot_id=snapshot.registry_snapshot_id,
                    policy_id=snapshot.policy.policy_id,action=args.action,reason=args.reason,
                    decided_by=args.decided_by,decision_source=args.decision_source,created_at=args.created_at)
                result={"decision":decision_payload(decision),"published":False}
                if args.command=="apply-decision":
                    updated=apply_decision(snapshot,decision,args.output_root); result={"decision":decision_payload(decision),"published":True,**_summary(updated)}
        print(json.dumps(result,sort_keys=True,ensure_ascii=False)); return 0
    except (FactorRegistryError,OSError,ValueError) as exc:
        print(json.dumps({"status":"error","error":str(exc)},ensure_ascii=False)); return 2


if __name__ == "__main__": raise SystemExit(main())
