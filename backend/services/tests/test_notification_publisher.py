from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

from backend.shared import notification_publisher as publisher


def test_publish_notification_uses_notification_type_column(monkeypatch):
    captured: dict[str, object] = {}
    events: list[dict] = []

    class FakeResult:
        def mappings(self):
            return self

        def first(self):
            return {"id": 42, "created_at": datetime.now(timezone.utc)}

    class FakeSession:
        def execute(self, statement, params):
            captured["sql"] = str(statement)
            captured["params"] = params
            return FakeResult()

        def commit(self):
            captured["committed"] = True

    @contextmanager
    def fake_get_db():
        yield FakeSession()

    monkeypatch.setattr(publisher, "get_db", fake_get_db)
    monkeypatch.setattr(
        publisher,
        "_push_notification_event",
        lambda payload: events.append(payload) or True,
    )

    ok = publisher.publish_notification(
        tenant_id="default",
        user_id="user-1",
        title="审批通知",
        content="审批请求已提交",
        type="system",
        level="info",
        action_url="/factor-research",
    )

    assert ok is True
    assert captured["committed"] is True
    sql = str(captured["sql"])
    assert "notification_type" in sql
    assert " content, type," not in sql
    assert captured["params"]["type"] == "system"
    assert events[0]["user_id"] == "user-1"


def test_missing_notification_table_detection_does_not_hide_column_errors():
    assert publisher._looks_like_missing_table_error(
        Exception('relation "notifications" does not exist')
    )
    assert not publisher._looks_like_missing_table_error(
        Exception('column "type" of relation "notifications" does not exist')
    )
