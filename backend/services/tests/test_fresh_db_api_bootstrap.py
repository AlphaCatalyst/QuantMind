"""Fresh DB API bootstrap and route-surface contract tests."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_api_lifespan_bootstraps_strategy_and_research_tables(monkeypatch):
    os.environ.setdefault("DEBUG", "false")
    from backend.services.api import main as api_main
    from backend.services.api.routers.admin import model_management
    import backend.services.engine.services.model_inference_persistence as inference
    from backend.services.api.user_app.services import rbac_service
    import backend.shared.database_manager_v2 as database_manager_v2
    import backend.shared.model_registry as model_registry
    import backend.shared.schema_registry as schema_registry
    import backend.shared.stock_name_mapper as stock_name_mapper
    import backend.shared.strategy_storage as strategy_storage

    calls: list[str] = []
    master_engine = object()

    async def fake_init_unified_config(*args, **kwargs):
        calls.append("config")

    async def fake_init_database():
        calls.append("database")

    async def fake_create_registered_tables(engine, schemas):
        calls.append(f"schemas:{','.join(schemas)}")
        assert engine is master_engine

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield "rbac-session"

    async def fake_ensure_factor_approval_permission(session):
        calls.append("factor_permission")
        assert session == "rbac-session"

    async def fake_ensure_admin_tables():
        calls.append("admin_tables")

    async def fake_model_registry_tables():
        calls.append("model_registry")

    async def fake_model_inference_tables():
        calls.append("model_inference")

    async def fake_research_factor_tables():
        calls.append("research_factor")

    monkeypatch.setattr(api_main, "init_unified_config", fake_init_unified_config)
    monkeypatch.setattr(
        api_main, "init_sync_db_pool", lambda **kwargs: calls.append("sync_pool")
    )
    monkeypatch.setattr(database_manager_v2, "init_database", fake_init_database)
    monkeypatch.setattr(
        database_manager_v2,
        "get_db_manager",
        lambda: SimpleNamespace(_master_engine=master_engine),
    )
    monkeypatch.setattr(
        schema_registry, "create_registered_tables", fake_create_registered_tables
    )
    monkeypatch.setattr(database_manager_v2, "get_session", fake_get_session)
    monkeypatch.setattr(
        rbac_service,
        "ensure_factor_approval_permission",
        fake_ensure_factor_approval_permission,
    )
    monkeypatch.setattr(
        strategy_storage,
        "ensure_strategy_storage_tables",
        lambda: calls.append("strategies"),
    )
    monkeypatch.setattr(
        model_management, "ensure_admin_tables", fake_ensure_admin_tables
    )
    monkeypatch.setattr(
        model_registry.model_registry_service,
        "ensure_tables",
        fake_model_registry_tables,
    )
    monkeypatch.setattr(
        inference.model_inference_persistence,
        "ensure_tables",
        fake_model_inference_tables,
    )
    monkeypatch.setattr(
        "backend.services.api.routers.research_factor_service.ensure_research_factor_tables",
        fake_research_factor_tables,
    )
    monkeypatch.setattr(
        stock_name_mapper,
        "get_stock_name_mapper",
        lambda: SimpleNamespace(_mapping={}),
    )

    async with api_main.lifespan(api_main.app):
        assert api_main.app.state.startup_healthy is True

    assert calls == [
        "config",
        "sync_pool",
        "database",
        "schemas:api.user",
        "factor_permission",
        "strategies",
        "admin_tables",
        "model_registry",
        "model_inference",
        "research_factor",
    ]


def test_api_fresh_db_route_surface_includes_cross_module_entrypoints():
    os.environ.setdefault("DEBUG", "false")
    from backend.services.api.main import app

    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/api/v1/auth/register" in paths
    assert "/api/v1/strategies" in paths
    assert "/api/v1/ai-ide/{subpath:path}" in paths
    assert "/api/v1/research/factors/candidates" in paths
    assert "/api/v1/research/factors/health" in paths
    assert "/api/v1/research/factors/runs/{run_id}/values" in paths
    assert "/api/v1/research/factors/campaigns/{campaign_id}/cancel" in paths
    assert "/api/v1/research/factors/promotions/{promotion_id}/train" in paths
    assert "/api/v1/research/factors/approvals" in paths
    assert "/api/v1/research/factors/approval-policy" in paths
    assert "/api/v1/research/factors/approval-requests" in paths
    assert "/api/v1/research/factors/approval-requests/{request_id}/review" in paths
    assert "/api/v1/research/factors/trainings/{training_id}/approval-requests" in paths
    assert "/api/v1/research/factors/trainings/{training_id}/approve" in paths
