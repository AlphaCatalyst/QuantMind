import json
import os
import shutil
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from backend.services.engine.factor_validation.labels import build_production_labels, production_label_contract

from .canonical import hash_payload, sha256_file, write_json
from .errors import FreshValidationError, FreshValidationNotMature


SCHEMA_VERSION = "fresh-validation-accrual-v1"


def _parquet_hash(frame, path):
    frame.to_parquet(path,index=False,engine="pyarrow",compression="zstd"); return sha256_file(path)


def build_accrual_snapshot(source_frame, candidate_factor_values, candidate_lock, protocol, watermark, output_root):
    if watermark["fresh_start_trade_date"] is None: raise FreshValidationNotMature("FRESH_VALIDATION_NOT_MATURE")
    frame=source_frame.copy(); frame["trade_date"]=pd.to_datetime(frame["trade_date"])
    start=pd.Timestamp(watermark["fresh_start_trade_date"])
    if (frame["trade_date"] < start).any() or (frame["trade_date"].dt.date.astype(str) <= candidate_lock["lock_market_date"]).any():
        raise FreshValidationError("Pre-lock observations are forbidden in Fresh Validation accrual")
    required={"symbol","trade_date","open","close","factor"}
    if required-set(frame): raise FreshValidationError("Accrual source lacks Label Contract columns")
    labels=build_production_labels(frame,production_label_contract(1))
    labels=labels[labels["entry_trade_date"].notna() & labels["exit_trade_date"].notna() &
                  np.isfinite(labels["raw_label"]) & np.isfinite(labels["model_label"])].copy()
    candidate_ids=tuple(candidate_lock["candidate_instance_ids"])
    if set(candidate_factor_values)!=set(candidate_ids): raise FreshValidationError("Accrual candidate cohort differs from lock")
    factors=[]
    for factor_id in candidate_ids:
        values=candidate_factor_values[factor_id].copy(); values["trade_date"]=pd.to_datetime(values["trade_date"])
        if values.duplicated(["symbol","trade_date"]).any(): raise FreshValidationError("Factor Values keys are duplicated")
        values=values[["symbol","trade_date","factor_value"]].rename(columns={"factor_value":factor_id})
        factors.append(values)
    wide=factors[0]
    for values in factors[1:]: wide=wide.merge(values,on=["symbol","trade_date"],how="outer",validate="one_to_one")
    aligned=labels[["symbol","trade_date","model_label"]].merge(wide,on=["symbol","trade_date"],how="inner",validate="one_to_one")
    finite=np.isfinite(aligned[["model_label",*candidate_ids]]).all(axis=1)
    counts=aligned.loc[finite].groupby("trade_date").size()
    eligible_dates=tuple(date for date,count in counts.sort_index().items() if count>=protocol["minimum_daily_observations"])
    identity={"schema_version":SCHEMA_VERSION,"candidate_lock_id":candidate_lock["candidate_lock_id"],
        "protocol_id":protocol["protocol_id"],"watermark_id":watermark["watermark_id"],
        "source_file_hashes":watermark["source_file_hashes"],"date_start":watermark["fresh_start_trade_date"],
        "date_end":str(frame["trade_date"].max().date()),"candidate_instance_ids":list(candidate_ids),
        "label_contract_id":protocol["label_contract_id"]}
    snapshot_id="fvas_"+hash_payload(identity); target=Path(output_root)/snapshot_id
    if target.exists(): return validate_accrual_snapshot(output_root,snapshot_id,exact_existing=True)
    staging=target.parent/f".{snapshot_id}.staging-{uuid.uuid4().hex}"; staging.mkdir(parents=True)
    try:
        source_columns=["symbol","trade_date","open","close","factor"]
        hashes={"features.parquet":_parquet_hash(frame[source_columns].sort_values(["trade_date","symbol"]),staging/"features.parquet"),
            "labels.parquet":_parquet_hash(labels.sort_values(["trade_date","symbol"]),staging/"labels.parquet"),
            "factor_values.parquet":_parquet_hash(wide.sort_values(["trade_date","symbol"]),staging/"factor_values.parquet")}
        write_json(staging/"dates.json",{"eligible_dates":[str(x.date()) for x in eligible_dates]})
        write_json(staging/"quality.json",{"eligible_date_count":len(eligible_dates),"minimum_daily_observations":protocol["minimum_daily_observations"],"same_candidate_window":True,"pre_lock_rows":0})
        hashes.update({name:sha256_file(staging/name) for name in ("dates.json","quality.json")})
        write_json(staging/"manifest.json",{**identity,"snapshot_id":snapshot_id,"file_hashes":hashes})
        target.parent.mkdir(parents=True,exist_ok=True); os.replace(staging,target); staging=None
    finally:
        if staging is not None and staging.exists(): shutil.rmtree(staging)
    return validate_accrual_snapshot(output_root,snapshot_id)


def validate_accrual_snapshot(output_root,snapshot_id,exact_existing=False):
    root=Path(output_root)/snapshot_id
    try: manifest=json.loads((root/"manifest.json").read_text())
    except Exception as exc: raise FreshValidationError("Accrual Snapshot is unreadable") from exc
    files={p.relative_to(root).as_posix() for p in root.iterdir() if p.name!="manifest.json"}
    if files!=set(manifest.get("file_hashes",{})): raise FreshValidationError("Accrual inventory mismatch")
    for name,digest in manifest["file_hashes"].items():
        if sha256_file(root/name)!=digest: raise FreshValidationError("Accrual hash mismatch")
    stable={key:value for key,value in manifest.items() if key not in {"snapshot_id","file_hashes"}}
    if manifest.get("schema_version")!=SCHEMA_VERSION or snapshot_id!="fvas_"+hash_payload(stable):
        raise FreshValidationError("Accrual identity mismatch")
    return {"snapshot_id":snapshot_id,"path":str(root),"manifest":manifest,
        "eligible_dates":json.loads((root/"dates.json").read_text())["eligible_dates"],"exact_existing":exact_existing}
