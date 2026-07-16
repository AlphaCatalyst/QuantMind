import copy

import pytest

from backend.services.engine.factor_dsl.models import SnapshotContract
from backend.services.engine.factor_optimization.enumerator import plan_study
from backend.services.engine.factor_optimization.examples import rolling_rank_study_spec, weighted_delta_study_spec
from backend.services.engine.factor_optimization.parser import parse_optimization_spec


CONTRACT = SnapshotContract("ds_bc82e7bb2c63d2c47677b11cf0f4fc1e5aa11a0ed18ee0bb27e3c8ab667d2ee7",
                            "legacy_feature_matrix_v1", {"mom_ret_1d": "feature", "liq_volume_ratio_5": "feature"},
                            60, {"mom_ret_1d": "double", "liq_volume_ratio_5": "double"})


def test_single_and_multi_parameter_deterministic_cartesian_order():
    first = plan_study(parse_optimization_spec(rolling_rank_study_spec()), CONTRACT)
    second = plan_study(parse_optimization_spec(rolling_rank_study_spec()), CONTRACT)
    assert first == second and [t.parameters for t in first.trials] == [{"window": x} for x in [2,3,5,10,20]]
    multi = plan_study(parse_optimization_spec(weighted_delta_study_spec()), CONTRACT)
    assert len(multi.trials) == 9
    assert multi.trials[0].parameters == {"periods": 1, "weight": 0.2}
    assert multi.trials[-1].parameters == {"periods": 5, "weight": 0.8}
    assert len({t.trial_id for t in multi.trials}) == 9


def test_parameter_name_sorting_not_mapping_order():
    payload = weighted_delta_study_spec()
    payload["search_space"] = {"weight": payload["search_space"]["weight"], "periods": payload["search_space"]["periods"]}
    payload["parameter_roles"] = {"weight": "factor_internal_weight", "periods": "lookback_window"}
    assert plan_study(parse_optimization_spec(payload), CONTRACT).trials[1].parameters == {"periods": 1, "weight": 0.5}


def test_different_spec_changes_study_and_budget_never_truncates():
    a = rolling_rank_study_spec(); b = copy.deepcopy(a); b["description"] = "A distinct immutable study description."
    assert plan_study(parse_optimization_spec(a), CONTRACT).study_id != plan_study(parse_optimization_spec(b), CONTRACT).study_id
    a["budget"]["max_trials"] = 4
    with pytest.raises(ValueError): plan_study(parse_optimization_spec(a), CONTRACT)


def test_lookback_cannot_exceed_snapshot_date_count():
    payload = rolling_rank_study_spec()
    payload["template"]["parameters"][0]["maximum"] = 100
    payload["search_space"]["window"]["values"] = [60, 61]
    with pytest.raises(ValueError, match="Snapshot date count"):
        plan_study(parse_optimization_spec(payload), CONTRACT)
