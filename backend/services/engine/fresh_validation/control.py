import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow.parquet as pq

from backend.services.engine.factor_dsl.identity import factor_template_id
from backend.services.engine.factor_dsl.parser import parse_template
from backend.services.engine.factor_registry.snapshot import validate_registry_snapshot
from backend.services.engine.fresh_validation_admission.artifact import validate_admission_result

from .canonical import hash_payload, sha256_file, write_json
from .errors import FreshValidationError


LABEL_CONTRACT_ID = "lc_f4cc31c4ebddf9f14623c639fd040be2bf7dcde5c2ad3bc8e98a6bf74205b744"
LOCK_SCHEMA = "fresh-validation-candidate-lock-v1"
LEDGER_SCHEMA = "research-data-exposure-ledger-v1"
PROTOCOL_SCHEMA = "fresh-validation-protocol-v1"
WATERMARK_SCHEMA = "fresh-validation-data-watermark-v1"


def _identity(prefix, payload, ignored=()):
    stable = {key: value for key, value in payload.items() if key not in set(ignored) | {
        "candidate_lock_id", "exposure_ledger_id", "protocol_id", "watermark_id"}}
    return prefix + hash_payload(stable)


def _json(path): return json.loads(Path(path).read_text())


def _proposal_for_template(campaign_path, template_id):
    found = []
    for path in sorted((Path(campaign_path) / "iterations").glob("*/decision.json")):
        decision = _json(path)
        for proposal in decision.get("proposals", []):
            template = proposal.get("template")
            if template and factor_template_id(parse_template(template)) == template_id:
                found.append((decision, proposal))
    if len(found) != 1: raise FreshValidationError("Candidate Template is not uniquely bound to Campaign Decision")
    return found[0]


def _development(campaign_path, development_id):
    memory = _json(Path(campaign_path) / "memory.json")
    found = [item for item in memory["development_results"] if item["development_evaluation_id"] == development_id]
    if len(found) != 1: raise FreshValidationError("Development evidence is not unique")
    return found[0]


def build_candidate_lock(*, registry_root, registry_snapshot_id, admission_root, admission_result_id,
                         campaign_roots, locked_at_utc=None, global_exposure_cutoff_date):
    registry = validate_registry_snapshot(registry_root, registry_snapshot_id)
    admission = validate_admission_result(admission_root, admission_result_id)
    admitted = tuple(admission.admitted_factor_instance_ids)
    if len(admitted) != 3: raise FreshValidationError("Candidate cohort must contain exactly three admitted Factors")
    by_id = {entry.factor_instance_id: entry for entry in registry.entries}
    campaign_paths = {}
    for root in campaign_roots:
        for path in (Path(root) / "campaigns").glob("rc_*"): campaign_paths[path.name] = path
    candidate_evidence = []
    for rank, factor_id in enumerate(admitted, 1):
        entry = by_id.get(factor_id)
        if (entry is None or entry.status.value != "research_registered" or entry.validation_result_id is not None or
                entry.frozen_result_id is not None or entry.fresh_validation_admission.get("admitted") is not True or
                entry.fresh_validation_admission.get("rank") != rank):
            raise FreshValidationError("Admitted Registry Entry violates candidate-lock preconditions")
        research = entry.research_evidence; campaign_path = campaign_paths.get(research["campaign_id"])
        if campaign_path is None: raise FreshValidationError("Campaign artifact is unavailable")
        decision, proposal = _proposal_for_template(campaign_path, entry.template_id)
        development = _development(campaign_path, research["development_evaluation_id"])
        if (decision["decision_id"] != research["research_decision_id"] or
                development["orientation"] != entry.orientation or
                development["orientation_source"] != "pre_2025_research_period"):
            raise FreshValidationError("Candidate direction or Decision lineage mismatch")
        candidate_evidence.append({"factor_instance_id": factor_id, "template_id": entry.template_id,
            "template": proposal["template"], "parameters": dict(sorted(entry.parameter_values.items())),
            "orientation": entry.orientation, "orientation_source": development["orientation_source"],
            "family_id": entry.family_id, "campaign_id": research["campaign_id"],
            "research_goal_id": research["research_goal_id"], "research_decision_id": research["research_decision_id"],
            "optimization_study_id": entry.optimization_study_id,
            "optimization_trial_id": entry.optimization_trial_id,
            "development_result_id": research["development_evaluation_id"], "admission_rank": rank})
    instant = locked_at_utc or datetime.now(timezone.utc)
    if instant.tzinfo is None: raise FreshValidationError("Lock timestamp must be timezone-aware")
    instant = instant.astimezone(timezone.utc); market = instant.astimezone(ZoneInfo("Asia/Shanghai"))
    payload = {"schema_version": LOCK_SCHEMA, "canonical_registry_snapshot_id": registry_snapshot_id,
        "admission_policy_id": admission.policy.policy_id, "admission_result_id": admission.result_id,
        "candidate_instance_ids": list(admitted), "candidate_evidence": candidate_evidence,
        "orientation": {item["factor_instance_id"]: item["orientation"] for item in candidate_evidence},
        "orientation_source": "pre_2025_research_period", "locked_at_utc": instant.isoformat().replace("+00:00", "Z"),
        "lock_market_timezone": "Asia/Shanghai", "lock_market_date": market.date().isoformat(),
        "previous_exposure_cutoff": global_exposure_cutoff_date,
        "fresh_start_rule": "first observed market trade date strictly after max(lock_market_date, global_exposure_cutoff_date)",
        "label_contract_id": LABEL_CONTRACT_ID, "evaluation_policy_id": "fresh-validation-evaluation-policy-v1"}
    payload["candidate_lock_id"] = _identity("fvcl_", payload)
    return payload


