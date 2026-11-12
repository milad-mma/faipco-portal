"""v9.3.3: office Push retries only failed subscriptions and requires session binding."""
import importlib.util
import os
import sys
import types
from types import SimpleNamespace

import pytest

# These are safe, non-production test settings; no database connection is opened.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://unused:unused@127.0.0.1/unused")
os.environ.setdefault("SECRET_KEY", "test-only-not-used-for-auth-0000000000000")
os.environ.setdefault("DB_CREDENTIALS_ENCRYPTION_KEY", "6M8FuWqloQBI_11SZcX5zGXwU-L0wZesFCQ_HLX6DMY=")
# CI has asyncpg; lightweight offline audits may only have SQLAlchemy installed.
if importlib.util.find_spec("asyncpg") is None:
    from sqlalchemy.orm import declarative_base
    db_stub = types.ModuleType("app.db.session")
    db_stub.Base = declarative_base()
    db_stub.AsyncSessionLocal = lambda: None
    db_stub.get_db = lambda: None
    sys.modules["app.db.session"] = db_stub
if "pywebpush" not in sys.modules:
    try:
        import pywebpush  # noqa: F401
    except ImportError:
        stub = types.ModuleType("pywebpush")
        stub.webpush = lambda **kwargs: None
        stub.WebPushException = type("WebPushException", (Exception,), {})
        sys.modules["pywebpush"] = stub

from app.services import oa_notification_outbox as oa  # noqa: E402
from app.services.push_service import PushService  # noqa: E402


class FakeResult:
    def scalars(self):
        return self

    def all(self):
        return [22]


class FakeDb:
    def __init__(self):
        self.added = []

    async def scalar(self, statement):
        return None

    async def get(self, model, employee_id):
        return None

    async def execute(self, statement):
        return FakeResult()

    def add(self, item):
        self.added.append(item)


class FakeDbContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_partial_successes_are_not_resent(monkeypatch):
    called_ids = []

    class FakePush:
        def __init__(self, db):
            pass

        async def notify_users(self, ids, *, subscription_ids, **kwargs):
            called_ids.append(subscription_ids)
            if len(called_ids) == 1:
                return {"attempted": 5, "results": [
                    {"id": 1, "status": "sent"}, {"id": 2, "status": "sent"},
                    {"id": 3, "status": "sent"}, {"id": 4, "status": "failed"},
                    {"id": 5, "status": "failed"},
                ]}
            return {"attempted": 2, "results": [
                {"id": 4, "status": "sent"}, {"id": 5, "status": "sent"},
            ]}

    async def fake_render(*args, **kwargs):
        return "new letter"

    monkeypatch.setattr(oa, "PushService", FakePush)
    monkeypatch.setattr(oa, "AsyncSessionLocal", FakeDbContext)
    monkeypatch.setattr(oa.notification_templates, "render", fake_render)
    db = FakeDb()
    event = SimpleNamespace(key="new_letter:23:203", payload={
        "employee_id": 203, "site_id": 1, "text_key": "oa.test", "url": "/automation/letters/23"
    })

    state, info = await oa._deliver_one(db, event)
    assert state == "pending" and "2 subscription" in info
    assert event.payload["_delivery"] == {"remaining": [4, 5], "sent": [1, 2, 3], "stale": []}
    state, info = await oa._deliver_one(db, event)
    assert state == "sent" and info is None
    assert called_ids == [None, {4, 5}]
    assert event.payload["_delivery"]["remaining"] == []
    assert len(db.added) == 1


@pytest.mark.asyncio
async def test_deleted_subscription_is_not_retried(monkeypatch):
    async def fake_render(*args, **kwargs):
        return "some letter"

    class FakePush:
        def __init__(self, db):
            pass

        async def notify_users(self, ids, *, subscription_ids, **kwargs):
            assert subscription_ids == {7}
            # Subscription was removed by logout during an earlier retry.
            return {"attempted": 0, "results": []}

    monkeypatch.setattr(oa, "PushService", FakePush)
    monkeypatch.setattr(oa, "AsyncSessionLocal", FakeDbContext)
    monkeypatch.setattr(oa.notification_templates, "render", fake_render)
    db = FakeDb()
    event = SimpleNamespace(key="return:24:203", payload={
        "employee_id": 203, "site_id": 1, "text_key": "oa.test", "url": "/automation/letters/24",
        "_delivery": {"remaining": [7], "sent": [6], "stale": []},
    })
    state, _ = await oa._deliver_one(db, event)
    assert state == "sent"
    assert event.payload["_delivery"]["remaining"] == []
    assert event.payload["_delivery"]["stale"] == [7]


def test_push_query_is_session_gated():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "app/services/push_service.py").read_text()
    assert "UserSession.revoked_at.is_(None)" in source
    assert "UserSession.last_seen_at >= expires_before" in source
    assert "PushSubscription.session_id == UserSession.id" in source
    assert "notification_key" in source


@pytest.mark.asyncio
async def test_push_has_stable_event_key_and_session_marker(monkeypatch):
    import json
    import app.services.push_service as push_module
    from types import SimpleNamespace

    recipient = SimpleNamespace(
        id=88, user_id=22, endpoint="https://fcm.googleapis.com/fcm/send/testing",
        p256dh="public-key", auth="auth-key",
    )
    payloads = []
    queries = []

    class Result:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

    class FakePushDb:
        async def execute(self, query):
            queries.append(str(query))
            if "JOIN user_sessions" in str(query):
                return Result([(recipient, "valid-sid-1")])
            return Result([])

    def accept_push(**kwargs):
        payloads.append(json.loads(kwargs["data"]))

    monkeypatch.setattr(push_module, "webpush", accept_push)
    monkeypatch.setattr(push_module, "settings", SimpleNamespace(
        VAPID_PRIVATE_KEY="test-key", VAPID_CLAIMS_EMAIL="test@example.com", REFRESH_TOKEN_EXPIRE_DAYS=7
    ))
    stats = await PushService(FakePushDb()).notify_users(
        {22}, body="new letter", notification_key="oa:new:52:203", return_stats=True,
    )
    assert stats["sent"] == 1 and stats["failed"] == 0
    assert stats["results"] == [{"id": 88, "status": "sent"}]
    assert payloads[0]["notification_key"] == "oa:new:52:203"
    assert payloads[0]["session_marker"] == "valid-sid-1"
    assert "user_sessions.revoked_at IS NULL" in queries[0]
    assert "user_sessions.last_seen_at" in queries[0]


@pytest.mark.asyncio
async def test_legacy_unlinked_subscriptions_are_never_sent(monkeypatch):
    import app.services.push_service as push_module
    from types import SimpleNamespace

    class EmptyDb:
        async def execute(self, query):
            return SimpleNamespace(all=lambda: [])

    def unexpected_webpush(**kwargs):
        raise AssertionError("unbound/revoked subscription must never be sent")

    monkeypatch.setattr(push_module, "webpush", unexpected_webpush)
    monkeypatch.setattr(push_module, "settings", SimpleNamespace(
        VAPID_PRIVATE_KEY="test-key", REFRESH_TOKEN_EXPIRE_DAYS=7
    ))
    stats = await PushService(EmptyDb()).notify_users({203}, body="new letter", return_stats=True)
    assert stats["attempted"] == 0 and stats["results"] == []
