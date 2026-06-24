import json

import httpx
import pytest

from backend.services.engine.scripts.factor_research_rollback_tool import (
    RollbackToolConfig,
    run_rollback_tool,
)


def _config(**overrides) -> RollbackToolConfig:
    values = {
        "base_url": "http://testserver",
        "token": "token-1",
        "tenant_id": "default",
        "username": None,
        "password": None,
        "promotion_id": "promotion-1",
        "latest_active": False,
        "reason": "test_rollback",
        "execute": False,
        "force": False,
        "timeout_seconds": 5.0,
    }
    values.update(overrides)
    return RollbackToolConfig(**values)


def _promotion(**overrides):
    payload = {
        "id": "promotion-1",
        "featureKey": "factor_alpha",
        "versionId": "factor_promoted_v1",
        "status": "materialized",
        "materializationStatus": "materialized",
        "metadata": {},
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_rollback_tool_dry_run_does_not_call_rollback_api():
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        if request.method == "GET" and request.url.path == "/health":
            return httpx.Response(200, json={"status": "healthy"})
        if (
            request.method == "GET"
            and request.url.path == "/api/v1/research/factors/promotions"
        ):
            return httpx.Response(
                200,
                json={"code": 200, "data": {"items": [_promotion()], "total": 1}},
            )
        return httpx.Response(404, json={"detail": "unhandled"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://testserver",
    ) as client:
        result = await run_rollback_tool(_config(), client=client)

    assert result.status == "dry_run"
    assert result.promotion_id == "promotion-1"
    assert result.feature_key == "factor_alpha"
    assert result.before_status == "materialized"
    assert ("POST", "/api/v1/research/factors/promotions/promotion-1/rollback") not in seen


@pytest.mark.asyncio
async def test_rollback_tool_execute_calls_api_and_verifies_status():
    seen: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = None
        if request.content:
            body = json.loads(request.content.decode("utf-8"))
        seen.append((request.method, request.url.path, body))
        if request.method == "GET" and request.url.path == "/health":
            return httpx.Response(200, json={"status": "healthy"})
        if (
            request.method == "GET"
            and request.url.path == "/api/v1/research/factors/promotions"
        ):
            return httpx.Response(
                200,
                json={"code": 200, "data": {"items": [_promotion()], "total": 1}},
            )
        if (
            request.method == "POST"
            and request.url.path
            == "/api/v1/research/factors/promotions/promotion-1/rollback"
        ):
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "promotion": _promotion(
                            status="rolled_back",
                            materializationStatus="rolled_back",
                            metadata={
                                "rollback": {
                                    "rollback_version_id": "factor_rollback_1"
                                }
                            },
                        )
                    },
                },
            )
        return httpx.Response(404, json={"detail": "unhandled"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://testserver",
    ) as client:
        result = await run_rollback_tool(
            _config(execute=True, reason="bad_factor_decay"),
            client=client,
        )

    assert result.status == "rolled_back"
    assert result.after_status == "rolled_back"
    assert result.after_materialization_status == "rolled_back"
    assert result.rollback_version_id == "factor_rollback_1"
    assert (
        "POST",
        "/api/v1/research/factors/promotions/promotion-1/rollback",
        {"reason": "bad_factor_decay"},
    ) in seen


@pytest.mark.asyncio
async def test_rollback_tool_skips_already_rolled_back_promotion_without_force():
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        if request.method == "GET" and request.url.path == "/health":
            return httpx.Response(200, json={"status": "healthy"})
        if (
            request.method == "GET"
            and request.url.path == "/api/v1/research/factors/promotions"
        ):
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "items": [
                            _promotion(
                                status="rolled_back",
                                materializationStatus="rolled_back",
                                metadata={
                                    "rollback": {
                                        "rollback_version_id": "factor_rollback_1"
                                    }
                                },
                            )
                        ],
                        "total": 1,
                    },
                },
            )
        return httpx.Response(404, json={"detail": "unhandled"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://testserver",
    ) as client:
        result = await run_rollback_tool(
            _config(execute=True),
            client=client,
        )

    assert result.status == "skipped"
    assert result.rollback_version_id == "factor_rollback_1"
    assert ("POST", "/api/v1/research/factors/promotions/promotion-1/rollback") not in seen
