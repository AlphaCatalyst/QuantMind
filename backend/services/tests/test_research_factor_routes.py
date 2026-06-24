from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.services.api.routers import research
from backend.services.api.routers.research_schemas import (
    FactorApprovalPolicyUpdateRequest,
    FactorTrainingApprovalRequestCreateRequest,
    FactorTrainingApprovalRequestReviewRequest,
    FactorTrainingApproveRequest,
    FactorValueBackfillCreateRequest,
)


@pytest.mark.asyncio
async def test_approve_factor_training_route_wraps_service_response(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_approve_service(
        tenant_id, user_id, training_id, payload, *, approver_user_id=None
    ):
        captured.update(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "training_id": training_id,
                "payload": payload,
                "approver_user_id": approver_user_id,
            }
        )
        return {
            "training": {"id": training_id},
            "approval": {"model_id": "model_train_1"},
        }

    monkeypatch.setattr(
        research, "approve_factor_training_run_service", fake_approve_service
    )

    result = await research.approve_factor_training_run(
        "factor-training-1",
        FactorTrainingApproveRequest(
            set_default_model=True,
            reason="reviewed",
            metadata={"ticket": "FR-1"},
        ),
        current_user={"tenant_id": "tenant-1", "user_id": "user-1", "is_admin": True},
    )

    assert captured == {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "training_id": "factor-training-1",
        "payload": {
            "set_default_model": True,
            "approve_default_model": False,
            "reason": "reviewed",
            "metadata": {"ticket": "FR-1"},
        },
        "approver_user_id": "user-1",
    }
    assert result == {
        "code": 0,
        "message": "ok",
        "data": {
            "training": {"id": "factor-training-1"},
            "approval": {"model_id": "model_train_1"},
        },
    }


