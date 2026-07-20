from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.engine.corporate_actions.credentials import token_from_environment
from backend.services.engine.corporate_actions.engine import (
    replay_corporate_action_audit,
    run_corporate_action_audit,
)
from backend.services.engine.corporate_actions.errors import CorporateActionCredentialError
from backend.services.engine.corporate_actions.tushare_client import CorporateActionTushareClient
from backend.services.engine.tushare_cutover.client import TushareError, TushareResponse
from tools.quantmind2.tushare_corporate_actions import parser


class FakeTransport:
    def query(self, endpoint, *, fields, **params):
        symbol = params.get("ts_code")
        if endpoint in {"anns_d", "merge", "merger"}:
            raise TushareError("redacted upstream error")
        rows = []
        if endpoint == "stock_basic":
            code = symbol.split(".")[0]
            rows = [{
                "ts_code": symbol, "symbol": code, "name": "test", "market": "主板",
                "exchange": "SSE", "list_status": "D", "list_date": "20000101",
                "delist_date": "20250304" if code == "600837" else "20250905",
            }]
        elif endpoint == "daily":
            rows = [{"ts_code": symbol,
                     "trade_date": "20250205" if symbol.startswith("600837") else "20250812",
                     "close": 10.0, "pre_close": 9.9}]
        return TushareResponse(endpoint, tuple(fields), tuple(rows))


def test_token_is_environment_only_and_cli_has_no_token(monkeypatch):
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    with pytest.raises(CorporateActionCredentialError):
        token_from_environment()
    monkeypatch.setenv("TUSHARE_TOKEN", "unit-secret")
    assert token_from_environment() == "unit-secret"
    assert "--token" not in parser().format_help()


def test_blocked_provider_publishes_safe_evidence_and_exact_replays(tmp_path):
    client = CorporateActionTushareClient(FakeTransport())
    result = run_corporate_action_audit(
        work_root=tmp_path / "work", store_root=tmp_path / "store", client=client,
    )
    assert result["status"] == "blocked"
    assert result["reason"] == "TUSHARE_CORPORATE_ACTION_EVIDENCE_INSUFFICIENT"
    assert result["new_artifacts"] == 3
    assert result["benchmark_revisions_published"] == 0
    assert result["integrity"] == "healthy"
    assert len(result["events"]) == 2
    assert all(row["evidence_completeness"] == "evidence_missing" for row in result["events"])
    raw = next((tmp_path / "work" / "artifacts" / "tushare_corporate_action_raw").iterdir())
    payload = b"".join(path.read_bytes() for path in raw.rglob("*") if path.is_file())
    assert b"unit-secret" not in payload
    requests = json.loads((raw / "requests.json").read_text())
    inaccessible = {row["endpoint"] for row in requests["requests"]
                    if row["status"] != "available"}
    assert {"anns_d", "merge", "merger"}.issubset(inaccessible)
    replay = replay_corporate_action_audit(
        raw_snapshot_id=result["raw_snapshot_id"], store_root=tmp_path / "store",
    )
    assert replay["status"] == "exact_replay"
    assert replay["tushare_network_calls"] == replay["qlib_calls"] == 0
    assert replay["new_artifacts"] == replay["new_blobs"] == 0

