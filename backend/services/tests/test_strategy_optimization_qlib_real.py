from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from backend.services.engine.artifact_store import FileSystemResearchArtifactStore, resolve_config


pytestmark = pytest.mark.skipif(
    os.environ.get("QUANTMIND_RUN_REAL_STRATEGY_OPTIMIZATION_TESTS") != "1",
    reason="requires the explicit immutable research Artifact Store",
)

STORE_ROOT = Path("~/.quantmind2/artifact-store/v1").expanduser()
STUDY_ID = "sos_e504d537b1a28f87db183fa3bb99cd3dc20601a4df0e59b26b155e933fa10687"


def _materialize(store, artifact_id, root):
    descriptor = store.find_by_artifact_id(artifact_id)
    assert descriptor is not None
    target = root / artifact_id
    store.materialize_artifact(descriptor.descriptor_id, target)
    return target, descriptor


def test_real_strategy_optimization_graph_has_96_formal_trials_and_four_locks(tmp_path):
    store = FileSystemResearchArtifactStore(resolve_config(STORE_ROOT)); store.validate_format()
    study_root, study_descriptor = _materialize(store, STUDY_ID, tmp_path)
    summary = json.loads((study_root / "summary.json").read_text())
    index = json.loads((study_root / "trial_index.json").read_text())
    assert summary["trial_count"] == len(index["trial_ids"]) == 96
    assert len(summary["candidate_lock_ids"]) == 4
    for trial_id in index["trial_ids"]:
        trial_root, trial_descriptor = _materialize(store, trial_id, tmp_path)
        trial = json.loads((trial_root / "trial.json").read_text())
        assert trial["n_drop"] < trial["topk"]
        assert len(trial["metrics"]["annual"]) == 6
        assert trial["execution_evidence"]["formal_chain"] == ["QlibBacktestService", "RedisRecordingStrategy", "SimulatorExecutor", "CnExchange"]
        result_id = trial["strategy_backtest_result_id"]
        result_descriptor = store.find_by_artifact_id(result_id)
        assert result_descriptor is not None and result_id in trial_descriptor.lineage
    for candidate_id in summary["candidate_lock_ids"]:
        candidate_root, _ = _materialize(store, candidate_id, tmp_path)
        candidate = json.loads((candidate_root / "candidate.json").read_text())
        assert set(candidate["retrospective_reports"]) == {"2025", "2026H1"}
        assert all(not value["usable_for_selection"] for value in candidate["retrospective_reports"].values())
        assert candidate["usable_for_promotion"] is False and candidate["eligible_for_production"] is False
    assert summary["strategy_optimization_result_id"] in study_descriptor.lineage
