from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.services.engine.artifact_store.enums import ArtifactKind
from backend.services.engine.autonomous_factor_campaign.artifact import KINDS
from backend.services.engine.fresh_model_cohort import engine
from backend.services.engine.fresh_model_cohort.models import (
    ALLOWED_ENDPOINTS,
    CANDIDATE_IDS,
    FRESH_LOCK_IDS,
    LABEL_ID,
    LEGAL_FRESH_STATES,
    MINIMUM_EVIDENCE,
    MODEL_SPEC_ID,
    PRIOR_FIRST_SEEN_SNAPSHOT_ID,
    PROJECT_EXPOSURE_DATE,
    SEEDS,
    STRATEGY_PROTOCOL,
    WALK_FORWARD_SPEC_ID,
    ModelFreshCandidateCohortV1,
    minimum_evidence_passed,
)


BUNDLES = (
    "mfbs1_e55d3d6c9a810cf3f3098de90ee948b6c150a45d178760d8e83f7e098a55e415",
    "mfbs1_19cc24e0ff0eeaa45d5cb10a1e1280bf6da0eabace1e1c380b8bc7bfc68504d6",
)


def _candidate(index: int) -> dict:
    return {
        "candidate_id": CANDIDATE_IDS[index],
        "status": "retrospective_model_candidate",
        "worth_fresh_observation": True,
        "label_id": LABEL_ID,
        "bundle_id": BUNDLES[index],
        "model_spec_id": MODEL_SPEC_ID,
        "walk_forward_spec_id": WALK_FORWARD_SPEC_ID,
    }


def _lock(index: int) -> dict:
    return {
        "fresh_lock_id": FRESH_LOCK_IDS[index],
        "candidate_id": CANDIDATE_IDS[index],
        "bundle_id": BUNDLES[index],
        "label_id": LABEL_ID,
        "model_spec_id": MODEL_SPEC_ID,
        "seed_ensemble": list(SEEDS),
        "monthly_retraining_rule": "first official trade date of each calendar month",
        "primary_statistic": "fresh daily official-label RankIC",
        "strategy_protocol": STRATEGY_PROTOCOL,
        "no_backfill": True,
    }


def _label() -> dict:
    return {
        "label_id": LABEL_ID,
        "label_name": "technical_return_1d",
        "formula": "adjusted_close[T+1]/adjusted_open[T+1]-1",
        "entry_offset_sessions": 1,
        "exit_offset_sessions": 1,
        "horizon_sessions": 1,
        "hac_lag": 10,
        "no_forward_fill": True,
    }


class FakeStore:
    def __init__(self):
        self.descriptors = []

    def list_by_kind(self, kind):
        return [row for row in self.descriptors if row.artifact_kind == kind]


class FakeRepository:
    def __init__(self):
        self.store = FakeStore()
        self.values = {
            **{CANDIDATE_IDS[i]: _candidate(i) for i in range(2)},
            **{FRESH_LOCK_IDS[i]: _lock(i) for i in range(2)},
            LABEL_ID: _label(),
        }
        self.published = []

    def identity(self, artifact_id):
        return dict(self.values[artifact_id])

    def publish(self, kind, identity, files, lineage=()):
        self.published.append(kind)
        field, _ = KINDS[kind]
        artifact_id = identity.get(field) or {
            "model_fresh_candidate_cohort": ModelFreshCandidateCohortV1()
            .payload()["model_fresh_candidate_cohort_id"]
        }[kind]
        stable = dict(identity)
        stable.pop(field, None)
        self.values[artifact_id] = stable
        self.store.descriptors.append(
            SimpleNamespace(artifact_kind=kind, artifact_id=artifact_id)
        )
        return {
            "artifact_id": artifact_id,
            "exact_existing": False,
            "new_blob_count": 1,
        }


