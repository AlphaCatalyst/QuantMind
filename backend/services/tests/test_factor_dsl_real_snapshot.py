import os
from pathlib import Path

import pytest
import json

from backend.services.engine.factor_dsl import compile_template, execute_compiled, parse_template, snapshot_contract, validate_values
from backend.services.engine.factor_dsl.examples import normalized_spread_template, rolling_rank_template, weighted_delta_template


SNAPSHOT_ID = "ds_bc82e7bb2c63d2c47677b11cf0f4fc1e5aa11a0ed18ee0bb27e3c8ab667d2ee7"


def test_five_parameter_instances_execute_validate_and_replay_on_real_snapshot(tmp_path):
    root_value = os.environ.get("QM2_FACTOR_DSL_REAL_SNAPSHOT_ROOT")
    if not root_value:
        pytest.skip("set QM2_FACTOR_DSL_REAL_SNAPSHOT_ROOT for the real Snapshot proof")
    root = Path(root_value); contract = snapshot_contract(root, SNAPSHOT_ID)
    cases = [(rolling_rank_template(), {"window": 3}), (rolling_rank_template(), {"window": 10}),
             (weighted_delta_template(), {"weight": 0.3, "periods": 2}), (weighted_delta_template(), {"weight": 0.7, "periods": 5}),
             (normalized_spread_template(), {})]
    ids = []
    for payload, parameters in cases:
        compiled = compile_template(parse_template(payload), contract, parameters)
        result = execute_compiled(compiled, root, tmp_path)
        assert validate_values(root, tmp_path, result.factor_values_id)["rows"] == 5931
        ids.append(result.factor_values_id)
    assert len(set(ids)) == 5
    replay = execute_compiled(compile_template(parse_template(cases[0][0]), contract, cases[0][1]), root, tmp_path)
    assert replay.replayed is True and replay.factor_values_id == ids[0]
    assert replay.artifact.factor_values_id == ids[0]
    assert not list(tmp_path.glob(".staging-*"))


def test_real_snapshot_contract_has_152_features_and_artifact_corruption_is_rejected(tmp_path):
    root_value = os.environ.get("QM2_FACTOR_DSL_REAL_SNAPSHOT_ROOT")
    if not root_value: pytest.skip("set QM2_FACTOR_DSL_REAL_SNAPSHOT_ROOT for the real Snapshot proof")
    root = Path(root_value); contract = snapshot_contract(root, SNAPSHOT_ID)
    assert sum(role == "feature" for role in contract.feature_roles.values()) == 152
    compiled = compile_template(parse_template(normalized_spread_template()), contract)
    result = execute_compiled(compiled, root, tmp_path)
    manifest_path = Path(result.artifact_path) / "manifest.json"
    manifest = json.loads(manifest_path.read_text()); manifest["row_count"] += 1
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(Exception): validate_values(root, tmp_path, result.factor_values_id)
