from typing import Any

from backend.services.trade.runner import main as runner_main


class _FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http error {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeRedis:
    def __init__(
        self,
        records: list[tuple[str, dict[str, str]]],
        latest_run_id: str | None = None,
    ):
        self.records = records
        self.latest_run_id = latest_run_id
        self.acked: list[str] = []
        self.set_calls: list[tuple[str, str, int | None, bool | None]] = []
        self.exec_events: list[dict[str, str]] = []

    def get(self, key: str):
        if key.startswith("qm:signal:latest:"):
            return self.latest_run_id
        return None

    def xreadgroup(self, *args, **kwargs):
        _ = (args, kwargs)
        if not self.records:
            return []
        messages = [(mid, fields) for mid, fields in self.records]
        self.records = []
        return [("qm:signal:stream:default", messages)]

    def xack(self, stream_name: str, group: str, *ack_ids: str):
        _ = (stream_name, group)
        self.acked.extend(list(ack_ids))
        return len(ack_ids)

    def set(self, key: str, value: str, ex: int | None = None, nx: bool | None = None):
        self.set_calls.append((key, value, ex, nx))
        return True

    def xadd(
        self, stream_name: str, fields: dict[str, str], maxlen: int, approximate: bool
    ):
        _ = (stream_name, maxlen, approximate)
        self.exec_events.append(fields)
        return "2-1"

    def xgroup_create(self, stream_name: str, groupname: str, id: str, mkstream: bool):
        _ = (stream_name, groupname, id, mkstream)
        return True


def test_runner_creates_hosted_execution_task(monkeypatch):
    fake_redis = _FakeRedis(records=[])

    def _fake_post(
        url: str, json: dict[str, Any], headers: dict[str, str], timeout: int
    ):
        assert url.endswith("/hosted-executions")
        assert headers["X-User-Id"] == "u1"
        assert json["strategy_id"] == "s1"
        assert json["signals"] == []
        assert json["trigger_context"]["phase"] == "BUY"
        _ = timeout
        return _FakeResponse({"status": "success", "task_id": json["task_id"]})

    monkeypatch.setattr(runner_main.requests, "post", _fake_post)
    monkeypatch.setattr(runner_main, "_current_local_ts", lambda: 1_710_310_800.0)
    monkeypatch.setattr(runner_main, "_is_rebalance_day", lambda _ts, _cfg: True)

    processed = runner_main.process_cycle(
        user_id="u1",
        tenant_id="default",
        strategy="s1",
        redis_client=fake_redis,  # type: ignore[arg-type]
        exec_config={},
        live_trade_config={
            "enabled_sessions": ["PM"],
            "sell_time": "14:00",
            "buy_time": "14:30",
            "sell_first": False,
            "max_orders_per_cycle": 20,
            "order_type": "LIMIT",
        },
    )

    assert processed is True
    assert fake_redis.acked == []
    assert len(fake_redis.set_calls) == 1


def test_runner_passes_factor_shadow_simulation_policy_to_hosted_task(monkeypatch):
    fake_redis = _FakeRedis(records=[])
    posted_payload: dict[str, Any] = {}

    def _fake_post(
        url: str, json: dict[str, Any], headers: dict[str, str], timeout: int
    ):
        assert url.endswith("/hosted-executions")
        assert headers["X-User-Id"] == "u1"
        assert headers["X-Tenant-Id"] == "default"
        assert timeout == 8
        posted_payload.update(json)
        return _FakeResponse({"status": "success", "task_id": json["task_id"]})

    monkeypatch.setattr(runner_main.requests, "post", _fake_post)
    monkeypatch.setattr(runner_main, "_current_local_ts", lambda: 1_710_310_800.0)
    monkeypatch.setattr(runner_main, "_is_rebalance_day", lambda _ts, _cfg: True)

