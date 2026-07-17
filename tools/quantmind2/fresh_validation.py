#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.fresh_validation import (
    FreshValidationNotMature, build_accrual_snapshot, build_candidate_lock,
    build_exposure_ledger, build_protocol, build_watermark, compute_locked_factor_values,
    evaluate_fresh_validation, publish_json_authority, validate_accrual_snapshot,
    validate_fresh_validation_result, validate_json_authority,
)

REGISTRY_ID = "frs_f0a08cc472270cf80f2ae8c1141de17871dacbe2edccba8eb4ffe05ca45d3ba4"
ADMISSION_ID = "fvar_89e61fe674bff1d10d46c9bea3913a456f236bbc191578291529736480a831ab"
REGISTRY_ROOT = "/private/tmp/qm2-p0-008g-final/registry"
ADMISSION_ROOT = "/private/tmp/qm2-p0-008g-final/fresh-validation-admission"
CAMPAIGN_ROOTS = ("/private/tmp/qm2-p0-008-final3/campaign-artifacts",
                  "/private/tmp/qm2-p0-008f-external4/campaign-artifacts")
SOURCE = "/Users/yj/Documents/Codex/2026-06-30/nih/work/QuantMind/db/feature_snapshots/model_features_2026.parquet"
SOURCE_ID = "legacy-feature-source-2026"


def _load(path):
    return json.loads(Path(path).read_text())


def authority_paths(authority_root):
    root = Path(authority_root)
    locks = sorted((root / "candidate-locks").glob("fvcl_*.json"))
    ledgers = sorted((root / "exposure-ledger").glob("rdel_*.json"))
    protocols = sorted((root / "protocols").glob("fvp_*.json"))
    watermarks = sorted((root / "watermarks").glob("fdw_*.json"))
    return locks, ledgers, protocols, watermarks


def load_control(authority_root, require_watermark=False):
    values = authority_paths(authority_root)
    required = values if require_watermark else values[:3]
    if any(len(items) != 1 for items in required):
        raise SystemExit("authority root must contain exactly one matching control artifact")
    return tuple(_load(items[0]) if items else None for items in values)


def lock_candidates(args):
    lock = build_candidate_lock(registry_root=REGISTRY_ROOT, registry_snapshot_id=REGISTRY_ID,
        admission_root=ADMISSION_ROOT, admission_result_id=ADMISSION_ID,
        campaign_roots=CAMPAIGN_ROOTS, global_exposure_cutoff_date="2026-06-24")
    ledger = build_exposure_ledger(lock)
    protocol = build_protocol(lock, ledger)
    root = Path(args.authority_root)
    publish_json_authority(root / "candidate-locks" / f"{lock['candidate_lock_id']}.json", lock, "candidate_lock_id")
    publish_json_authority(root / "exposure-ledger" / f"{ledger['exposure_ledger_id']}.json", ledger, "exposure_ledger_id")
    publish_json_authority(root / "protocols" / f"{protocol['protocol_id']}.json", protocol, "protocol_id")
    return {"candidate_lock_id": lock["candidate_lock_id"], "candidate_instance_ids": lock["candidate_instance_ids"],
            "exposure_ledger_id": ledger["exposure_ledger_id"], "protocol_id": protocol["protocol_id"],
            "lock_market_date": lock["lock_market_date"], "global_exposure_cutoff_date": ledger["global_exposure_cutoff_date"]}


def inspect_watermark(args):
    lock, _, protocol, _ = load_control(args.authority_root)
    watermark = build_watermark(lock, protocol, source_id=SOURCE_ID, source_files=[args.source])
    path = Path(args.authority_root) / "watermarks" / f"{watermark['watermark_id']}.json"
    publish_json_authority(path, watermark, "watermark_id")
    return watermark


def build_accrual(args):
    lock, _, protocol, watermark = load_control(args.authority_root, True)
    if watermark["fresh_start_trade_date"] is None:
        raise FreshValidationNotMature("FRESH_VALIDATION_NOT_MATURE")
    frame = pd.read_parquet(args.source)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame = frame[frame.trade_date >= pd.Timestamp(watermark["fresh_start_trade_date"])].copy()
    values = compute_locked_factor_values(frame, lock)
    return build_accrual_snapshot(frame, values, lock, protocol, watermark, args.output_root)


def validate_all(args):
    lock_paths, ledger_paths, protocol_paths, watermark_paths = authority_paths(args.authority_root)
    for paths, field, prefix, ignored in ((lock_paths,"candidate_lock_id","fvcl_",()),
            (ledger_paths,"exposure_ledger_id","rdel_",()),(protocol_paths,"protocol_id","fvp_",()),
            (watermark_paths,"watermark_id","fdw_",("checked_at",))):
        for path in paths: validate_json_authority(path,field,prefix,ignored)
    return {"valid": True, "candidate_locks":len(lock_paths), "exposure_ledgers":len(ledger_paths),
            "protocols":len(protocol_paths), "watermarks":len(watermark_paths)}


def main(argv=None):
    parser=argparse.ArgumentParser(description="Strict forward Fresh Validation control")
    sub=parser.add_subparsers(dest="command",required=True)
    for name in ("lock-candidates","inspect-exposure","inspect-watermark","check-maturity","inspect","validate"):
        p=sub.add_parser(name); p.add_argument("--authority-root",required=True)
        if name=="inspect-watermark": p.add_argument("--source",default=SOURCE)
    p=sub.add_parser("build-accrual"); p.add_argument("--authority-root",required=True); p.add_argument("--source",default=SOURCE); p.add_argument("--output-root",required=True)
    p=sub.add_parser("evaluate"); p.add_argument("--authority-root",required=True); p.add_argument("--accrual-root",required=True); p.add_argument("--snapshot-id",required=True); p.add_argument("--output-root",required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=="lock-candidates": payload=lock_candidates(args)
        elif args.command=="inspect-watermark": payload=inspect_watermark(args)
        elif args.command=="validate": payload=validate_all(args)
        else:
            lock,ledger,protocol,watermark=load_control(args.authority_root,args.command not in {"inspect-exposure"})
            if args.command=="inspect-exposure": payload={"exposure_ledger_id":ledger["exposure_ledger_id"],"global_exposure_cutoff_date":ledger["global_exposure_cutoff_date"],"exposure_count":len(ledger["exposures"])}
            elif args.command in {"check-maturity","inspect"}: payload={"candidate_lock_id":lock["candidate_lock_id"],"protocol_id":protocol["protocol_id"],"watermark_id":watermark["watermark_id"],"eligible_date_count":watermark["eligible_date_count"],"target_valid_dates":protocol["target_valid_dates"],"status":watermark["status"]}
            elif args.command=="build-accrual": payload=build_accrual(args)
            else: payload=evaluate_fresh_validation(lock,protocol,watermark,args.accrual_root,args.snapshot_id,args.output_root)
    except FreshValidationNotMature as exc:
        payload={"error_code":exc.error_code,"status":"awaiting_data"}
    print(json.dumps(payload,indent=2,sort_keys=True,default=str)); return 0


if __name__=="__main__": raise SystemExit(main())
