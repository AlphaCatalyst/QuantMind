from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from backend.services.engine.artifact_store import FileSystemResearchArtifactStore, resolve_config


pytestmark = pytest.mark.skipif(
    os.environ.get("QUANTMIND_RUN_REAL_STRATEGY_TESTS") != "1",
    reason="requires the explicit immutable research Artifact Store",
)

STORE_ROOT = Path("~/.quantmind2/artifact-store/v1").expanduser()
QLIB_SOURCE = "tqb_ea39d0378a835a3b609dacef769e4bf47708be004c703243d44375c95075d768"
RESULT_IDS = (
    "sbr_6c31a5f88f83e1380a2767c19a11aa3227fcc2dcf0c1e388bd2ea3632634e189",
    "sbr_2f708e69013a13eb7cf1b18effec3d73cd6f6b26175970c717aef663a1b0b5f6",
    "sbr_1a3f3d43b6b6a5e89278831def848cfe12010a9c55f17ee4003bf42be6dbbf93",
    "sbr_75d24a99db153896cf8b79af6e84d57d95ed5a76965e24ae1caba66adbd7e1ee",
)


def test_real_strategy_results_have_verified_formal_qlib_lineage(tmp_path):
    store = FileSystemResearchArtifactStore(resolve_config(STORE_ROOT)); store.validate_format()
    assert store.find_by_artifact_id(QLIB_SOURCE) is not None
    for result_id in RESULT_IDS:
        descriptor = store.find_by_artifact_id(result_id)
        assert descriptor is not None and QLIB_SOURCE in descriptor.lineage
        root = tmp_path / result_id
        store.materialize_artifact(descriptor.descriptor_id, root)
        plan = json.loads((root / "execution_plan.json").read_text())
        canonicality = json.loads((root / "canonicality.json").read_text())
        comparison = json.loads((root / "target_execution_comparison.json").read_text())
        assert plan["execution"]["chain"] == ["QlibBacktestService", "RedisRecordingStrategy", "SimulatorExecutor", "CnExchange"]
        assert canonicality["usable_for_research"] is True
        assert canonicality["usable_for_parameter_optimization"] is False
        assert canonicality["usable_for_promotion"] is False
        assert comparison["status"] == "not_verifiable_from_source_qlib_result"
