import json
from contextlib import asynccontextmanager

import pytest

from backend.services.api.routers import research_factor_service as svc
from backend.services.engine.research import factor_value_backfill


class FakeMappings:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None

    def one(self):
        return self.rows[0]


class FakeResult:
    def __init__(self, rows=None, scalar=None):
        self.rows = rows or []
        self.scalar = scalar

    def mappings(self):
        return FakeMappings(self.rows)

    def scalar_one(self):
        return self.scalar


@pytest.mark.asyncio
async def test_factor_value_backfill_dry_run_plans_candidate_without_writes(monkeypatch):
    writes: list[dict] = []

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            params = params or {}
            if "INSERT INTO qm_factor_candidate_runs" in sql:
                writes.append(params)
                return FakeResult()
            if "FROM qm_factor_candidates" in sql:
                return FakeResult([{"id": params["candidate_id"]}])
            if "FROM qm_factor_candidate_runs" in sql and "ORDER BY created_at DESC" in sql:
                return FakeResult(
                    [
                        {
                            "id": "existing-run",
                            "params_json": {
                                "start_date": "2026-01-01",
                                "end_date": "2026-01-31",
                                "holding_period": 5,
                            },
                        }
                    ]
                )
            return FakeResult()

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(factor_value_backfill, "get_session", fake_get_session)

    result = await factor_value_backfill.run_factor_value_backfill(
        tenant_id="tenant",
        user_id="user",
        candidate_ids=["candidate-1"],
        start_date="2026-02-01",
        end_date="2026-02-28",
        dry_run=True,
    )

    assert result["status"] == "planned"
    assert result["resolvedRuns"] == 1
    assert result["runs"][0]["run_id"] == "planned-candidate-candidate-1"
    assert result["runs"][0]["params"]["start_date"] == "2026-02-01"
    assert writes == []


@pytest.mark.asyncio
async def test_factor_value_backfill_processes_existing_run(monkeypatch):
    calls: list[tuple[str, str, str]] = []

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            if "id = ANY(:run_ids)" in sql:
                return FakeResult(
                    [
                        {
                            "id": "run-1",
                            "candidate_id": "candidate-1",
                            "params_json": {
                                "start_date": "2026-01-01",
                                "end_date": "2026-01-31",
                            },
                        }
                    ]
                )
            return FakeResult()

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    async def fake_evaluate(tenant_id, user_id, run_id):
        calls.append((tenant_id, user_id, run_id))
        return {
            "id": run_id,
            "status": "completed",
            "metrics": {"inserted_values": 12},
        }

    monkeypatch.setattr(factor_value_backfill, "get_session", fake_get_session)
    monkeypatch.setattr(svc, "evaluate_factor_run_locally", fake_evaluate)

    result = await factor_value_backfill.run_factor_value_backfill(
        tenant_id="tenant",
        user_id="user",
        run_ids=["run-1", "run-1"],
    )

    assert result["status"] == "completed"
    assert result["resolvedRuns"] == 1
    assert result["processedRuns"] == 1
    assert result["runs"][0]["status"] == "completed"
    assert calls == [("tenant", "user", "run-1")]


@pytest.mark.asyncio
async def test_create_factor_value_backfill_job_persists_target_and_params(monkeypatch):
    captured: dict[str, object] = {}

    class FakeSession:
        async def execute(self, statement, params=None):
            captured["sql"] = str(statement)
            captured["params"] = params or {}
            target = json.loads(captured["params"]["target_json"])
            job_params = json.loads(captured["params"]["params_json"])
            return FakeResult(
                [
                    {
                        "id": "job-1",
                        "tenant_id": "tenant",
                        "user_id": "user",
                        "status": "pending",
                        "target_json": target,
                        "params_json": job_params,
                        "result_json": None,
                        "error_message": None,
                        "worker_id": None,
                        "started_at": None,
                        "completed_at": None,
                        "created_at": None,
                        "updated_at": None,
                    }
                ]
            )

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(factor_value_backfill, "get_session", fake_get_session)

    job = await factor_value_backfill.create_factor_value_backfill_job(
        "tenant",
        "user",
        {
            "run_ids": ["run-1"],
            "candidate_ids": ["candidate-1"],
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "dry_run": True,
        },
    )

    assert "INSERT INTO qm_factor_value_backfill_jobs" in captured["sql"]
    assert job["id"] == "job-1"
    assert job["target"]["runIds"] == ["run-1"]
    assert job["target"]["candidateIds"] == ["candidate-1"]
    assert job["params"]["startDate"] == "2026-01-01"
    assert job["params"]["dryRun"] is True


