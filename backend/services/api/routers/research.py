"""投研平台聚合接口。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

import backend.services.api.routers.research_service as _research_service
from backend.services.api.routers.research_schemas import (
    FactorApprovalPolicyUpdateRequest,
    FactorCampaignCreateRequest,
    FactorCandidateCreateRequest,
    FactorCandidateEvaluateRequest,
    FactorCandidatePromoteRequest,
    FactorShadowSignalPublishRequest,
    FactorTrainingApproveRequest,
    FactorTrainingApprovalRequestCreateRequest,
    FactorTrainingApprovalRequestReviewRequest,
    FactorTrainingLaunchRequest,
    FactorValueBackfillCreateRequest,
    PoolAddRequest,
    SymbolsFeaturesRequest,
    WatchlistAddRequest,
)
from backend.services.api.routers.research_factor_service import (
    approve_factor_training_run as approve_factor_training_run_service,
    cancel_factor_campaign as cancel_factor_campaign_service,
    create_factor_campaign as create_factor_campaign_service,
    create_factor_candidate as create_factor_candidate_service,
    create_factor_training_approval_request as create_factor_training_approval_request_service,
    create_factor_evaluation_run as create_factor_evaluation_run_service,
    get_factor_campaign as get_factor_campaign_service,
    get_factor_approval_policy as get_factor_approval_policy_service,
    get_factor_evaluation_run as get_factor_evaluation_run_service,
    get_factor_research_health as get_factor_research_health_service,
    list_factor_approval_audits as list_factor_approval_audits_service,
    list_factor_approval_requests as list_factor_approval_requests_service,
    list_factor_campaigns as list_factor_campaigns_service,
    list_factor_feature_promotions as list_factor_feature_promotions_service,
    list_factor_candidates as list_factor_candidates_service,
    list_factor_signal_runs as list_factor_signal_runs_service,
    list_factor_training_runs as list_factor_training_runs_service,
    launch_factor_promotion_training as launch_factor_promotion_training_service,
    materialize_factor_feature_promotion as materialize_factor_feature_promotion_service,
    publish_factor_shadow_signal as publish_factor_shadow_signal_service,
    review_factor_training_approval_request as review_factor_training_approval_request_service,
    promote_factor_candidate as promote_factor_candidate_service,
    rollback_factor_feature_promotion as rollback_factor_feature_promotion_service,
    upsert_factor_approval_policy as upsert_factor_approval_policy_service,
)
from backend.services.engine.research.factor_campaign_service import (
    list_factor_campaign_worker_events as list_factor_campaign_worker_events_service,
)
from backend.services.engine.research.factor_value_store import (
    list_factor_run_values as list_factor_run_values_service,
)
from backend.services.engine.research.factor_value_backfill import (
    cancel_factor_value_backfill_job as cancel_factor_value_backfill_job_service,
    create_factor_value_backfill_job as create_factor_value_backfill_job_service,
    execute_factor_value_backfill_job as execute_factor_value_backfill_job_service,
    list_factor_value_backfill_events as list_factor_value_backfill_events_service,
    list_factor_value_backfill_jobs as list_factor_value_backfill_jobs_service,
)
from backend.services.api.routers.research_service import (
    add_to_research_pool as add_to_research_pool_service,
    add_to_watchlist as add_to_watchlist_service,
    get_available_models as get_available_models_service,
    get_inference_runs as get_inference_runs_service,
    get_research_overview as get_research_overview_service,
    get_research_universe as get_research_universe_service,
    get_stock_kline as get_stock_kline_service,
    get_symbols_features as get_symbols_features_service,
    get_user_research_pool as get_user_research_pool_service,
    get_user_watchlist as get_user_watchlist_service,
    remove_from_research_pool as remove_from_research_pool_service,
    remove_from_watchlist as remove_from_watchlist_service,
)
from backend.services.api.user_app.middleware.auth import get_current_user
from backend.services.api.user_app.services.rbac_service import RBACService
from backend.shared.database_manager_v2 import get_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/research", tags=["Research"])
FACTOR_APPROVAL_PERMISSION = "factor.approve"

# 向后兼容：保留测试与历史调用使用的私有符号
_format_candidate_record = _research_service._format_candidate_record  # noqa: SLF001


def _ok(data: dict):
    return {"code": 0, "message": "ok", "data": data}


async def _can_review_factor_approval(current_user: dict) -> bool:
    """Return whether the user can approve factor research model promotions."""
    if current_user.get("is_admin"):
        return True

    user_id = str(current_user.get("user_id") or "")
    if not user_id:
        return False

    try:
        async with get_session(read_only=True) as session:
            return await RBACService(session).has_permission(
                user_id, FACTOR_APPROVAL_PERMISSION
            )
    except Exception as exc:  # pragma: no cover - defensive auth hardening
        logger.warning(
            "factor approval permission lookup failed for user %s: %s",
            user_id,
            exc,
        )
        return False


async def _do_get_overview(  # noqa: SLF001
    tid: str,
    uid: str,
    model_id: str | None,
    run_id: str | None,
    limit: int,
    offset: int,
):
    original_get_session = _research_service.get_session
    _research_service.get_session = get_session
    try:
        return await _research_service._do_get_overview(
            tid, uid, model_id, run_id, limit, offset
        )  # noqa: SLF001
    finally:
        _research_service.get_session = original_get_session


@router.get("/models")
async def get_available_models(current_user: dict = Depends(get_current_user)):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return await get_available_models_service(tid, uid)


@router.post("/factors/candidates")
async def create_factor_candidate(
    req: FactorCandidateCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        candidate = await create_factor_candidate_service(tid, uid, req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok({"candidate": candidate})


@router.get("/factors/candidates")
async def list_factor_candidates(
    status: str | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return _ok(
        await list_factor_candidates_service(
            tid, uid, status=status, limit=limit, offset=offset
        )
    )


@router.get("/factors/health")
async def get_factor_research_health(
    window_hours: int = Query(24),
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return _ok(
        {
            "health": await get_factor_research_health_service(
                tid, uid, window_hours=window_hours
            )
        }
    )


@router.get("/factors/campaign-worker-events")
async def list_factor_campaign_worker_events(
    campaign_id: str | None = Query(None),
    worker_id: str | None = Query(None),
    event_type: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(20),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return _ok(
        await list_factor_campaign_worker_events_service(
            tid,
            uid,
            campaign_id=campaign_id,
            worker_id=worker_id,
            event_type=event_type,
            status=status,
            limit=limit,
            offset=offset,
        )
    )


@router.get("/factors/promotions")
async def list_factor_feature_promotions(
    limit: int = Query(50),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return _ok(
        await list_factor_feature_promotions_service(
            tid, uid, limit=limit, offset=offset
        )
    )


@router.get("/factors/signals")
async def list_factor_signal_runs(
    limit: int = Query(50),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return _ok(
        await list_factor_signal_runs_service(tid, uid, limit=limit, offset=offset)
    )


@router.get("/factors/trainings")
async def list_factor_training_runs(
    limit: int = Query(50),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return _ok(
        await list_factor_training_runs_service(tid, uid, limit=limit, offset=offset)
    )


@router.get("/factors/approvals")
async def list_factor_approval_audits(
    training_id: str | None = Query(None),
    model_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return _ok(
        await list_factor_approval_audits_service(
            tid,
            uid,
            training_id=training_id,
            model_id=model_id,
            status=status,
            limit=limit,
            offset=offset,
        )
    )


@router.get("/factors/approval-policy")
async def get_factor_approval_policy(current_user: dict = Depends(get_current_user)):
    tid = str(current_user["tenant_id"])
    return _ok({"policy": await get_factor_approval_policy_service(tid)})


@router.put("/factors/approval-policy")
async def update_factor_approval_policy(
    req: FactorApprovalPolicyUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    if not await _can_review_factor_approval(current_user):
        raise HTTPException(
            status_code=403,
            detail=f"permission required: {FACTOR_APPROVAL_PERMISSION}",
        )
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        policy = await upsert_factor_approval_policy_service(
            tid,
            req.model_dump(exclude_none=True),
            updated_by=uid,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok({"policy": policy})


@router.post("/factors/trainings/{training_id}/approval-requests")
async def create_factor_training_approval_request(
    training_id: str,
    req: FactorTrainingApprovalRequestCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        request = await create_factor_training_approval_request_service(
            tid,
            uid,
            training_id,
            {**req.model_dump(), "requested_by": uid},
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok({"request": request})


@router.get("/factors/approval-requests")
async def list_factor_approval_requests(
    status: str | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    can_review = await _can_review_factor_approval(current_user)
    scope_user_id = None if can_review else uid
    return _ok(
        await list_factor_approval_requests_service(
            tid,
            user_id=scope_user_id,
            status=status,
            limit=limit,
            offset=offset,
        )
    )


@router.post("/factors/approval-requests/{request_id}/review")
async def review_factor_training_approval_request(
    request_id: str,
    req: FactorTrainingApprovalRequestReviewRequest,
    current_user: dict = Depends(get_current_user),
):
    if not await _can_review_factor_approval(current_user):
        raise HTTPException(
            status_code=403,
            detail=f"permission required: {FACTOR_APPROVAL_PERMISSION}",
        )
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        result = await review_factor_training_approval_request_service(
            tid,
            request_id,
            uid,
            req.model_dump(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok(result)


@router.post("/factors/trainings/{training_id}/approve")
async def approve_factor_training_run(
    training_id: str,
    req: FactorTrainingApproveRequest,
    current_user: dict = Depends(get_current_user),
):
    if not await _can_review_factor_approval(current_user):
        raise HTTPException(
            status_code=403,
            detail=f"permission required: {FACTOR_APPROVAL_PERMISSION}",
        )
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        result = await approve_factor_training_run_service(
            tid,
            uid,
            training_id,
            req.model_dump(),
            approver_user_id=uid,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok(result)


@router.post("/factors/campaigns")
async def create_factor_campaign(
    req: FactorCampaignCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        campaign = await create_factor_campaign_service(tid, uid, req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok({"campaign": campaign})


@router.get("/factors/campaigns")
async def list_factor_campaigns(
    limit: int = Query(50),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return _ok(
        await list_factor_campaigns_service(tid, uid, limit=limit, offset=offset)
    )


@router.get("/factors/campaigns/{campaign_id}")
async def get_factor_campaign(
    campaign_id: str, current_user: dict = Depends(get_current_user)
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        campaign = await get_factor_campaign_service(tid, uid, campaign_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _ok({"campaign": campaign})


@router.post("/factors/campaigns/{campaign_id}/cancel")
async def cancel_factor_campaign(
    campaign_id: str,
    reason: str = "manual_cancel",
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        campaign = await cancel_factor_campaign_service(
            tid, uid, campaign_id, reason=reason
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok({"campaign": campaign})


@router.post("/factors/value-backfills")
async def create_factor_value_backfill_job(
    req: FactorValueBackfillCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        job = await create_factor_value_backfill_job_service(
            tid,
            uid,
            req.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok({"job": job})


@router.get("/factors/value-backfills")
async def list_factor_value_backfill_jobs(
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    jobs = await list_factor_value_backfill_jobs_service(
        tid,
        uid,
        status=status,
        limit=limit,
        offset=offset,
    )
    return _ok(jobs)


@router.get("/factors/value-backfill-events")
async def list_factor_value_backfill_events(
    job_id: str | None = Query(default=None),
    worker_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    events = await list_factor_value_backfill_events_service(
        tid,
        uid,
        job_id=job_id,
        worker_id=worker_id,
        event_type=event_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    return _ok(events)


@router.post("/factors/value-backfills/{job_id}/run")
async def run_factor_value_backfill_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        job = await execute_factor_value_backfill_job_service(
            tid,
            uid,
            job_id,
            worker_id=f"api:{uid}",
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _ok({"job": job})


@router.post("/factors/value-backfills/{job_id}/cancel")
async def cancel_factor_value_backfill_job(
    job_id: str,
    reason: str = Query(default="manual_cancel"),
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        job = await cancel_factor_value_backfill_job_service(
            tid,
            uid,
            job_id,
            reason=reason,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _ok({"job": job})


@router.post("/factors/candidates/{candidate_id}/evaluate")
async def create_factor_evaluation_run(
    candidate_id: str,
    req: FactorCandidateEvaluateRequest,
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        run = await create_factor_evaluation_run_service(
            tid, uid, candidate_id, req.model_dump()
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _ok({"run": run})


@router.post("/factors/candidates/{candidate_id}/promote")
async def promote_factor_candidate(
    candidate_id: str,
    req: FactorCandidatePromoteRequest,
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        promotion = await promote_factor_candidate_service(
            tid, uid, candidate_id, req.model_dump()
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok({"promotion": promotion})


@router.post("/factors/promotions/{promotion_id}/materialize")
async def materialize_factor_feature_promotion(
    promotion_id: str,
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        promotion = await materialize_factor_feature_promotion_service(
            tid, uid, promotion_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok({"promotion": promotion})


@router.post("/factors/promotions/{promotion_id}/rollback")
async def rollback_factor_feature_promotion(
    promotion_id: str,
    payload: dict | None = None,
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        promotion = await rollback_factor_feature_promotion_service(
            tid, uid, promotion_id, payload or {}
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok({"promotion": promotion})


@router.post("/factors/promotions/{promotion_id}/train")
async def launch_factor_promotion_training(
    promotion_id: str,
    req: FactorTrainingLaunchRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        training = await launch_factor_promotion_training_service(
            tid,
            uid,
            promotion_id,
            req.model_dump(),
            background_tasks=background_tasks,
            current_user=current_user,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok({"training": training})


@router.post("/factors/candidates/{candidate_id}/publish-shadow-signal")
async def publish_factor_shadow_signal(
    candidate_id: str,
    req: FactorShadowSignalPublishRequest,
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        signal_run = await publish_factor_shadow_signal_service(
            tid, uid, candidate_id, req.model_dump()
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ok({"signalRun": signal_run})


@router.get("/factors/runs/{run_id}")
async def get_factor_evaluation_run(
    run_id: str, current_user: dict = Depends(get_current_user)
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        run = await get_factor_evaluation_run_service(tid, uid, run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _ok({"run": run})


@router.get("/factors/runs/{run_id}/values")
async def list_factor_run_values(
    run_id: str,
    limit: int = Query(100),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    try:
        return _ok(
            await list_factor_run_values_service(
                tid, uid, run_id, limit=limit, offset=offset
            )
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs")
async def get_inference_runs(
    model_id: str, current_user: dict = Depends(get_current_user)
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return await get_inference_runs_service(tid, uid, model_id)


@router.get("/overview")
async def get_research_overview(
    model_id: str | None = Query(None),
    run_id: str | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return await get_research_overview_service(
        tid, uid, model_id, run_id, limit, offset
    )


@router.get("/universe")
async def get_research_universe(
    run_id: str,
    limit: int = Query(2000),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return await get_research_universe_service(tid, uid, run_id, limit, offset)


@router.get("/watchlist")
async def get_user_watchlist(
    limit: int = Query(50),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return await get_user_watchlist_service(tid, uid, limit, offset)


@router.post("/watchlist/{symbol}")
async def add_to_watchlist(
    symbol: str,
    req: WatchlistAddRequest,
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return await add_to_watchlist_service(
        tid, uid, symbol, req.run_id, req.stock_name, req.features_snapshot
    )


@router.delete("/watchlist/{symbol}")
async def remove_from_watchlist(
    symbol: str, current_user: dict = Depends(get_current_user)
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return await remove_from_watchlist_service(tid, uid, symbol)


@router.get("/pool")
async def get_user_research_pool(
    status: str | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return await get_user_research_pool_service(tid, uid, status, limit, offset)


@router.post("/pool/{symbol}")
async def add_to_research_pool(
    symbol: str, req: PoolAddRequest, current_user: dict = Depends(get_current_user)
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return await add_to_research_pool_service(
        tid,
        uid,
        symbol,
        req.run_id,
        req.stock_name,
        req.model_id,
        req.fusion_score,
        req.thesis_summary,
        req.features_snapshot,
    )


@router.delete("/pool/{symbol}")
async def remove_from_research_pool(
    symbol: str, current_user: dict = Depends(get_current_user)
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return await remove_from_research_pool_service(tid, uid, symbol)


@router.post("/symbols/features")
async def get_symbols_features(
    req: SymbolsFeaturesRequest,
    lite: bool = Query(
        False, description="轻量模式：仅查询 stock_daily_latest 最新交易日核心字段"
    ),
    current_user: dict = Depends(get_current_user),
):
    tid, uid = str(current_user["tenant_id"]), str(current_user["user_id"])
    return await get_symbols_features_service(tid, uid, req.symbols, lite)


@router.get("/kline/{symbol}")
async def get_stock_kline(
    symbol: str, days: int = Query(60), current_user: dict = Depends(get_current_user)
):
    _ = current_user
    return await get_stock_kline_service(symbol, days)