@pytest.mark.asyncio
async def test_factor_research_health_route_wraps_service(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_health_service(tenant_id, user_id, *, window_hours=24):
        captured.update(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "window_hours": window_hours,
            }
        )
        return {"status": "healthy", "alerts": []}

    monkeypatch.setattr(
        research, "get_factor_research_health_service", fake_health_service
    )

    result = await research.get_factor_research_health(
        window_hours=12,
        current_user={"tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert captured == {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "window_hours": 12,
    }
    assert result["data"]["health"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_factor_campaign_worker_events_route_wraps_service(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_worker_events_service(
        tenant_id,
        user_id,
        *,
        campaign_id=None,
        worker_id=None,
        event_type=None,
        status=None,
        limit=20,
        offset=0,
    ):
        captured.update(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "campaign_id": campaign_id,
                "worker_id": worker_id,
                "event_type": event_type,
                "status": status,
                "limit": limit,
                "offset": offset,
            }
        )
        return {"items": [{"id": "event-1"}], "total": 1}

    monkeypatch.setattr(
        research,
        "list_factor_campaign_worker_events_service",
        fake_worker_events_service,
    )

    result = await research.list_factor_campaign_worker_events(
        campaign_id="campaign-1",
        worker_id="worker-1",
        event_type="processed",
        status="completed",
        limit=7,
        offset=2,
        current_user={"tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert captured == {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "campaign_id": "campaign-1",
        "worker_id": "worker-1",
        "event_type": "processed",
        "status": "completed",
        "limit": 7,
        "offset": 2,
    }
    assert result["data"]["items"] == [{"id": "event-1"}]


@pytest.mark.asyncio
async def test_create_factor_value_backfill_job_route_wraps_service(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_create_service(tenant_id, user_id, payload):
        captured.update(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "payload": payload,
            }
        )
        return {"id": "job-1", "status": "pending"}

    monkeypatch.setattr(
        research,
        "create_factor_value_backfill_job_service",
        fake_create_service,
    )

    result = await research.create_factor_value_backfill_job(
        FactorValueBackfillCreateRequest(
            run_ids=["run-1"],
            start_date="2026-01-01",
            end_date="2026-01-31",
            dry_run=True,
            metadata={"ticket": "FR-1"},
        ),
        current_user={"tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert captured["tenant_id"] == "tenant-1"
    assert captured["user_id"] == "user-1"
    assert captured["payload"]["run_ids"] == ["run-1"]
    assert captured["payload"]["dry_run"] is True
    assert result["data"]["job"]["id"] == "job-1"


@pytest.mark.asyncio
async def test_run_factor_value_backfill_job_route_wraps_service(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_run_service(tenant_id, user_id, job_id, *, worker_id=None):
        captured.update(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "job_id": job_id,
                "worker_id": worker_id,
            }
        )
        return {"id": job_id, "status": "completed"}

    monkeypatch.setattr(
        research,
        "execute_factor_value_backfill_job_service",
        fake_run_service,
    )

    result = await research.run_factor_value_backfill_job(
        "job-1",
        current_user={"tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert captured == {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "job_id": "job-1",
        "worker_id": "api:user-1",
    }
    assert result["data"]["job"]["status"] == "completed"


@pytest.mark.asyncio
async def test_list_factor_value_backfill_events_route_wraps_service(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_events_service(
        tenant_id,
        user_id,
        *,
        job_id=None,
        worker_id=None,
        event_type=None,
        status=None,
        limit=20,
        offset=0,
    ):
        captured.update(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "job_id": job_id,
                "worker_id": worker_id,
                "event_type": event_type,
                "status": status,
                "limit": limit,
                "offset": offset,
            }
        )
        return {"items": [{"id": "event-1"}], "total": 1}

    monkeypatch.setattr(
        research,
        "list_factor_value_backfill_events_service",
        fake_events_service,
    )

    result = await research.list_factor_value_backfill_events(
        job_id="job-1",
        worker_id="worker-1",
        event_type="claimed",
        status="running",
        limit=7,
        offset=2,
        current_user={"tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert captured == {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "job_id": "job-1",
        "worker_id": "worker-1",
        "event_type": "claimed",
        "status": "running",
        "limit": 7,
        "offset": 2,
    }
    assert result["data"]["items"] == [{"id": "event-1"}]


@pytest.mark.asyncio
async def test_cancel_factor_value_backfill_job_route_wraps_service(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_cancel_service(tenant_id, user_id, job_id, *, reason="manual_cancel"):
        captured.update(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "job_id": job_id,
                "reason": reason,
            }
        )
        return {"id": job_id, "status": "cancelled"}

    monkeypatch.setattr(
        research,
        "cancel_factor_value_backfill_job_service",
        fake_cancel_service,
    )

    result = await research.cancel_factor_value_backfill_job(
        "job-1",
        reason="stop",
        current_user={"tenant_id": "tenant-1", "user_id": "user-1"},
    )

    assert captured == {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "job_id": "job-1",
        "reason": "stop",
    }
    assert result["data"]["job"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_approve_factor_training_route_maps_missing_to_404(monkeypatch):
    async def fake_approve_service(*args, **kwargs):
        raise LookupError("factor training run not found")

    monkeypatch.setattr(
        research, "approve_factor_training_run_service", fake_approve_service
    )

    with pytest.raises(HTTPException) as exc_info:
        await research.approve_factor_training_run(
            "missing",
            FactorTrainingApproveRequest(set_default_model=True),
            current_user={
                "tenant_id": "tenant-1",
                "user_id": "user-1",
                "is_admin": True,
            },
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "factor training run not found"


@pytest.mark.asyncio
async def test_approve_factor_training_route_maps_gate_rejection_to_400(monkeypatch):
    async def fake_approve_service(*args, **kwargs):
        raise ValueError("factor training gate does not allow default model promotion")

    monkeypatch.setattr(
        research, "approve_factor_training_run_service", fake_approve_service
    )

    with pytest.raises(HTTPException) as exc_info:
        await research.approve_factor_training_run(
            "factor-training-1",
            FactorTrainingApproveRequest(set_default_model=True),
            current_user={
                "tenant_id": "tenant-1",
                "user_id": "user-1",
                "is_admin": True,
            },
        )

    assert exc_info.value.status_code == 400
    assert (
        exc_info.value.detail
        == "factor training gate does not allow default model promotion"
    )


@pytest.mark.asyncio
async def test_approve_factor_training_route_requires_factor_approval_permission(
    monkeypatch,
):
    async def fake_can_review(_current_user):
        return False

    monkeypatch.setattr(research, "_can_review_factor_approval", fake_can_review)

    with pytest.raises(HTTPException) as exc_info:
        await research.approve_factor_training_run(
            "factor-training-1",
            FactorTrainingApproveRequest(set_default_model=True),
            current_user={
                "tenant_id": "tenant-1",
                "user_id": "user-1",
                "is_admin": False,
            },
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "permission required: factor.approve"


@pytest.mark.asyncio
async def test_approve_factor_training_route_allows_factor_approval_permission(
    monkeypatch,
):
    captured: dict[str, object] = {}

    async def fake_can_review(_current_user):
        return True

    async def fake_approve_service(
        tenant_id, user_id, training_id, payload, *, approver_user_id=None
    ):
        captured.update(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "training_id": training_id,
                "approver_user_id": approver_user_id,
            }
        )
        return {"training": {"id": training_id}}

    monkeypatch.setattr(research, "_can_review_factor_approval", fake_can_review)
    monkeypatch.setattr(
        research, "approve_factor_training_run_service", fake_approve_service
    )

    result = await research.approve_factor_training_run(
        "factor-training-1",
        FactorTrainingApproveRequest(set_default_model=True),
        current_user={
            "tenant_id": "tenant-1",
            "user_id": "reviewer-1",
            "is_admin": False,
        },
    )

    assert captured == {
        "tenant_id": "tenant-1",
        "user_id": "reviewer-1",
        "training_id": "factor-training-1",
        "approver_user_id": "reviewer-1",
    }
    assert result["data"]["training"]["id"] == "factor-training-1"


@pytest.mark.asyncio
async def test_create_factor_training_approval_request_route_wraps_service(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_create_request(tenant_id, user_id, training_id, payload):
        captured.update(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "training_id": training_id,
                "payload": payload,
            }
        )
        return {"id": "approval-request-1", "status": "pending"}

    monkeypatch.setattr(
        research,
        "create_factor_training_approval_request_service",
        fake_create_request,
    )

    result = await research.create_factor_training_approval_request(
        "factor-training-1",
        FactorTrainingApprovalRequestCreateRequest(
            reason="please approve",
            metadata={"ticket": "FR-2"},
        ),
        current_user={"tenant_id": "tenant-1", "user_id": "user-1", "is_admin": False},
    )

    assert captured == {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "training_id": "factor-training-1",
        "payload": {
            "reason": "please approve",
            "metadata": {"ticket": "FR-2"},
            "requested_by": "user-1",
        },
    }
    assert result["data"]["request"]["status"] == "pending"


@pytest.mark.asyncio
async def test_cancel_factor_campaign_route_wraps_service(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_cancel_campaign(tenant_id, user_id, campaign_id, *, reason):
        captured.update(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "campaign_id": campaign_id,
                "reason": reason,
            }
        )
        return {"id": campaign_id, "status": "cancelled"}

    monkeypatch.setattr(
        research, "cancel_factor_campaign_service", fake_cancel_campaign
    )

    result = await research.cancel_factor_campaign(
        "campaign-1",
        reason="manual",
        current_user={"tenant_id": "tenant-1", "user_id": "user-1", "is_admin": False},
    )

    assert captured == {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "campaign_id": "campaign-1",
        "reason": "manual",
    }
    assert result["data"]["campaign"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_factor_campaign_route_maps_inactive_to_400(monkeypatch):
    async def fake_cancel_campaign(*args, **kwargs):
        raise ValueError("factor campaign is not active")

    monkeypatch.setattr(
        research, "cancel_factor_campaign_service", fake_cancel_campaign
    )

    with pytest.raises(HTTPException) as exc_info:
        await research.cancel_factor_campaign(
            "campaign-1",
            current_user={
                "tenant_id": "tenant-1",
                "user_id": "user-1",
                "is_admin": False,
            },
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "factor campaign is not active"


@pytest.mark.asyncio
async def test_list_factor_run_values_route_wraps_service(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_list_values(tenant_id, user_id, run_id, *, limit, offset):
        captured.update(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "run_id": run_id,
                "limit": limit,
                "offset": offset,
            }
        )
        return {"items": [], "summary": {"total": 0}, "pagination": {}}

    monkeypatch.setattr(research, "list_factor_run_values_service", fake_list_values)

    result = await research.list_factor_run_values(
        "run-1",
        limit=25,
        offset=5,
        current_user={"tenant_id": "tenant-1", "user_id": "user-1", "is_admin": False},
    )

    assert captured == {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "run_id": "run-1",
        "limit": 25,
        "offset": 5,
    }
    assert result["data"]["summary"]["total"] == 0


@pytest.mark.asyncio
async def test_list_factor_run_values_route_maps_missing_run_to_404(monkeypatch):
    async def fake_list_values(*args, **kwargs):
        raise LookupError("factor evaluation run not found")

    monkeypatch.setattr(research, "list_factor_run_values_service", fake_list_values)

    with pytest.raises(HTTPException) as exc_info:
        await research.list_factor_run_values(
            "run-1",
            current_user={
                "tenant_id": "tenant-1",
                "user_id": "user-1",
                "is_admin": False,
            },
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "factor evaluation run not found"


@pytest.mark.asyncio
async def test_list_factor_approval_requests_scopes_non_reviewers(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_can_review(_current_user):
        return False

    async def fake_list_requests(tenant_id, *, user_id, status, limit, offset):
        captured.update(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "status": status,
                "limit": limit,
                "offset": offset,
            }
        )
        return {"items": [], "total": 0, "pagination": {}}

    monkeypatch.setattr(research, "_can_review_factor_approval", fake_can_review)
    monkeypatch.setattr(
        research, "list_factor_approval_requests_service", fake_list_requests
    )

    await research.list_factor_approval_requests(
        status="pending",
        limit=5,
        offset=10,
        current_user={"tenant_id": "tenant-1", "user_id": "user-1", "is_admin": False},
    )

    assert captured == {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "status": "pending",
        "limit": 5,
        "offset": 10,
    }


@pytest.mark.asyncio
async def test_list_factor_approval_requests_allows_reviewers_to_view_tenant(
    monkeypatch,
):
    captured: dict[str, object] = {}

    async def fake_can_review(_current_user):
        return True

    async def fake_list_requests(tenant_id, *, user_id, status, limit, offset):
        captured.update({"tenant_id": tenant_id, "user_id": user_id})
        return {"items": [], "total": 0, "pagination": {}}

    monkeypatch.setattr(research, "_can_review_factor_approval", fake_can_review)
    monkeypatch.setattr(
        research, "list_factor_approval_requests_service", fake_list_requests
    )

    await research.list_factor_approval_requests(
        status=None,
        limit=20,
        offset=0,
        current_user={
            "tenant_id": "tenant-1",
            "user_id": "reviewer-1",
            "is_admin": False,
        },
    )

    assert captured == {"tenant_id": "tenant-1", "user_id": None}


@pytest.mark.asyncio
async def test_review_factor_training_approval_request_route_requires_factor_approval_permission(
    monkeypatch,
):
    async def fake_can_review(_current_user):
        return False

    monkeypatch.setattr(research, "_can_review_factor_approval", fake_can_review)

    with pytest.raises(HTTPException) as exc_info:
        await research.review_factor_training_approval_request(
            "approval-request-1",
            FactorTrainingApprovalRequestReviewRequest(approve=True),
            current_user={
                "tenant_id": "tenant-1",
                "user_id": "user-1",
                "is_admin": False,
            },
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "permission required: factor.approve"


@pytest.mark.asyncio
async def test_review_factor_training_approval_request_route_wraps_service(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_review_request(tenant_id, request_id, reviewer_user_id, payload):
        captured.update(
            {
                "tenant_id": tenant_id,
                "request_id": request_id,
                "reviewer_user_id": reviewer_user_id,
                "payload": payload,
            }
        )
        return {
            "request": {
                "id": request_id,
                "status": "approved",
                "reviewerUserId": reviewer_user_id,
            },
            "approvalResult": {"approval": {"approved_by": reviewer_user_id}},
        }

    monkeypatch.setattr(
        research,
        "review_factor_training_approval_request_service",
        fake_review_request,
    )

    result = await research.review_factor_training_approval_request(
        "approval-request-1",
        FactorTrainingApprovalRequestReviewRequest(
            approve=True,
            decision="approve",
            reviewer_note="ok",
            metadata={"review": "ops"},
        ),
        current_user={"tenant_id": "tenant-1", "user_id": "admin-1", "is_admin": True},
    )

    assert captured == {
        "tenant_id": "tenant-1",
        "request_id": "approval-request-1",
        "reviewer_user_id": "admin-1",
        "payload": {
            "approve": True,
            "decision": "approve",
            "reason": None,
            "reviewer_note": "ok",
            "metadata": {"review": "ops"},
        },
    }
    assert result["data"]["request"]["status"] == "approved"


@pytest.mark.asyncio
async def test_factor_approval_policy_routes_read_and_update(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_get_policy(tenant_id):
        return {"tenantId": tenant_id, "minApprovals": 1}

    async def fake_can_review(_current_user):
        return True

    async def fake_upsert_policy(tenant_id, payload, *, updated_by=None):
        captured.update(
            {"tenant_id": tenant_id, "payload": payload, "updated_by": updated_by}
        )
        return {"tenantId": tenant_id, "minApprovals": payload["min_approvals"]}

    monkeypatch.setattr(research, "get_factor_approval_policy_service", fake_get_policy)
    monkeypatch.setattr(research, "_can_review_factor_approval", fake_can_review)
    monkeypatch.setattr(
        research, "upsert_factor_approval_policy_service", fake_upsert_policy
    )

    read_result = await research.get_factor_approval_policy(
        current_user={"tenant_id": "tenant-1", "user_id": "reviewer-1"}
    )
    assert read_result["data"]["policy"]["minApprovals"] == 1

    update_result = await research.update_factor_approval_policy(
        FactorApprovalPolicyUpdateRequest(
            allow_direct_approval=False,
            allow_self_approval=False,
            min_approvals=2,
        ),
        current_user={"tenant_id": "tenant-1", "user_id": "reviewer-1"},
    )

    assert captured == {
        "tenant_id": "tenant-1",
        "payload": {
            "allow_direct_approval": False,
            "allow_self_approval": False,
            "min_approvals": 2,
        },
        "updated_by": "reviewer-1",
    }
    assert update_result["data"]["policy"]["minApprovals"] == 2


@pytest.mark.asyncio
async def test_update_factor_approval_policy_requires_factor_permission(monkeypatch):
    async def fake_can_review(_current_user):
        return False

    monkeypatch.setattr(research, "_can_review_factor_approval", fake_can_review)

    with pytest.raises(HTTPException) as exc_info:
        await research.update_factor_approval_policy(
            FactorApprovalPolicyUpdateRequest(min_approvals=2),
            current_user={"tenant_id": "tenant-1", "user_id": "user-1"},
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "permission required: factor.approve"


@pytest.mark.asyncio
async def test_review_factor_training_approval_request_route_allows_factor_permission(
    monkeypatch,
):
    captured: dict[str, object] = {}

    async def fake_can_review(_current_user):
        return True

    async def fake_review_request(tenant_id, request_id, reviewer_user_id, payload):
        captured.update(
            {
                "tenant_id": tenant_id,
                "request_id": request_id,
                "reviewer_user_id": reviewer_user_id,
            }
        )
        return {
            "request": {"id": request_id, "status": "approved"},
            "approvalResult": None,
        }

    monkeypatch.setattr(research, "_can_review_factor_approval", fake_can_review)
    monkeypatch.setattr(
        research,
        "review_factor_training_approval_request_service",
        fake_review_request,
    )

    result = await research.review_factor_training_approval_request(
        "approval-request-1",
        FactorTrainingApprovalRequestReviewRequest(approve=True),
        current_user={
            "tenant_id": "tenant-1",
            "user_id": "reviewer-1",
            "is_admin": False,
        },
    )

    assert captured == {
        "tenant_id": "tenant-1",
        "request_id": "approval-request-1",
        "reviewer_user_id": "reviewer-1",
    }
    assert result["data"]["request"]["status"] == "approved"