def test_cohort_contract_is_exactly_two_members():
    value = ModelFreshCandidateCohortV1().payload()
    assert value["candidate_membership"] == list(CANDIDATE_IDS)
    assert value["fresh_lock_ids"] == list(FRESH_LOCK_IDS)
    assert value["membership_frozen"] is True
    assert value["configuration_frozen"] is True


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("label_id", LABEL_ID),
        ("model_spec_id", MODEL_SPEC_ID),
        ("walk_forward_spec_id", WALK_FORWARD_SPEC_ID),
        ("primary_statistic", "daily official-label RankIC"),
        ("hac_lag", 10),
        ("bh_fdr_q", 0.10),
        ("project_exposure_date", PROJECT_EXPOSURE_DATE),
        ("market_snapshot_id_at_lock", PRIOR_FIRST_SEEN_SNAPSHOT_ID),
        ("no_backfill", True),
        ("published_before_fresh_market_read", True),
        ("registry_writes", 0),
        ("promotion_writes", 0),
    ],
)
def test_cohort_frozen_fields(field, expected):
    assert ModelFreshCandidateCohortV1().payload()[field] == expected


@pytest.mark.parametrize(("field", "expected"), list(STRATEGY_PROTOCOL.items()))
def test_strategy_protocol_is_frozen(field, expected):
    assert ModelFreshCandidateCohortV1().payload()["strategy_protocol"][field] == expected


@pytest.mark.parametrize(("field", "expected"), list(MINIMUM_EVIDENCE.items()))
def test_minimum_evidence_policy_is_frozen(field, expected):
    assert ModelFreshCandidateCohortV1().payload()["minimum_evidence_policy"][field] == expected


@pytest.mark.parametrize("endpoint", ALLOWED_ENDPOINTS)
def test_incremental_endpoint_allowlist(endpoint):
    assert endpoint in {"daily", "adj_factor", "daily_basic", "trade_cal", "index_daily"}


@pytest.mark.parametrize("status", LEGAL_FRESH_STATES)
def test_legal_fresh_states(status):
    assert status.startswith("fresh_")


def test_membership_mutation_is_rejected():
    invalid = replace(
        ModelFreshCandidateCohortV1(),
        candidate_membership=(CANDIDATE_IDS[0],),
    )
    with pytest.raises(ValueError, match="MODEL_FRESH_COHORT_MEMBERSHIP_MISMATCH"):
        invalid.payload()


def test_lock_mutation_is_rejected():
    invalid = replace(
        ModelFreshCandidateCohortV1(),
        fresh_lock_ids=(FRESH_LOCK_IDS[0],),
    )
    with pytest.raises(ValueError, match="MODEL_FRESH_COHORT_LOCK_MISMATCH"):
        invalid.payload()


def test_contract_recovery_maps_candidates_to_exact_bundles():
    repository = FakeRepository()
    candidates, locks, label = engine._recover_contracts(repository)
    assert [row["bundle_id"] for row in candidates] == list(BUNDLES)
    assert [row["candidate_id"] for row in locks] == list(CANDIDATE_IDS)
    assert label["label_id"] == LABEL_ID


@pytest.mark.parametrize(
    ("target", "field", "value"),
    [
        ("candidate", "status", "approved"),
        ("candidate", "worth_fresh_observation", False),
        ("candidate", "label_id", "wrong"),
        ("candidate", "model_spec_id", "wrong"),
        ("candidate", "walk_forward_spec_id", "wrong"),
        ("lock", "candidate_id", "wrong"),
        ("lock", "bundle_id", "wrong"),
        ("lock", "label_id", "wrong"),
        ("lock", "model_spec_id", "wrong"),
        ("lock", "seed_ensemble", [20260701]),
        ("lock", "primary_statistic", "return"),
        ("lock", "strategy_protocol", {}),
        ("lock", "no_backfill", False),
    ],
)
def test_contract_drift_is_rejected(target, field, value):
    repository = FakeRepository()
    artifact_id = CANDIDATE_IDS[0] if target == "candidate" else FRESH_LOCK_IDS[0]
    repository.values[artifact_id][field] = value
    with pytest.raises(engine.FreshModelContractError, match="FRESH_LOCK_CONTRACT_MISMATCH"):
        engine._recover_contracts(repository)


