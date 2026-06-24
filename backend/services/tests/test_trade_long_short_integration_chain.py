import uuid
import sys
import types
from types import SimpleNamespace

import pytest

if "slowapi" not in sys.modules:
    slowapi_module = types.ModuleType("slowapi")
    slowapi_util_module = types.ModuleType("slowapi.util")

    class _Limiter:
        def __init__(self, *args, **kwargs):
            pass

        def limit(self, *args, **kwargs):
            def _decorator(func):
                return func

            return _decorator

    def _get_remote_address(*args, **kwargs):
        return "test-client"

    slowapi_module.Limiter = _Limiter
    slowapi_util_module.get_remote_address = _get_remote_address
    sys.modules["slowapi"] = slowapi_module
    sys.modules["slowapi.util"] = slowapi_util_module

from backend.services.trade.models.enums import OrderSide, OrderStatus, TradeAction, TradingMode
from backend.services.trade.routers import internal_strategy_bridge, internal_strategy_lifecycle
from backend.services.trade.schemas.qmt_agent import QMTBridgeExecutionPayload
from backend.services.trade.services.qmt_agent_auth import BridgeSessionContext
from backend.services.trade.services import internal_strategy_dispatcher


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return self

    def first(self):
        return self._value

    def all(self):
        if self._value is None:
            return []
        if isinstance(self._value, list):
            return list(self._value)
        return [self._value]

    def scalar_one_or_none(self):
        return self._value


class _SequenceDb:
    def __init__(self, values):
        self._values = list(values)

    async def execute(self, *_args, **_kwargs):
        if not self._values:
            raise AssertionError("unexpected execute call")
        return _ScalarResult(self._values.pop(0))

    async def commit(self):
        return None


class _DummyRedis:
    pass


async def _fake_portfolio_snapshot(*_args, **_kwargs):
    return None


@pytest.mark.asyncio
async def test_internal_strategy_order_sell_to_open_success(monkeypatch):
    captured = {}

    class _FakeOrderService:
        def __init__(self, _db, _redis):
            pass

        async def create_order(self, user_id, tenant_id, order_data):
            captured["order_data"] = order_data
            return SimpleNamespace(
                order_id=uuid.uuid4(),
                trade_action=order_data.trade_action,
                position_side=order_data.position_side,
                is_margin_trade=order_data.is_margin_trade,
                tenant_id=tenant_id,
                user_id=user_id,
            )

        async def transition_order_status(self, *_args, **_kwargs):
            return None

    class _FakeEngine:
        def __init__(self, _db, _redis):
            pass

        async def check_order_risk(self, _uid, _order):
            return {"passed": True, "violations": []}

        async def submit_order(self, order, tenant_id="default"):
            return {
                "success": True,
                "order_id": str(order.order_id),
                "status": "submitted",
                "message": f"submitted:{tenant_id}",
            }

    monkeypatch.setattr(internal_strategy_dispatcher, "OrderService", _FakeOrderService)
    monkeypatch.setattr(internal_strategy_dispatcher, "TradingEngine", _FakeEngine)
    monkeypatch.setattr(internal_strategy_dispatcher, "_fetch_active_portfolio_snapshot", _fake_portfolio_snapshot)

    db = _SequenceDb([12345, None])
    res = await internal_strategy_lifecycle.strategy_order(
        {
            "trading_mode": "REAL",
            "symbol": "600000.SH",
            "side": "SELL",
            "quantity": 200,
            "price": 10.1,
            "order_type": "LIMIT",
            "trade_action": "sell_to_open",
            "position_side": "short",
            "is_margin_trade": True,
            "client_order_id": "cid-chain-001",
        },
        x_user_id="1001",
        x_tenant_id="default",
        redis=_DummyRedis(),
        db=db,
    )

    assert res["status"] == "success"
    assert res["execution"] == "direct"
    assert captured["order_data"].trade_action.value == "sell_to_open"
    assert captured["order_data"].position_side.value == "short"
    assert captured["order_data"].is_margin_trade is True


