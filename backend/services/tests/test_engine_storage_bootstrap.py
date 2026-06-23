from unittest.mock import MagicMock

import pytest


def test_engine_storage_bootstrap_ensures_strategy_and_pool_tables(monkeypatch):
    pytest.importorskip("passlib.context")

    from backend.services.engine import main as engine_main

    calls: list[str] = []

    class FakeSession:
        def get_bind(self):
            return "fake-bind"

    class FakeDb:
        def __enter__(self):
            return FakeSession()

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_metadata = MagicMock()

    monkeypatch.setattr(
        "backend.shared.strategy_storage.ensure_strategy_storage_tables",
        lambda: calls.append("strategies"),
    )
    monkeypatch.setattr("backend.shared.database_pool.get_db", lambda: FakeDb())
    monkeypatch.setattr(
        "backend.services.engine.ai_strategy.models.stock_pool_file.Base.metadata",
        fake_metadata,
    )

    engine_main._ensure_engine_storage_tables()

    assert calls == ["strategies"]
    fake_metadata.create_all.assert_called_once_with(bind="fake-bind", checkfirst=True)
