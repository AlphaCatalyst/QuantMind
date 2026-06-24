import pytest

from backend.services.engine.scripts import factor_value_backfill_worker as worker


@pytest.mark.asyncio
async def test_factor_value_backfill_worker_processes_one_job(monkeypatch):
    events: list[dict] = []

    async def fake_ensure_tables():
        events.append({"event": "ensure"})

    async def fake_claim(*, worker_id, lease_seconds):
        events.append(
            {
                "event": "claim",
                "worker_id": worker_id,
                "lease_seconds": lease_seconds,
            }
        )
        return {
            "id": "job-1",
            "tenantId": "tenant",
            "userId": "user",
            "status": "running",
            "target": {"runIds": ["run-1"]},
            "params": {},
        }

    async def fake_execute(job, *, worker_id=None):
        events.append({"event": "execute", "job_id": job["id"], "worker_id": worker_id})
        return {
            **job,
            "status": "completed",
            "result": {"resolvedRuns": 1, "processedRuns": 1},
        }

    async def fake_record(**kwargs):
        events.append({"event": "record", **kwargs})

    monkeypatch.setattr(worker, "ensure_research_factor_tables", fake_ensure_tables)
    monkeypatch.setattr(
        worker, "claim_next_pending_factor_value_backfill_job", fake_claim
    )
    monkeypatch.setattr(worker, "execute_claimed_factor_value_backfill_job", fake_execute)
    monkeypatch.setattr(worker, "record_factor_value_backfill_event", fake_record)

    processed = await worker.run_worker(
        once=True,
        poll_interval=0.1,
        idle_limit=None,
        worker_id="worker-1",
        max_claims=None,
        heartbeat_interval=None,
        lease_seconds=90,
    )

    assert processed == 1
    assert {"event": "ensure"} in events
    assert any(item.get("event") == "claim" for item in events)
    assert any(item.get("event") == "execute" for item in events)
    assert any(
        item.get("event") == "record" and item.get("event_type") == "worker_processed"
        for item in events
    )


@pytest.mark.asyncio
async def test_factor_value_backfill_worker_once_idle(monkeypatch):
    events: list[dict] = []

    async def fake_ensure_tables():
        events.append({"event": "ensure"})

    async def fake_claim(*, worker_id, lease_seconds):
        events.append({"event": "claim", "worker_id": worker_id})
        return None

    async def fake_record(**kwargs):
        events.append({"event": "record", **kwargs})

    monkeypatch.setattr(worker, "ensure_research_factor_tables", fake_ensure_tables)
    monkeypatch.setattr(
        worker, "claim_next_pending_factor_value_backfill_job", fake_claim
    )
    monkeypatch.setattr(worker, "record_factor_value_backfill_event", fake_record)

    processed = await worker.run_worker(
        once=True,
        poll_interval=0.1,
        idle_limit=None,
        worker_id="worker-1",
        max_claims=None,
        heartbeat_interval=None,
        lease_seconds=None,
    )

    assert processed == 0
    assert any(
        item.get("event") == "record" and item.get("event_type") == "worker_idle"
        for item in events
    )