@pytest.mark.asyncio
async def test_internal_strategy_order_sell_to_open_rejected_by_risk(monkeypatch):
    class _FakeOrderService:
        def __init__(self, _db, _redis):
            self.rejected = False

        async def create_order(self, user_id, tenant_id, order_data):
            return SimpleNamespace(
                order_id=uuid.uuid4(),
                trade_action=order_data.trade_action,
                position_side=order_data.position_side,
                is_margin_trade=order_data.is_margin_trade,
                tenant_id=tenant_id,
                user_id=user_id,
            )

        async def transition_order_status(self, order, status, remarks=None):
            order.status = status
            order.remarks = remarks
            return order

    class _FakeEngine:
        def __init__(self, _db, _redis):
            pass

        async def check_order_risk(self, _uid, _order):
            return {
                "passed": False,
                "violations": [{"rule": "SHORT_QUOTA_INSUFFICIENT", "message": "quota not enough"}],
            }

        async def submit_order(self, *_args, **_kwargs):
            raise AssertionError("risk blocked should not submit")

    monkeypatch.setattr(internal_strategy_dispatcher, "OrderService", _FakeOrderService)
    monkeypatch.setattr(internal_strategy_dispatcher, "TradingEngine", _FakeEngine)
    monkeypatch.setattr(internal_strategy_dispatcher, "_fetch_active_portfolio_snapshot", _fake_portfolio_snapshot)

    db = _SequenceDb([12345, None])
    res = await internal_strategy_lifecycle.strategy_order(
        {
            "trading_mode": "REAL",
            "symbol": "600000.SH",
            "side": "SELL",
            "quantity": 200,
            "price": 10.1,
            "order_type": "LIMIT",
            "trade_action": "sell_to_open",
            "position_side": "short",
            "is_margin_trade": True,
            "client_order_id": "cid-chain-002",
        },
        x_user_id="1001",
        x_tenant_id="default",
        redis=_DummyRedis(),
        db=db,
    )

    assert res["status"] == "rejected"
    assert res["execution"] == "risk_blocked"
    assert res["violations"][0]["rule"] == "SHORT_QUOTA_INSUFFICIENT"


@pytest.mark.asyncio
async def test_internal_strategy_order_simulation_uses_submission_service_rejection(
    monkeypatch,
):
    captured = {}

    class _ForbiddenRealEngine:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("simulation dispatch must not instantiate real engine")

    class _FakeSimulationManager:
        def __init__(self, redis):
            captured["redis"] = redis

    class _FakeSimulationSubmissionService:
        def __init__(self, db, sim_manager):
            captured["db"] = db
            captured["sim_manager"] = sim_manager

        async def submit_and_fill(self, **kwargs):
            captured["submission_kwargs"] = kwargs
            return SimpleNamespace(
                success=False,
                order_id=uuid.uuid4(),
                message="Insufficient cash for buy order",
            )

    monkeypatch.setattr(
        internal_strategy_dispatcher,
        "TradingEngine",
        _ForbiddenRealEngine,
    )
    monkeypatch.setattr(
        internal_strategy_dispatcher,
        "SimulationAccountManager",
        _FakeSimulationManager,
    )
    monkeypatch.setattr(
        internal_strategy_dispatcher,
        "SimulationOrderSubmissionService",
        _FakeSimulationSubmissionService,
    )

    res = await internal_strategy_dispatcher.dispatch_internal_strategy_order(
        order_data={
            "trading_mode": "SIMULATION",
            "portfolio_id": 88,
            "strategy_id": "48",
            "symbol": "SH600519",
            "side": "BUY",
            "quantity": 100,
            "price": 0,
            "order_type": "MARKET",
            "trade_action": "buy_to_open",
            "position_side": "long",
            "client_order_id": "factor-shadow-sim-risk",
            "remarks": "signal_source=factor_shadow",
        },
        user_id="1001",
        tenant_id="default",
        redis=_DummyRedis(),
        db=_SequenceDb([]),
    )

    assert res["status"] == "failed"
    assert res["execution"] == "simulation_rejected"
    assert res["reason"] == "Insufficient cash for buy order"
    assert captured["submission_kwargs"]["trigger_source"] == "strategy_dispatch"
    assert captured["submission_kwargs"]["tenant_id"] == "default"
    assert captured["submission_kwargs"]["user_id"] == 1001
    assert captured["submission_kwargs"]["portfolio_id"] == 88
    assert captured["submission_kwargs"]["symbol"] == "SH600519"
    assert captured["submission_kwargs"]["trade_action"] == "buy_to_open"
    assert captured["submission_kwargs"]["client_order_id"] == "factor-shadow-sim-risk"