def build_exposure_ledger(candidate_lock, *, prior_ledger=None):
    exposures = [] if prior_ledger is None else list(prior_ledger["exposures"])
    required = [
        {"exposure_id":"rde_development_2025","protocol_id":"adaptive-development-2025-v1","dataset_id":"vd_1ac71a8b1bab36f7d4304fe13c14cbb936f073d0426b76e0c73096a819c3ed62","date_start":"2025-01-02","date_end":"2025-12-30","exposure_class":"development","consumer_class":["agent","control_layer"],"purpose":"adaptive Agent factor development","adaptive":True,"published":True,"source_artifact_ids":["QM2-P0-008","QM2-P0-008F"]},
        {"exposure_id":"rde_validation_2024","protocol_id":"factor-validation-v1","dataset_id":"vd_1ac71a8b1bab36f7d4304fe13c14cbb936f073d0426b76e0c73096a819c3ed62","date_start":"2024-01-02","date_end":"2024-12-30","exposure_class":"validation","consumer_class":["control_layer","human_report","registry"],"purpose":"formal factor validation","adaptive":False,"published":True,"source_artifact_ids":["fvr_b9f247e42487267754d5e6128beb4f90a379b77853462b6ca25f0f2918c51ab0"]},
        {"exposure_id":"rde_frozen_2026","protocol_id":"qm2-frozen-2026-v1","dataset_id":"vd_1ac71a8b1bab36f7d4304fe13c14cbb936f073d0426b76e0c73096a819c3ed62","date_start":"2026-01-05","date_end":"2026-06-23","exposure_class":"frozen_test","consumer_class":["control_layer","human_report","registry"],"purpose":"historical confirmatory Frozen Test","adaptive":False,"published":True,"source_artifact_ids":["fvt_734478fcc0291910667321669e5b5293f64594efe6f0e5b1334779f4d921c787"]},
    ]
    if prior_ledger is None: exposures.extend(required)
    elif exposures[:len(required)] != required: raise FreshValidationError("Exposure Ledger history cannot be deleted or rewritten")
    payload = {"schema_version": LEDGER_SCHEMA, "previous_exposure_ledger_id": None if prior_ledger is None else prior_ledger["exposure_ledger_id"],
        "candidate_lock_id": candidate_lock["candidate_lock_id"], "exposures": exposures,
        "lock_fact": {"locked_at_utc":candidate_lock["locked_at_utc"],"lock_market_date":candidate_lock["lock_market_date"],"future_data_exposed":False},
        "global_exposure_cutoff_date": max([candidate_lock["previous_exposure_cutoff"]] + [x["date_end"] for x in exposures])}
    payload["exposure_ledger_id"] = _identity("rdel_", payload)
    return payload