def test_executable_label_guard_accepts_formal_l1():
    engine._validate_executable_label(_label())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("label_name", "model_label"),
        ("formula", "CSZScore(open[T+5]/open[T]-1)"),
        ("entry_offset_sessions", 0),
        ("exit_offset_sessions", 5),
        ("horizon_sessions", 5),
        ("hac_lag", 15),
        ("no_forward_fill", False),
    ],
)
def test_executable_label_guard_rejects_identity_drift(field, value):
    label = _label()
    label[field] = value
    with pytest.raises(
        engine.FreshModelContractError, match="EXECUTABLE_LABEL_IDENTITY_MISMATCH"
    ):
        engine._validate_executable_label(label)


def test_minimum_evidence_passes_only_at_complete_boundary():
    assert minimum_evidence_passed(dict(MINIMUM_EVIDENCE))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fresh_trading_days", 59),
        ("completed_holding_windows", 4),
        ("rebalance_periods", 2),
        ("monthly_retraining_events", 1),
        ("coverage", 0.899),
        ("pit_violations", 1),
    ],
)
def test_minimum_evidence_rejects_each_shortfall(field, value):
    observation = dict(MINIMUM_EVIDENCE)
    observation[field] = value
    assert minimum_evidence_passed(observation) is False


def test_cohort_is_published_before_any_market_boundary(monkeypatch, tmp_path):
    repository = FakeRepository()
    bundle = SimpleNamespace()
    monkeypatch.setattr(engine, "_runtime", lambda *args, **kwargs: (bundle, repository))
    result = engine.freeze_cohort(
        repository_root=tmp_path, work_root=tmp_path, store_root=tmp_path
    )
    assert repository.published == ["model_fresh_candidate_cohort"]
    assert result["candidate_count"] == 2
    assert result["fresh_lock_count"] == 2


def test_token_absence_blocks_after_cohort_freeze(monkeypatch, tmp_path):
    repository = FakeRepository()
    bundle = SimpleNamespace()
    monkeypatch.setattr(engine, "_runtime", lambda *args, **kwargs: (bundle, repository))
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    result = engine.run_fresh_heartbeat(
        repository_root=tmp_path,
        work_root=tmp_path,
        store_root=tmp_path,
    )
    assert result["status"] == "fresh_data_blocked"
    assert result["reason"] == "blocked_token_absent"
    assert repository.published[0] == "model_fresh_candidate_cohort"
    assert result["execution_counts"]["network_calls"] == 0


def test_artifact_kinds_use_stable_prefixes():
    expected = {
        "model_fresh_candidate_cohort": "mfcc1_",
        "fresh_model_training_event": "fmte1_",
        "fresh_model_bundle_membership": "fmbm1_",
        "fresh_model_prediction": "fmp1_",
        "fresh_model_label_observation": "fmlo1_",
        "fresh_model_strategy_observation": "fmso1_",
        "fresh_model_candidate_observation": "fmco1_",
        "fresh_model_cohort_multiple_testing": "fmcmt1_",
        "fresh_model_candidate_assessment": "fmca1_",
        "fresh_model_heartbeat_run": "fmhr1_",
    }
    assert {name: KINDS[name][1] for name in expected} == expected


@pytest.mark.parametrize(
    "kind",
    [
        ArtifactKind.MODEL_FRESH_CANDIDATE_COHORT,
        ArtifactKind.FRESH_MODEL_TRAINING_EVENT,
        ArtifactKind.FRESH_MODEL_BUNDLE_MEMBERSHIP,
        ArtifactKind.FRESH_MODEL_PREDICTION,
        ArtifactKind.FRESH_MODEL_LABEL_OBSERVATION,
        ArtifactKind.FRESH_MODEL_STRATEGY_OBSERVATION,
        ArtifactKind.FRESH_MODEL_CANDIDATE_OBSERVATION,
        ArtifactKind.FRESH_MODEL_COHORT_MULTIPLE_TESTING,
        ArtifactKind.FRESH_MODEL_CANDIDATE_ASSESSMENT,
        ArtifactKind.FRESH_MODEL_HEARTBEAT_RUN,
    ],
)
def test_store_enum_contains_each_fresh_model_artifact(kind):
    assert kind.value in KINDS


