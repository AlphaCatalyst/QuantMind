import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.services.engine.fresh_validation import (
    FreshValidationError, FreshValidationNotMature, build_accrual_snapshot,
    build_candidate_lock, build_exposure_ledger, build_protocol, build_watermark,
    evaluate_fresh_validation, validate_accrual_snapshot,
)


AUTHORITY = Path(__file__).resolve().parents[3] / "docs/quantmind2/research/fresh_validation"


def published():
    read = lambda folder, pattern: json.loads(next((AUTHORITY/folder).glob(pattern)).read_text())
    return read("candidate-locks","fvcl_*.json"), read("exposure-ledger","rdel_*.json"), read("protocols","fvp_*.json"), read("watermarks","fdw_*.json")


def fixture_control():
    ids=["fi_"+str(i)*64 for i in (1,2,3)]
    lock={"candidate_lock_id":"fvcl_"+"a"*64,"candidate_instance_ids":ids,
          "candidate_evidence":[{"factor_instance_id":x,"template_id":"ft_"+str(i)*64,
            "parameters":{},"orientation":1} for i,x in enumerate(ids,1)],
          "lock_market_date":"2026-01-01","previous_exposure_cutoff":"2025-12-31"}
    protocol={"protocol_id":"fvp_"+"b"*64,"target_valid_dates":60,"minimum_daily_observations":100,
      "minimum_ic_observations":20,"label_contract_id":"lc_"+"c"*64,
      "pass_policy":{"minimum_valid_dates":60,"minimum_median_daily_observations":100,
      "minimum_factor_finite_coverage":.6,"minimum_oriented_mean_rank_ic":.01,
      "minimum_oriented_rank_icir":.1,"minimum_oriented_rank_ic_positive_rate":.52,
      "require_same_sign_as_development":True}}
    watermark={"watermark_id":"fdw_"+"d"*64,"fresh_start_trade_date":"2026-01-02",
               "source_file_hashes":{"fixture":"0"*64}}
    return lock,protocol,watermark


def fixture_data(date_count=61, symbols=120):
    dates=pd.bdate_range("2026-01-02",periods=date_count)
    rows=[]
    for day_index,date in enumerate(dates):
        for index in range(symbols):
            score=(index-(symbols-1)/2)/symbols
            previous_score=score if day_index else 0
            rows.append((f"{index:06d}",date,100.0,100.0*(1+previous_score*.01),1.0))
    frame=pd.DataFrame(rows,columns=["symbol","trade_date","open","close","factor"])
    factors={}
    lock,_,_=fixture_control()
    for offset,factor_id in enumerate(lock["candidate_instance_ids"]):
        values=frame[["symbol","trade_date"]].copy()
        score=np.tile(np.linspace(-1,1,symbols),date_count)
        values["factor_value"]=score if offset<2 else -score
        factors[factor_id]=values
    return frame,factors


def test_published_lock_is_exact_three_and_deterministic():
    lock,ledger,protocol,watermark=published()
    assert len(lock["candidate_instance_ids"])==3
    assert [x["admission_rank"] for x in lock["candidate_evidence"]]==[1,2,3]
    assert all(x["parameters"] and x["orientation"]==-1 for x in lock["candidate_evidence"])
    assert protocol["candidate_instance_ids"]==lock["candidate_instance_ids"]
    assert watermark["candidate_lock_id"]==lock["candidate_lock_id"]
    assert watermark["status"]=="awaiting_first_fresh_date" and watermark["eligible_date_count"]==0
    assert ledger["global_exposure_cutoff_date"]=="2026-06-24"


def test_real_candidate_lock_rebuild_and_mutation_change_identity():
    lock,_,_,_=published()
    rebuilt=build_candidate_lock(registry_root="/private/tmp/qm2-p0-008g-final/registry",
      registry_snapshot_id=lock["canonical_registry_snapshot_id"],
      admission_root="/private/tmp/qm2-p0-008g-final/fresh-validation-admission",
      admission_result_id=lock["admission_result_id"],
      campaign_roots=("/private/tmp/qm2-p0-008-final3/campaign-artifacts","/private/tmp/qm2-p0-008f-external4/campaign-artifacts"),
      locked_at_utc=datetime.fromisoformat(lock["locked_at_utc"].replace("Z","+00:00")),global_exposure_cutoff_date="2026-06-24")
    assert rebuilt==lock


