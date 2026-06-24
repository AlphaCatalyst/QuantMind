from typing import Any

import pytest

from backend.services.engine.research.external_submit_guard import (
    ExternalSubmitDisabledError,
)
from backend.services.engine.research.quantgpt_client import QuantGPTClient
from backend.services.engine.research.schemas import QuantGPTEvaluationRequest


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def test_quantgpt_client_uses_versioned_health_endpoint(monkeypatch):
    calls: list[str] = []

    def fake_get(url: str, timeout: int):
        calls.append(url)
        assert timeout == 7
        return _FakeResponse({"status": "ok"})

    monkeypatch.setattr(
        "backend.services.engine.research.quantgpt_client.requests.get",
        fake_get,
    )

    client = QuantGPTClient("http://quantgpt-research:8013/", timeout_seconds=7)
    assert client.health() == {"status": "ok"}
    assert calls == ["http://quantgpt-research:8013/api/v1/health"]


def test_quantgpt_client_factor_values_parses_contract(monkeypatch):
    def fake_post(url: str, json: dict[str, Any], timeout: int):
        assert url == "http://quantgpt-research:8013/api/v1/factor_values"
        assert json["expression"] == "rank(close)"
        assert timeout == 30
        return _FakeResponse(
            {
                "expression": "rank(close)",
                "universe": "hs300",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
                "data": [{"date": "2026-01-02", "values": {"sh.600519": 1.0}}],
            }
        )

    monkeypatch.setattr(
        "backend.services.engine.research.quantgpt_client.requests.post",
        fake_post,
    )

    client = QuantGPTClient("http://quantgpt-research:8013")
    result = client.compute_factor_values(
        QuantGPTEvaluationRequest(
            expression="rank(close)",
            universe="hs300",
            start_date="2026-01-01",
            end_date="2026-01-02",
        )
    )

    assert len(result.rows) == 1
    assert result.rows[0].symbol == "SH600519"


def test_quantgpt_client_blocks_external_submit_endpoint_by_default(monkeypatch):
    monkeypatch.setenv("WQ_BRAIN_EMAIL", "configured@example.com")
    monkeypatch.setenv("WQ_BRAIN_PASSWORD", "secret")
    monkeypatch.delenv("QUANTMIND_FACTOR_RESEARCH_ALLOW_EXTERNAL_SUBMIT", raising=False)

    client = QuantGPTClient("http://quantgpt-research:8013")

    with pytest.raises(ExternalSubmitDisabledError):
        client._url("/api/v1/wq-brain/submit")
