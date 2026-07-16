import json
import os
import inspect
from pathlib import Path

import pytest

from backend.services.engine.factor_dsl import snapshot_contract
from backend.services.engine.factor_optimization import execute_study, parse_optimization_spec, plan_study, validate_study
from backend.services.engine.factor_optimization.examples import rolling_rank_study_spec, weighted_delta_study_spec


def test_optimizer_has_no_label_provider_legacy_or_predictive_runtime_calls():
    import backend.services.engine.factor_optimization.runner as runner
    source = inspect.getsource(runner)
    for forbidden in ("load_labels", "TongDaXin", "LegacyFeatureProvider", "RankIC", "backtest", "LightGBM"):
        assert forbidden not in source


def test_two_real_studies_fourteen_trials_and_exact_existing(tmp_path):
    root_value=os.getenv("QM2_FACTOR_DSL_REAL_SNAPSHOT_ROOT")
    if not root_value: pytest.skip("real Snapshot root is required")
    root=Path(root_value); values=tmp_path/"values"; studies=tmp_path/"studies"
    results=[]
    for payload,count in ((rolling_rank_study_spec(),5),(weighted_delta_study_spec(),9)):
        spec=parse_optimization_spec(payload); contract=snapshot_contract(root,spec.snapshot_id); study=plan_study(spec,contract)
        result=execute_study(study,contract,root,values,studies)
        assert len(result.trials)==count and all(t.factor_values_id for t in result.trials)
        assert all(t.eligible_for_validation for t in result.trials)
        assert validate_study(study,root,values,studies).result_id==result.result_id
        replay=execute_study(study,contract,root,values,studies)
        assert replay.exact_existing and replay.result_id==result.result_id
        assert not list(studies.glob(f".{study.study_id}.staging-*"))
        results.append(result)
    assert sum(len(x.trials) for x in results)==14
    assert len({t.trial_id for r in results for t in r.trials})==14
    assert all(t.metrics.infinity_count==0 for r in results for t in r.trials)


def test_conflicting_complete_artifact_is_rejected(tmp_path):
    root_value=os.getenv("QM2_FACTOR_DSL_REAL_SNAPSHOT_ROOT")
    if not root_value: pytest.skip("real Snapshot root is required")
    root=Path(root_value); spec=parse_optimization_spec(rolling_rank_study_spec()); contract=snapshot_contract(root,spec.snapshot_id); study=plan_study(spec,contract)
    execute_study(study,contract,root,tmp_path/"values",tmp_path/"studies")
    summary=tmp_path/"studies"/study.study_id/"summary.json"; payload=json.loads(summary.read_text()); payload["predictive_claim"]=True; summary.write_text(json.dumps(payload))
    with pytest.raises(ValueError): execute_study(study,contract,root,tmp_path/"values",tmp_path/"studies")


def test_study_status_cannot_contradict_trial_outcomes(tmp_path):
    root_value=os.getenv("QM2_FACTOR_DSL_REAL_SNAPSHOT_ROOT")
    if not root_value: pytest.skip("real Snapshot root is required")
    root=Path(root_value); spec=parse_optimization_spec(rolling_rank_study_spec()); contract=snapshot_contract(root,spec.snapshot_id); study=plan_study(spec,contract)
    execute_study(study,contract,root,tmp_path/"values",tmp_path/"studies")
    manifest=tmp_path/"studies"/study.study_id/"manifest.json"; payload=json.loads(manifest.read_text()); payload["status"]="partial"; manifest.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="Study status"):
        validate_study(study,root,tmp_path/"values",tmp_path/"studies")


def test_trial_failure_is_isolated_and_budget_marks_remaining_not_run(tmp_path, monkeypatch):
    root_value=os.getenv("QM2_FACTOR_DSL_REAL_SNAPSHOT_ROOT")
    if not root_value: pytest.skip("real Snapshot root is required")
    import backend.services.engine.factor_optimization.runner as runner
    root=Path(root_value); payload=rolling_rank_study_spec(); payload["search_space"]["window"]["values"]=[2,3,5]; payload["budget"]["max_trials"]=3
    spec=parse_optimization_spec(payload); contract=snapshot_contract(root,spec.snapshot_id); study=plan_study(spec,contract)
    original=runner.execute_compiled
    def sometimes_fail(compiled,*args,**kwargs):
        if compiled.bound_parameters["window"]==3: raise RuntimeError("sensitive absolute path must not be persisted")
        return original(compiled,*args,**kwargs)
    monkeypatch.setattr(runner,"execute_compiled",sometimes_fail)
    stale=tmp_path/"studies"/f".{study.study_id}.staging-old"; stale.mkdir(parents=True)
    result=execute_study(study,contract,root,tmp_path/"values",tmp_path/"studies")
    assert [t.status.value for t in result.trials]==["succeeded","failed","not_run"]
    assert result.status.value=="partial" and result.trials[1].error_code=="TRIAL_RUNTIMEERROR"
    assert not stale.exists()