def test_exposure_ledger_is_append_only_and_lock_date_dominates():
    lock,ledger,_,_=published()
    assert {x["exposure_class"] for x in ledger["exposures"]}=={"development","validation","frozen_test"}
    assert {c for x in ledger["exposures"] for c in x["consumer_class"]}>={"agent","control_layer","human_report","registry"}
    damaged=deepcopy(ledger); damaged["exposures"].pop()
    with pytest.raises(FreshValidationError): build_exposure_ledger(lock,prior_ledger=damaged)


def test_watermark_is_strictly_after_lock_and_detects_source_drift(tmp_path):
    lock,_,protocol,_=published()
    dates=pd.DataFrame([(f"{i:06d}",date,1.,1.,1.) for date in ("2026-07-17","2026-07-20") for i in range(100)],columns=["symbol","trade_date","open","close","factor"])
    path=tmp_path/"source.parquet"; dates.to_parquet(path,index=False)
    first=build_watermark(lock,protocol,source_id="fixture",source_files=[path],checked_at=datetime.now(timezone.utc))
    assert first["fresh_start_trade_date"] is None and first["eligible_date_count"]==0
    extra=pd.DataFrame([(f"{i:06d}","2026-07-21",1.,1.,1.) for i in range(100)],columns=dates.columns)
    dates=pd.concat([dates,extra],ignore_index=True); dates.to_parquet(path,index=False)
    second=build_watermark(lock,protocol,source_id="fixture",source_files=[path])
    assert second["watermark_id"]!=first["watermark_id"] and second["eligible_date_count"]==1
    assert second["fresh_start_trade_date"]=="2026-07-20"


def test_accrual_rejects_prelock_and_incomplete_label(tmp_path):
    lock,protocol,watermark=fixture_control(); frame,factors=fixture_data()
    bad=frame.copy(); bad.loc[0,"trade_date"]=pd.Timestamp("2025-12-31")
    with pytest.raises(FreshValidationError): build_accrual_snapshot(bad,factors,lock,protocol,watermark,tmp_path)
    result=build_accrual_snapshot(frame,factors,lock,protocol,watermark,tmp_path)
    assert len(result["eligible_dates"])==60
    assert build_accrual_snapshot(frame,factors,lock,protocol,watermark,tmp_path)["exact_existing"]


def test_maturity_one_time_evaluation_and_61st_date_cannot_change_result(tmp_path):
    lock,protocol,watermark=fixture_control(); frame,factors=fixture_data()
    accrual=build_accrual_snapshot(frame,factors,lock,protocol,watermark,tmp_path/"accrual")
    first=evaluate_fresh_validation(lock,protocol,watermark,tmp_path/"accrual",accrual["snapshot_id"],tmp_path/"result")
    second=evaluate_fresh_validation(lock,protocol,watermark,tmp_path/"missing", "ignored",tmp_path/"result")
    assert first["result_id"]==second["result_id"] and second["exact_existing"]
    assert len(first["manifest"]["evaluation_window"])==60
    assert len(first["manifest"]["candidate_results"])==3


def test_immature_and_corruption_are_rejected(tmp_path):
    lock,protocol,watermark=fixture_control(); frame,factors=fixture_data(60)
    accrual=build_accrual_snapshot(frame,factors,lock,protocol,watermark,tmp_path/"accrual")
    assert len(accrual["eligible_dates"])==59
    with pytest.raises(FreshValidationNotMature): evaluate_fresh_validation(lock,protocol,watermark,tmp_path/"accrual",accrual["snapshot_id"],tmp_path/"result")
    (Path(accrual["path"])/"dates.json").write_text("{}")
    with pytest.raises(FreshValidationError): validate_accrual_snapshot(tmp_path/"accrual",accrual["snapshot_id"])


def test_agent_optimizer_and_admission_do_not_import_fresh_evaluator():
    root=Path(__file__).resolve().parents[1]/"engine"
    forbidden=(root/"research_campaign",root/"factor_optimization",root/"fresh_validation_admission")
    for folder in forbidden:
        text="\n".join(path.read_text(errors="ignore") for path in folder.rglob("*.py"))
        assert "evaluate_fresh_validation" not in text and "FreshValidationResult" not in text


def test_sanitized_memory_exposes_only_fresh_outcome_category():
    from backend.services.engine.research_campaign.memory import sanitize_memory
    memory=sanitize_memory([],[],fresh_validation_outcomes=[{"factor_instance_id":"fi_"+"1"*64,
        "outcome":"fresh_validation_pending"}])
    assert memory["fresh_validation_feedback"][0]["outcome"]=="fresh_validation_pending"
    assert "rank_ic" not in json.dumps(memory).lower()