@pytest.mark.asyncio
async def test_internal_strategy_order_factor_shadow_simulation_returns_fill_result(
    monkeypatch,
):
    captured = {}
    order_id = uuid.uuid4()
    trade_id = uuid.uuid4()

    class _ForbiddenRealEngine:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("SIMULATION factor_shadow must not use real engine")

    class _FakeSimulationManager:
        def __init__(self, redis):
            captured["redis"] = redis

    class _FakeSimulationSubmissionService:
        def __init__(self, db, sim_manager):
            captured["db"] = db
            captured["sim_manager"] = sim_manager

        async def submit_and_fill(self, **kwargs):
            captured["submission_kwargs"] = kwargs
            return SimpleNamespace(
                success=True,
                order_id=order_id,
                trade_id=trade_id,
                client_order_id=kwargs["client_order_id"],
                fill_price=18.88,
                price_source="market_latest",
                filled_quantity=200,
                commission=1.2,
                message="filled",
            )

    monkeypatch.setattr(
        internal_strategy_dispatcher,
        "TradingEngine",
        _ForbiddenRealEngine,
    )
    monkeypatch.setattr(
        internal_strategy_dispatcher,
        "SimulationAccountManager",
        _FakeSimulationManager,
    )
    monkeypatch.setattr(
        internal_strategy_dispatcher,
        "SimulationOrderSubmissionService",
        _FakeSimulationSubmissionService,
    )

    res = await internal_strategy_dispatcher.dispatch_internal_strategy_order(
        order_data={
            "trading_mode": "SIMULATION",
            "portfolio_id": 88,
            "strategy_id": "48",
            "symbol": "SH600000",
            "side": "BUY",
            "quantity": 200,
            "price": 0,
            "order_type": "MARKET",
            "trade_action": "buy_to_open",
            "position_side": "long",
            "client_order_id": "factor-shadow-sim-fill",
            "remarks": "signal_source=factor_shadow",
        },
        user_id="1001",
        tenant_id="default",
        redis=_DummyRedis(),
        db=_SequenceDb([]),
    )

    assert res == {
        "status": "success",
        "execution": "simulation_filled",
        "order_id": str(order_id),
        "trade_id": str(trade_id),
        "client_order_id": "factor-shadow-sim-fill",
        "fill_price": 18.88,
        "price_source": "market_latest",
        "filled_quantity": 200,
        "commission": 1.2,
    }
    assert captured["submission_kwargs"]["remarks"] == "signal_source=factor_shadow"
    assert captured["submission_kwargs"]["trigger_source"] == "strategy_dispatch"
    assert captured["submission_kwargs"]["tenant_id"] == "default"
    assert captured["submission_kwargs"]["user_id"] == 1001
    assert captured["submission_kwargs"]["portfolio_id"] == 88
    assert captured["submission_kwargs"]["symbol"] == "SH600000"
    assert captured["submission_kwargs"]["price"] is None
    assert captured["submission_kwargs"]["trade_action"] == "buy_to_open"
    assert captured["submission_kwargs"]["position_side"] == "long"


@pytest.mark.asyncio
async def test_internal_strategy_order_buy_to_close_success(monkeypatch):
    captured = {}

    class _FakeOrderService:
        def __init__(self, _db, _redis):
            pass

        async def create_order(self, user_id, tenant_id, order_data):
            captured["order_data"] = order_data
            return SimpleNamespace(
                order_id=uuid.uuid4(),
                trade_action=order_data.trade_action,
                position_side=order_data.position_side,
                is_margin_trade=order_data.is_margin_trade,
                tenant_id=tenant_id,
                user_id=user_id,
            )

        async def transition_order_status(self, *_args, **_kwargs):
            return None

    class _FakeEngine:
        def __init__(self, _db, _redis):
            pass

        async def check_order_risk(self, _uid, _order):
            return {"passed": True, "violations": []}

        async def submit_order(self, order, tenant_id="default"):
            return {
                "success": True,
                "order_id": str(order.order_id),
                "status": "submitted",
                "message": f"submitted:{tenant_id}",
            }

    monkeypatch.setattr(internal_strategy_dispatcher, "OrderService", _FakeOrderService)
    monkeypatch.setattr(internal_strategy_dispatcher, "TradingEngine", _FakeEngine)
    monkeypatch.setattr(internal_strategy_dispatcher, "_fetch_active_portfolio_snapshot", _fake_portfolio_snapshot)

    db = _SequenceDb([12345, None])
    res = await internal_strategy_lifecycle.strategy_order(
        {
            "trading_mode": "REAL",
            "symbol": "600000.SH",
            "side": "BUY",
            "quantity": 100,
            "price": 9.8,
            "order_type": "LIMIT",
            "trade_action": "buy_to_close",
            "position_side": "short",
            "is_margin_trade": True,
            "client_order_id": "cid-chain-003",
        },
        x_user_id="1001",
        x_tenant_id="default",
        redis=_DummyRedis(),
        db=db,
    )

    assert res["status"] == "success"
    assert captured["order_data"].trade_action.value == "buy_to_close"
    assert captured["order_data"].position_side.value == "short"
    assert captured["order_data"].is_margin_trade is True


