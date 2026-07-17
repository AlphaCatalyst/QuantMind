import json
import os
import shutil
import uuid
from pathlib import Path

import pandas as pd

from backend.services.engine.factor_validation.metrics import calculate_split_metrics, metrics_payload

from .accrual import validate_accrual_snapshot
from .canonical import hash_payload, sha256_file, write_json
from .errors import FreshValidationError, FreshValidationNotMature


SCHEMA_VERSION="fresh-validation-result-v1"


def _gate(metrics,policy):
    checks=((metrics.date_count_valid>=policy["minimum_valid_dates"],"FRESH_VALID_DATES_BELOW_GATE"),
        (metrics.median_daily_observations>=policy["minimum_median_daily_observations"],"FRESH_DAILY_OBSERVATIONS_BELOW_GATE"),
        (metrics.factor_finite_coverage>=policy["minimum_factor_finite_coverage"],"FRESH_FACTOR_COVERAGE_BELOW_GATE"),
        (metrics.mean_rank_ic is not None and metrics.mean_rank_ic>=policy["minimum_oriented_mean_rank_ic"],"FRESH_MEAN_RANK_IC_BELOW_GATE"),
        (metrics.rank_icir is not None and metrics.rank_icir>=policy["minimum_oriented_rank_icir"],"FRESH_RANK_ICIR_BELOW_GATE"),
        (metrics.rank_ic_positive_rate is not None and metrics.rank_ic_positive_rate>=policy["minimum_oriented_rank_ic_positive_rate"],"FRESH_RANK_IC_POSITIVE_RATE_BELOW_GATE"))
    return tuple(reason for passed,reason in checks if not passed)


def _result_lock(output_root,protocol_id): return Path(output_root)/"protocol-locks"/f"{protocol_id}.json"


def evaluate_fresh_validation(candidate_lock,protocol,watermark,accrual_root,snapshot_id,output_root):
    existing_lock=_result_lock(output_root,protocol["protocol_id"])
    if existing_lock.exists():
        result_id=json.loads(existing_lock.read_text())["result_id"]
        return validate_fresh_validation_result(output_root,result_id,exact_existing=True)
    accrual=validate_accrual_snapshot(accrual_root,snapshot_id)
    if accrual["manifest"]["watermark_id"] != watermark["watermark_id"]:
        raise FreshValidationError("Fresh Validation Watermark differs from Accrual lineage")
    dates=accrual["eligible_dates"]
    if len(dates)<protocol["target_valid_dates"]: raise FreshValidationNotMature("FRESH_VALIDATION_NOT_MATURE")
    window=dates[:protocol["target_valid_dates"]]; root=Path(accrual["path"])
    labels=pd.read_parquet(root/"labels.parquet"); factors=pd.read_parquet(root/"factor_values.parquet")
    labels=labels[labels.trade_date.dt.date.astype(str).isin(window)]
    rows=[]
    for item in candidate_lock["candidate_evidence"]:
        locked_id=item["factor_instance_id"]
        values=factors[["symbol","trade_date",locked_id]].rename(columns={locked_id:"factor_value"})
        values=values[values.trade_date.dt.date.astype(str).isin(window)]
        metrics=calculate_split_metrics(values,labels,orientation=item["orientation"],minimum_observations=protocol["minimum_ic_observations"])
        reasons=_gate(metrics,protocol["pass_policy"]); passed=not reasons
        rows.append({"locked_factor_instance_id":locked_id,"template_id":item["template_id"],
            "parameters":item["parameters"],"orientation":item["orientation"],"metrics":metrics_payload(metrics),
            "passed":passed,"reasons":list(reasons)})
    passing=[row for row in rows if row["passed"]]
    passing.sort(key=lambda row:(-row["metrics"]["mean_rank_ic"],-row["metrics"]["rank_icir"],
        -row["metrics"]["rank_ic_positive_rate"],-row["metrics"]["factor_finite_coverage"],row["locked_factor_instance_id"]))
    order=[row["locked_factor_instance_id"] for row in passing]
    identity={"schema_version":SCHEMA_VERSION,"candidate_lock_id":candidate_lock["candidate_lock_id"],
        "protocol_id":protocol["protocol_id"],"accrual_snapshot_id":snapshot_id,"evaluation_window":window,
        "candidate_results":rows,"future_frozen_candidate_order":order}
    result_id="fvvr_"+hash_payload(identity); target=Path(output_root)/"results"/result_id
    if target.exists(): return validate_fresh_validation_result(output_root,result_id,exact_existing=True)
    staging=target.parent/f".{result_id}.staging-{uuid.uuid4().hex}"; staging.mkdir(parents=True)
    try:
        write_json(staging/"protocol.json",protocol); write_json(staging/"candidate_lock.json",candidate_lock)
        write_json(staging/"watermark.json",watermark)
        (staging/"results").mkdir()
        for row in rows: write_json(staging/"results"/f"{row['locked_factor_instance_id']}.json",row)
        write_json(staging/"candidate_order.json",{"factor_instance_ids":order})
        hashes={p.relative_to(staging).as_posix():sha256_file(p) for p in sorted(staging.rglob("*.json"))}
        write_json(staging/"manifest.json",{**identity,"result_id":result_id,"file_hashes":hashes})
        target.parent.mkdir(parents=True,exist_ok=True); os.replace(staging,target); staging=None
        lock=_result_lock(output_root,protocol["protocol_id"]); lock.parent.mkdir(parents=True,exist_ok=True)
        temporary=lock.parent/f".{lock.name}.{uuid.uuid4().hex}"; write_json(temporary,{"protocol_id":protocol["protocol_id"],"result_id":result_id}); os.replace(temporary,lock)
    finally:
        if staging is not None and staging.exists(): shutil.rmtree(staging)
    return validate_fresh_validation_result(output_root,result_id)


def validate_fresh_validation_result(output_root,result_id,exact_existing=False):
    root=Path(output_root)/"results"/result_id
    try: manifest=json.loads((root/"manifest.json").read_text())
    except Exception as exc: raise FreshValidationError("Fresh Validation Result unreadable") from exc
    inventory={p.relative_to(root).as_posix() for p in root.rglob("*.json") if p.name!="manifest.json"}
    if inventory!=set(manifest.get("file_hashes",{})): raise FreshValidationError("Fresh Result inventory mismatch")
    for name,digest in manifest["file_hashes"].items():
        if sha256_file(root/name)!=digest: raise FreshValidationError("Fresh Result hash mismatch")
    stable={key:value for key,value in manifest.items() if key not in {"result_id","file_hashes"}}
    if result_id!="fvvr_"+hash_payload(stable): raise FreshValidationError("Fresh Result identity mismatch")
    return {"result_id":result_id,"path":str(root),"manifest":manifest,"exact_existing":exact_existing}