def test_identity_has_no_credential_material():
    serialized = repr(ModelFreshCandidateCohortV1().payload()).lower()
    assert "token_hash" not in serialized
    assert "access_token" not in serialized
    assert "api_key" not in serialized


def test_model_configuration_has_three_fixed_seeds():
    assert SEEDS == (20260701, 20260702, 20260703)
    assert len(set(SEEDS)) == 3


def test_fresh_start_is_rule_not_hardcoded_date():
    value = ModelFreshCandidateCohortV1().payload()
    assert "strictly after project exposure date" in value["fresh_start_rule"]
    assert "2026-07-24" not in value["fresh_start_rule"]


def test_unprocessed_snapshot_is_recovered_without_network_or_republish():
    repository = FakeRepository()
    snapshot_id = "fms1_existing"
    repository.values[snapshot_id] = {
        "fresh_start_date": "2026-07-24",
        "data_as_of_date": "2026-07-24",
    }
    repository.store.descriptors.append(
        SimpleNamespace(artifact_kind="fresh_market_snapshot", artifact_id=snapshot_id)
    )

    result = engine._recover_unprocessed_snapshot(repository, "2026-07-25")

    assert result["fresh_market_snapshot_id"] == snapshot_id
    assert result["recovered_from_store"] is True
    assert result["network_calls"] == 0
    assert result["new_artifacts"] == 0


def test_snapshot_with_completed_heartbeat_is_not_reprocessed():
    repository = FakeRepository()
    snapshot_id = "fms1_existing"
    heartbeat_id = "fmhr1_existing"
    repository.values[snapshot_id] = {
        "fresh_start_date": "2026-07-24",
        "data_as_of_date": "2026-07-24",
    }
    repository.values[heartbeat_id] = {
        "fresh_market_snapshot_id": snapshot_id,
        "requested_through_date": "2026-07-24",
        "data_as_of_date": "2026-07-24",
        "status": "fresh_evidence_accumulating",
    }
    repository.store.descriptors.extend(
        [
            SimpleNamespace(
                artifact_kind="fresh_market_snapshot", artifact_id=snapshot_id
            ),
            SimpleNamespace(
                artifact_kind="fresh_model_heartbeat_run", artifact_id=heartbeat_id
            ),
        ]
    )

    assert engine._recover_unprocessed_snapshot(repository, "2026-07-25") is None


def test_monthly_retraining_count_counts_month_events_not_seed_models():
    repository = FakeRepository()
    candidate_id = CANDIDATE_IDS[0]
    for index, (effective_from, event_type) in enumerate(
        [
            ("2026-07-24", "initial_fresh_model_event"),
            ("2026-08-03", "monthly_retraining_event"),
            ("2026-08-03", "monthly_retraining_event"),
            ("2026-08-03", "monthly_retraining_event"),
            ("2026-09-01", "monthly_retraining_event"),
        ]
    ):
        artifact_id = f"fmte1_{index}"
        repository.values[artifact_id] = {
            "candidate_id": candidate_id,
            "effective_from": effective_from,
            "event_type": event_type,
            "counts_toward_monthly_retraining_minimum": (
                event_type == "monthly_retraining_event"
            ),
        }
        repository.store.descriptors.append(
            SimpleNamespace(
                artifact_kind="fresh_model_training_event",
                artifact_id=artifact_id,
            )
        )

    assert engine._monthly_training_event_count(repository, candidate_id) == 2


def test_missing_monthly_retraining_policy_is_a_specific_hard_failure():
    repository = FakeRepository()
    repository.values[FRESH_LOCK_IDS[0]]["monthly_retraining_rule"] = None

    with pytest.raises(
        engine.FreshModelContractError,
        match="FRESH_RETRAINING_POLICY_INCOMPLETE",
    ):
        engine._recover_contracts(repository)