    processed = runner_main.process_cycle(
        user_id="u1",
        tenant_id="default",
        strategy="s1",
        redis_client=fake_redis,  # type: ignore[arg-type]
        exec_config={
            "trading_mode": "SIMULATION",
            "allow_factor_shadow_signals": True,
        },
        live_trade_config={
            "enabled_sessions": ["PM"],
            "sell_time": "14:00",
            "buy_time": "14:30",
            "sell_first": False,
            "max_orders_per_cycle": 20,
            "order_type": "LIMIT",
        },
    )

    assert processed is True
    assert posted_payload["trading_mode"] == "SIMULATION"
    assert posted_payload["execution_config"]["allow_factor_shadow_signals"] is True
    assert posted_payload["signals"] == []
    assert posted_payload["trigger_context"]["source"] == "hosted_runner"
    assert posted_payload["trigger_context"]["signal_input"] == "engine_signal_scores"
    assert (
        posted_payload["trigger_context"]["signal_source_policy"]
        == "factor_shadow_allowed"
    )
    assert posted_payload["trigger_context"]["runner_mode"] == "SIMULATION"
    assert posted_payload["trigger_context"]["phase"] == "BUY"
    assert fake_redis.acked == []
    assert len(fake_redis.set_calls) == 1


def test_consume_signal_stream_skips_other_user_and_acks():
    signal_event = {
        "event_type": "signal_created",
        "tenant_id": "default",
        "user_id": "u-other",
        "signal_id": "sig-2",
        "client_order_id": "coid-2",
        "symbol": "000001.SZ",
        "side": "BUY",
        "quantity": "200",
        "price": "15",
        "score": "0.03",
    }
    fake_redis = _FakeRedis(records=[("1-1", signal_event)])

    signals, ack_ids = runner_main._consume_signal_events(
        user_id="u1",
        tenant_id="default",
        strategy="s1",
        redis_client=fake_redis,  # type: ignore[arg-type]
        exec_config={},
    )
    runner_main._ack_signal_events(
        redis_client=fake_redis,  # type: ignore[arg-type]
        tenant_id="default",
        user_id="u1",
        strategy="s1",
        exec_config={},
        ack_ids=ack_ids,
    )

    assert signals == []
    assert ack_ids == ["1-1"]
    assert fake_redis.acked == ["1-1"]


def test_consume_signal_stream_rejects_factor_shadow_without_explicit_allow():
    signal_event = {
        "event_type": "signal_created",
        "tenant_id": "default",
        "user_id": "u1",
        "run_id": "run-shadow",
        "signal_id": "sig-shadow",
        "client_order_id": "coid-shadow",
        "symbol": "SH600519",
        "side": "BUY",
        "quantity": "100",
        "price": "1500",
        "score": "0.12",
        "signal_source": "factor_shadow",
    }
    fake_redis = _FakeRedis(records=[("1-1", signal_event)])

    signals, ack_ids = runner_main._consume_signal_events(
        user_id="u1",
        tenant_id="default",
        strategy="s1",
        redis_client=fake_redis,  # type: ignore[arg-type]
        exec_config={},
    )

    assert signals == []
    assert ack_ids == ["1-1"]


def test_consume_signal_stream_allows_factor_shadow_with_explicit_allow():
    signal_event = {
        "event_type": "signal_created",
        "tenant_id": "default",
        "user_id": "u1",
        "run_id": "run-shadow",
        "signal_id": "sig-shadow",
        "client_order_id": "coid-shadow",
        "symbol": "SH600519",
        "side": "BUY",
        "quantity": "100",
        "price": "1500",
        "score": "0.12",
        "signal_source": "factor_shadow",
    }
    fake_redis = _FakeRedis(records=[("1-1", signal_event)])

    signals, ack_ids = runner_main._consume_signal_events(
        user_id="u1",
        tenant_id="default",
        strategy="s1",
        redis_client=fake_redis,  # type: ignore[arg-type]
        exec_config={"allow_factor_shadow_signals": True},
    )

    assert ack_ids == ["1-1"]
    assert len(signals) == 1
    assert signals[0]["signal_source"] == "factor_shadow"
    assert signals[0]["symbol"] == "SH600519"