@pytest.mark.asyncio
async def test_execute_factor_value_backfill_job_updates_result(monkeypatch):
    updates: list[dict] = []

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            params = params or {}
            updates.append(params)
            if "SET status = 'running'" in sql:
                return FakeResult(
                    [
                        {
                            "id": "job-1",
                            "tenant_id": "tenant",
                            "user_id": "user",
                            "status": "running",
                            "target_json": {"runIds": ["run-1"]},
                            "params_json": {"dryRun": True, "maxRuns": 20},
                            "result_json": None,
                            "error_message": None,
                            "worker_id": "worker-1",
                            "started_at": None,
                            "completed_at": None,
                            "created_at": None,
                            "updated_at": None,
                        }
                    ]
                )
            if "result_json" in sql:
                result = json.loads(params["result_json"])
                return FakeResult(
                    [
                        {
                            "id": "job-1",
                            "tenant_id": "tenant",
                            "user_id": "user",
                            "status": params["status"],
                            "target_json": {"runIds": ["run-1"]},
                            "params_json": {"dryRun": True, "maxRuns": 20},
                            "result_json": result,
                            "error_message": params["error_message"],
                            "worker_id": "worker-1",
                            "started_at": None,
                            "completed_at": None,
                            "created_at": None,
                            "updated_at": None,
                        }
                    ]
                )
            return FakeResult()

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    async def fake_run_backfill(**kwargs):
        return {
            "status": "planned",
            "resolvedRuns": 1,
            "processedRuns": 0,
            "runs": [{"run_id": "run-1"}],
        }

    monkeypatch.setattr(factor_value_backfill, "get_session", fake_get_session)
    monkeypatch.setattr(
        factor_value_backfill, "run_factor_value_backfill", fake_run_backfill
    )

    job = await factor_value_backfill.execute_factor_value_backfill_job(
        "tenant",
        "user",
        "job-1",
        worker_id="worker-1",
    )

    assert job["status"] == "completed"
    assert job["result"]["status"] == "planned"
    assert updates[0]["worker_id"] == "worker-1"
    assert updates[-1]["status"] == "completed"


@pytest.mark.asyncio
async def test_claim_next_pending_factor_value_backfill_job_uses_skip_locked(monkeypatch):
    captured: list[tuple[str, dict]] = []

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            params = params or {}
            captured.append((sql, params))
            if "UPDATE qm_factor_value_backfill_jobs" in sql:
                return FakeResult(
                    [
                        {
                            "id": "job-1",
                            "tenant_id": "tenant",
                            "user_id": "user",
                            "status": "running",
                            "target_json": {"runIds": ["run-1"]},
                            "params_json": {},
                            "result_json": None,
                            "error_message": None,
                            "worker_id": "worker-1",
                            "started_at": None,
                            "completed_at": None,
                            "created_at": None,
                            "updated_at": None,
                        }
                    ]
                )
            return FakeResult()

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(factor_value_backfill, "get_session", fake_get_session)

    job = await factor_value_backfill.claim_next_pending_factor_value_backfill_job(
        worker_id="worker-1",
        lease_seconds=60,
    )

    sql, params = captured[0]
    assert job["id"] == "job-1"
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert params["worker_id"] == "worker-1"
    assert json.loads(params["execution_lease_json"]) == {
        "workerId": "worker-1",
        "leaseSeconds": 60,
    }
    assert any("INSERT INTO qm_factor_value_backfill_events" in item[0] for item in captured)


@pytest.mark.asyncio
async def test_cancel_factor_value_backfill_job_marks_cancelled(monkeypatch):
    captured: list[tuple[str, dict]] = []

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            params = params or {}
            captured.append((sql, params))
            if "UPDATE qm_factor_value_backfill_jobs" in sql:
                return FakeResult(
                    [
                        {
                            "id": "job-1",
                            "tenant_id": "tenant",
                            "user_id": "user",
                            "status": "cancelled",
                            "target_json": {"runIds": ["run-1"]},
                            "params_json": {},
                            "result_json": None,
                            "error_message": "stop",
                            "worker_id": None,
                            "started_at": None,
                            "completed_at": None,
                            "created_at": None,
                            "updated_at": None,
                        }
                    ]
                )
            return FakeResult()

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(factor_value_backfill, "get_session", fake_get_session)

    job = await factor_value_backfill.cancel_factor_value_backfill_job(
        "tenant",
        "user",
        "job-1",
        reason="stop",
    )

    assert job["status"] == "cancelled"
    assert captured[0][1]["reason"] == "stop"
    assert any("INSERT INTO qm_factor_value_backfill_events" in item[0] for item in captured)


@pytest.mark.asyncio
async def test_list_factor_value_backfill_events_filters_scope(monkeypatch):
    captured: list[tuple[str, dict]] = []

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            params = params or {}
            captured.append((sql, params))
            if "SELECT COUNT" in sql:
                return FakeResult(scalar=1)
            return FakeResult(
                [
                    {
                        "id": "event-1",
                        "job_id": "job-1",
                        "tenant_id": "tenant",
                        "user_id": "user",
                        "worker_id": "worker-1",
                        "event_type": "claimed",
                        "status": "running",
                        "details_json": {"leaseSeconds": 60},
                        "created_at": None,
                    }
                ]
            )

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        assert kwargs.get("read_only") is True
        yield FakeSession()

    monkeypatch.setattr(factor_value_backfill, "get_session", fake_get_session)

    result = await factor_value_backfill.list_factor_value_backfill_events(
        "tenant",
        "user",
        job_id="job-1",
        worker_id="worker-1",
        event_type="claimed",
        status="running",
        limit=500,
        offset=-5,
    )

    sql, params = captured[0]
    assert "(tenant_id = :tenant_id OR tenant_id IS NULL)" in sql
    assert "(user_id = :user_id OR user_id IS NULL)" in sql
    assert "job_id = :job_id" in sql
    assert "worker_id = :worker_id" in sql
    assert params["limit"] == 100
    assert params["offset"] == 0
    assert result["total"] == 1
    assert result["items"][0]["eventType"] == "claimed"