class _DbForExecutionDedup:
    def __init__(self, order):
        self.order = order
        self.trades = []

    async def execute(self, stmt, *_args, **_kwargs):
        sql = str(stmt)
        if "FROM orders" in sql:
            return _ScalarResult(self.order)
        if "FROM trades" in sql:
            return _ScalarResult(self.trades[0] if self.trades else None)
        raise AssertionError(f"unexpected sql: {sql}")

    def add(self, trade):
        self.trades.append(trade)

    async def commit(self):
        return None


@pytest.mark.asyncio
async def test_bridge_execution_reconcile_replay_not_duplicate_trade():
    order = SimpleNamespace(
        order_id=uuid.uuid4(),
        tenant_id="default",
        user_id=1001,
        portfolio_id=11,
        symbol="600000.SH",
        side=OrderSide.BUY,
        trading_mode=TradingMode.REAL,
        status=OrderStatus.SUBMITTED,
        exchange_order_id=None,
        filled_quantity=0.0,
        average_price=None,
        quantity=100.0,
        price=10.0,
        remarks=None,
    )
    db = _DbForExecutionDedup(order)
    ctx = BridgeSessionContext(
        session_id="s1",
        binding_id="b1",
        tenant_id="default",
        user_id="1001",
        account_id="acc-1",
        client_fingerprint="fp-1",
        hostname="host-1",
        client_version="0.2.0",
    )
    payload = QMTBridgeExecutionPayload(
        client_order_id="cid-replay-1",
        exchange_order_id="oid-1",
        exchange_trade_id="tid-1",
        account_id="acc-1",
        symbol="600000.SH",
        side="BUY",
        status="FILLED",
        filled_quantity=100,
        filled_price=10.2,
        message="filled",
    )

    first = await internal_strategy_bridge.report_qmt_execution(payload, ctx=ctx, db=db)
    second = await internal_strategy_bridge.report_qmt_execution(payload, ctx=ctx, db=db)

    assert first["ok"] is True
    assert second["ok"] is True
    assert len(db.trades) == 1


@pytest.mark.asyncio
async def test_bridge_execution_order_callback_without_trade_id_does_not_double_count_trade():
    order = SimpleNamespace(
        order_id=uuid.uuid4(),
        tenant_id="default",
        user_id=1001,
        portfolio_id=11,
        symbol="600000.SH",
        side=OrderSide.BUY,
        trading_mode=TradingMode.REAL,
        status=OrderStatus.SUBMITTED,
        exchange_order_id=None,
        filled_quantity=0.0,
        filled_value=0.0,
        average_price=None,
        quantity=100.0,
        price=10.0,
        remarks=None,
    )
    db = _DbForExecutionDedup(order)
    ctx = BridgeSessionContext(
        session_id="s1",
        binding_id="b1",
        tenant_id="default",
        user_id="1001",
        account_id="acc-1",
        client_fingerprint="fp-1",
        hostname="host-1",
        client_version="0.2.0",
    )

    order_payload = QMTBridgeExecutionPayload(
        client_order_id="cid-replay-2",
        exchange_order_id="oid-2",
        exchange_trade_id=None,
        account_id="acc-1",
        symbol="600000.SH",
        side="BUY",
        status="FILLED",
        filled_quantity=100,
        filled_price=10.2,
        message="order callback filled",
    )
    trade_payload = QMTBridgeExecutionPayload(
        client_order_id="cid-replay-2",
        exchange_order_id="oid-2",
        exchange_trade_id="tid-2",
        account_id="acc-1",
        symbol="600000.SH",
        side="BUY",
        status="FILLED",
        filled_quantity=100,
        filled_price=10.2,
        message="trade callback filled",
    )

    first = await internal_strategy_bridge.report_qmt_execution(order_payload, ctx=ctx, db=db)
    second = await internal_strategy_bridge.report_qmt_execution(trade_payload, ctx=ctx, db=db)

    assert first["ok"] is True
    assert second["ok"] is True
    assert len(db.trades) == 1
    assert order.filled_quantity == 100.0
    assert order.filled_value == pytest.approx(1020.0)
    assert order.average_price == 10.2
    assert order.status == OrderStatus.FILLED
