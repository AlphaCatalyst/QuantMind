import pytest

from backend.services.engine.scripts import factor_campaign_worker as worker


@pytest.mark.asyncio
async def test_factor_campaign_worker_recovers_stale_before_claim(monkeypatch):
    events: list[str] = []

    async def fake_ensure_tables():
        events.append("ensure")

    async def fake_recover(*, stale_after_minutes, worker_id):
        events.append(f"recover:{stale_after_minutes}:{worker_id}")
        return 1

    async def fake_claim(*, worker_id, lease_seconds):
        events.append(f"claim:{worker_id}:{lease_seconds}")
        return None

    async def fake_record_worker_event(**kwargs):
        events.append(f"record:{kwargs['event_type']}")
        return "event-1"

    monkeypatch.setattr(worker, "ensure_factor_campaign_tables", fake_ensure_tables)
    monkeypatch.setattr(worker, "recover_stale_running_factor_campaigns", fake_recover)
    monkeypatch.setattr(worker, "claim_next_pending_factor_campaign", fake_claim)
    monkeypatch.setattr(
        worker, "record_factor_campaign_worker_event", fake_record_worker_event
    )

    processed = await worker.run_worker(
        once=True,
        poll_interval=0.1,
        idle_limit=None,
        recover_stale_after_minutes=7,
        worker_id="worker-1",
        max_claims=None,
        concurrency=1,
        heartbeat_interval=None,
        lease_seconds=60,
    )

    assert processed == 0
    assert events == [
        "ensure",
        "record:started",
        "recover:7:worker-1",
        "record:recovered",
        "claim:worker-1:60",
        "record:idle",
        "record:stopped",
    ]


@pytest.mark.asyncio
async def test_factor_campaign_worker_records_processed_campaign(monkeypatch):
    events: list[dict] = []

    async def fake_ensure_tables():
        return None

    async def fake_recover(*, stale_after_minutes, worker_id):
        return 0

    async def fake_claim(*, worker_id, lease_seconds):
        return {
            "id": "campaign-1",
            "tenantId": "tenant",
            "userId": "user",
            "status": "completed",
            "summary": {"completedRuns": 2},
            "items": [{"id": "item-1"}, {"id": "item-2"}],
        }

    async def fake_record_worker_event(**kwargs):
        events.append(kwargs)
        return "event-1"

    monkeypatch.setattr(worker, "ensure_factor_campaign_tables", fake_ensure_tables)
    monkeypatch.setattr(worker, "recover_stale_running_factor_campaigns", fake_recover)
    monkeypatch.setattr(worker, "claim_next_pending_factor_campaign", fake_claim)
    monkeypatch.setattr(
        worker, "record_factor_campaign_worker_event", fake_record_worker_event
    )

    processed = await worker.run_worker(
        once=True,
        poll_interval=0.1,
        idle_limit=None,
        recover_stale_after_minutes=7,
        worker_id="worker-1",
        max_claims=None,
        concurrency=1,
        heartbeat_interval=None,
        lease_seconds=60,
    )

    assert processed == 1
    assert [event["event_type"] for event in events] == [
        "started",
        "processed",
        "stopped",
    ]
    processed_event = events[1]
    assert processed_event == {
        "event_type": "processed",
        "campaign_id": "campaign-1",
        "tenant_id": "tenant",
        "user_id": "user",
        "worker_id": "worker-1",
        "attempt_no": 1,
        "duration_ms": processed_event["duration_ms"],
        "heartbeat_at": None,
        "status": "completed",
        "details": {"completedRuns": 2, "itemCount": 2},
    }
    assert events[0]["details"]["maxClaims"] == 1
    assert events[2]["details"] == {"processed": 1, "reason": "once_processed"}
    assert isinstance(processed_event["duration_ms"], int)
    assert processed_event["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_factor_campaign_worker_records_claim_failure(monkeypatch):
    events: list[dict] = []

    async def fake_ensure_tables():
        return None

    async def fake_recover(*, stale_after_minutes, worker_id):
        return 0

    async def fake_claim(*, worker_id, lease_seconds):
        raise RuntimeError("claim failed")

    async def fake_record_worker_event(**kwargs):
        events.append(kwargs)
        return "event-1"

    monkeypatch.setattr(worker, "ensure_factor_campaign_tables", fake_ensure_tables)
    monkeypatch.setattr(worker, "recover_stale_running_factor_campaigns", fake_recover)
    monkeypatch.setattr(worker, "claim_next_pending_factor_campaign", fake_claim)
    monkeypatch.setattr(
        worker, "record_factor_campaign_worker_event", fake_record_worker_event
    )

    with pytest.raises(RuntimeError, match="claim failed"):
        await worker.run_worker(
            once=True,
            poll_interval=0.1,
            idle_limit=None,
            recover_stale_after_minutes=7,
            worker_id="worker-1",
            max_claims=None,
            concurrency=1,
            heartbeat_interval=None,
            lease_seconds=60,
        )

    assert [event["event_type"] for event in events] == ["started", "failed"]
    assert events[1] == {
        "event_type": "failed",
        "campaign_id": None,
        "tenant_id": None,
        "user_id": None,
        "worker_id": "worker-1",
        "attempt_no": 1,
        "duration_ms": None,
        "heartbeat_at": None,
        "status": "failed",
        "details": {"error": "claim failed"},
    }


@pytest.mark.asyncio
async def test_factor_campaign_worker_claims_concurrently_until_max_claims(monkeypatch):
    claim_calls: list[tuple[str, int | None]] = []
    recorded: list[dict] = []

    async def fake_ensure_tables():
        return None

    async def fake_recover(*, stale_after_minutes, worker_id):
        return 0

    async def fake_claim(*, worker_id, lease_seconds):
        claim_calls.append((worker_id, lease_seconds))
        idx = len(claim_calls)
        return {
            "id": f"campaign-{idx}",
            "tenantId": "tenant",
            "userId": "user",
            "status": "completed",
            "summary": {"completedRuns": idx},
            "items": [{"id": f"item-{idx}"}],
        }

    async def fake_record_worker_event(**kwargs):
        recorded.append(kwargs)
        return "event-1"

    monkeypatch.setattr(worker, "ensure_factor_campaign_tables", fake_ensure_tables)
    monkeypatch.setattr(worker, "recover_stale_running_factor_campaigns", fake_recover)
    monkeypatch.setattr(worker, "claim_next_pending_factor_campaign", fake_claim)
    monkeypatch.setattr(
        worker, "record_factor_campaign_worker_event", fake_record_worker_event
    )

    processed = await worker.run_worker(
        once=False,
        poll_interval=0.1,
        idle_limit=None,
        recover_stale_after_minutes=7,
        worker_id="worker-2",
        max_claims=2,
        concurrency=2,
        heartbeat_interval=None,
        lease_seconds=120,
    )

    assert processed == 2
    assert claim_calls == [("worker-2", 120), ("worker-2", 120)]
    processed_events = [
        event for event in recorded if event["event_type"] == "processed"
    ]
    assert [event["campaign_id"] for event in processed_events] == [
        "campaign-1",
        "campaign-2",
    ]
    assert [event["attempt_no"] for event in processed_events] == [1, 2]
    assert recorded[0]["event_type"] == "started"
    assert recorded[-1]["event_type"] == "stopped"
    assert recorded[-1]["details"] == {"processed": 2, "reason": "max_claims_reached"}
    assert all(event["worker_id"] == "worker-2" for event in recorded)