def build_protocol(candidate_lock, ledger):
    payload = {"schema_version": PROTOCOL_SCHEMA, "version":"1.0.0",
        "candidate_lock_id":candidate_lock["candidate_lock_id"], "candidate_instance_ids":candidate_lock["candidate_instance_ids"],
        "fresh_start_rule":candidate_lock["fresh_start_rule"], "target_valid_dates":60,
        "minimum_daily_observations":100, "minimum_ic_observations":20,
        "label_contract_id":candidate_lock["label_contract_id"], "orientation_policy":"locked_pre_2025_orientation_only",
        "evaluation_metrics":["mean_ic","std_ic","icir","ic_positive_rate","mean_rank_ic","std_rank_ic","rank_icir","rank_ic_positive_rate","valid_date_count","observation_count","median_daily_observations","minimum_daily_observations","factor_finite_coverage","label_finite_coverage"],
        "pass_policy":{"minimum_valid_dates":60,"minimum_median_daily_observations":100,"minimum_factor_finite_coverage":0.60,"minimum_oriented_mean_rank_ic":0.01,"minimum_oriented_rank_icir":0.10,"minimum_oriented_rank_ic_positive_rate":0.52,"require_same_sign_as_development":True},
        "selection_after_validation":"passing candidates ordered by signed Fresh mean RankIC, RankICIR, positive rate, finite coverage, factor_instance_id",
        "no_reselection":True,"no_backfill":True,"exposure_ledger_id":ledger["exposure_ledger_id"]}
    payload["protocol_id"] = _identity("fvp_", payload)
    return payload


def build_watermark(candidate_lock, protocol, *, source_id, source_files, checked_at=None):
    hashes = {Path(path).name: sha256_file(path) for path in sorted(map(Path, source_files))}
    frames = []
    for path in sorted(map(Path, source_files)):
        frames.append(pq.read_table(path, columns=["symbol", "trade_date", "open", "close", "factor"]).to_pandas())
    data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["symbol","trade_date","open","close","factor"])
    data["trade_date"] = pd.to_datetime(data["trade_date"], errors="coerce")
    if data["trade_date"].isna().any() or data.duplicated(["symbol","trade_date"]).any():
        raise FreshValidationError("Watermark source keys are invalid")
    data = data.sort_values(["symbol","trade_date"], kind="mergesort")
    grouped = data.groupby("symbol", sort=False)
    next_open = grouped["open"].shift(-1) * grouped["factor"].shift(-1)
    next_close = grouped["close"].shift(-1) * grouped["factor"].shift(-1)
    complete = pd.to_numeric(next_open, errors="coerce").gt(0) & pd.to_numeric(next_close, errors="coerce").gt(0)
    complete_counts = data.loc[complete].groupby("trade_date").size()
    dates = sorted(data["trade_date"].dt.date.astype(str).unique())
    cutoff = max(candidate_lock["lock_market_date"], candidate_lock["previous_exposure_cutoff"])
    eligible = [str(date.date()) for date,count in complete_counts.sort_index().items()
                if str(date.date()) > cutoff and count >= protocol["minimum_daily_observations"]]
    status = "awaiting_first_fresh_date" if not eligible else ("mature" if len(eligible) >= protocol["target_valid_dates"] else "collecting")
    payload = {"schema_version": WATERMARK_SCHEMA, "candidate_lock_id":candidate_lock["candidate_lock_id"],
        "protocol_id":protocol["protocol_id"], "source_id":source_id,"source_file_hashes":hashes,
        "observed_max_trade_date":dates[-1] if dates else None,
        "label_complete_max_observation_date":eligible[-1] if eligible else None,
        "fresh_start_trade_date":eligible[0] if eligible else None,
        "eligible_date_count":len(eligible), "target_valid_dates":protocol["target_valid_dates"],
        "status":status}
    payload["watermark_id"] = _identity("fdw_", payload)
    payload["checked_at"] = (checked_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat().replace("+00:00","Z")
    return payload


def publish_json_authority(path, payload, id_field):
    target=Path(path)
    if target.exists():
        existing=_json(target)
        if existing != payload: raise FreshValidationError("Immutable Git authority conflicts with existing content")
        return existing, True
    write_json(target,payload); return payload,False


def validate_json_authority(path, id_field, prefix, ignored=()):
    payload=_json(path); expected=_identity(prefix,payload,ignored)
    if payload.get(id_field)!=expected: raise FreshValidationError("Authority identity is invalid")
    return payload
