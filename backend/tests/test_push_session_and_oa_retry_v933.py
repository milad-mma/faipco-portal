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
            assert kwargs["session_bindings"] == {sid: 100 + sid for sid in subscription_ids}
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

    async def recipient(db, payload):
        return {22}, payload["text_key"], {}

    monkeypatch.setattr(oa, "_current_recipient", recipient)
    monkeypatch.setattr(oa, "PushService", FakePush)
    monkeypatch.setattr(oa, "AsyncSessionLocal", FakeDbContext)
    monkeypatch.setattr(oa.notification_templates, "render", fake_render)
    db = FakeDb()
    event = SimpleNamespace(key="new_letter:23:203", payload={
        "employee_id": 203, "site_id": 1, "text_key": "oa.test", "url": "/automation/letters/23"
    })

    async def bindings(db, ids):
        return {str(i): 100 + i for i in range(1, 6)}

    monkeypatch.setattr(oa, "_snapshot_bindings", bindings)
    state, info = await oa._deliver_one(db, event)
    assert state == "initialized" and not called_ids
    state, info = await oa._deliver_one(db, event)
    assert state == "pending" and "2 subscription" in info
    assert event.payload["_delivery"]["remaining"] == [4, 5]
    assert event.payload["_delivery"]["sent"] == [1, 2, 3]
    state, info = await oa._deliver_one(db, event)
    assert state == "sent" and info is None
    assert called_ids == [{1, 2, 3, 4, 5}, {4, 5}]
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

    async def recipient(db, payload):
        return {22}, payload["text_key"], {}

    monkeypatch.setattr(oa, "_current_recipient", recipient)
    monkeypatch.setattr(oa, "PushService", FakePush)
    monkeypatch.setattr(oa, "AsyncSessionLocal", FakeDbContext)
    monkeypatch.setattr(oa.notification_templates, "render", fake_render)
    db = FakeDb()
    event = SimpleNamespace(key="return:24:203", payload={
        "employee_id": 203, "site_id": 1, "text_key": "oa.test", "url": "/automation/letters/24",
        "_delivery": {"remaining": [7], "sent": [6], "stale": [], "bindings": {"7": 107}},
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


@pytest.mark.asyncio
async def test_network_error_does_not_log_private_endpoint_or_keys(monkeypatch, caplog):
    import app.services.push_service as push_module
    endpoint = "https://fcm.googleapis.com/fcm/send/private-endpoint-test"
    sub = SimpleNamespace(id=88, user_id=22, endpoint=endpoint,
                          p256dh="private-p256dh-test", auth="private-auth-test")

    class FakePushDb:
        async def execute(self, query):
            rows = [(sub, "valid-sid")] if "JOIN user_sessions" in str(query) else []
            return SimpleNamespace(all=lambda: rows)

    def fail(**kwargs):
        raise TimeoutError(f"timeout at {endpoint}; auth={sub.auth}; key={sub.p256dh}")

    monkeypatch.setattr(push_module, "webpush", fail)
    monkeypatch.setattr(push_module, "settings", SimpleNamespace(
        VAPID_PRIVATE_KEY="test-key", VAPID_CLAIMS_EMAIL="test@example.com", REFRESH_TOKEN_EXPIRE_DAYS=7
    ))
    stats = await PushService(FakePushDb()).notify_users({22}, body="notice", return_stats=True)
    assert stats["failed"] == 1 and stats["sent"] == 0
    assert "TimeoutError" in caplog.text and "subscription_id=88" in caplog.text
    assert "fcm.googleapis.com" in caplog.text
    assert "private-endpoint-test" not in caplog.text
    assert "private-auth-test" not in caplog.text
    assert "private-p256dh-test" not in caplog.text


@pytest.mark.asyncio
async def test_no_eligible_session_has_diagnostic_but_never_sends(monkeypatch, caplog):
    import logging
    import app.services.push_service as push_module

    class EmptyDb:
        async def execute(self, query):
            return SimpleNamespace(all=lambda: [])

    def forbidden(**kwargs):
        pytest.fail("no eligible session: never send")

    monkeypatch.setattr(push_module, "webpush", forbidden)
    monkeypatch.setattr(push_module, "settings", SimpleNamespace(
        VAPID_PRIVATE_KEY="test-key", REFRESH_TOKEN_EXPIRE_DAYS=7
    ))
    with caplog.at_level(logging.INFO, logger="faipco.push"):
        stats = await PushService(EmptyDb()).notify_users({22}, body="notice", return_stats=True)
    assert stats["attempted"] == 0
    assert "no eligible session-bound subscriptions" in caplog.text


@pytest.mark.asyncio
async def test_notice_dispatch_insert_is_idempotent_and_does_not_commit():
    from datetime import timedelta
    from sqlalchemy.dialects import postgresql
    from app.services import push_dispatch as dispatch
    now = dispatch.utcnow()
    statements = []

    class Db:
        async def execute(self, statement):
            statements.append(statement.compile(dialect=postgresql.dialect()))

        async def commit(self):
            pytest.fail("publication owns commit")

    notice = SimpleNamespace(id=269, publish_at=now + timedelta(hours=2),
                             notice_type="payroll", priority="high")
    await dispatch.enqueue_notice_push(Db(), notice)
    await dispatch.enqueue_notice_push(Db(), notice)
    assert "ON CONFLICT (key) DO NOTHING" in str(statements[0])
    assert statements[0].params["key"] == statements[1].params["key"] == "dispatch:notice:269:publish"
    assert statements[0].params["next_attempt_at"] == notice.publish_at
    assert statements[0].params["url"] == "/notices?type=payroll"
    await dispatch.enqueue_notice_push(Db(), notice, user_ids={22}, resend=True)
    assert statements[2].params["key"] != statements[0].params["key"]
    assert statements[2].params["user_ids"] == [22]


def test_dispatch_retry_and_terminal_states():
    from app.services import push_dispatch as dispatch
    now = dispatch.utcnow()
    deadline = now + dispatch.RETRY_WINDOW
    row = SimpleNamespace(attempts=0, status="pending", next_attempt_at=now)
    dispatch.apply_delivery_result(row, "failed", now, deadline)
    assert row.status == "pending" and row.next_attempt_at == now + dispatch.retry_delay(1)
    dispatch.apply_delivery_result(row, "sent", now, deadline)
    assert row.status == "accepted" and row.accepted_at == now
    for result in ("stale", "ineligible"):
        dispatch.apply_delivery_result(row, result, now, deadline)
        assert row.status == result
    row.attempts = dispatch.MAX_ATTEMPTS - 1
    dispatch.apply_delivery_result(row, "failed", now, deadline)
    assert row.status == "failed"
    assert dispatch.retry_delay(999).total_seconds() <= 21600


@pytest.mark.asyncio
async def test_dispatch_no_device_unread_notice_waits_for_registration(monkeypatch):
    from app.services import push_dispatch as dispatch
    now = dispatch.utcnow()
    async def no_devices(*args): return set()
    monkeypatch.setattr(dispatch, "add_devices", no_devices)
    job = SimpleNamespace(notice_id=269, status="pending", deadline_at=now+dispatch.RETRY_WINDOW)
    await dispatch.initialize_job(object(), job, {22}, now)
    assert job.status == "pending" and job.initialized
    assert job.no_device_count == 1 and job.next_attempt_at > now
    generic = SimpleNamespace(notice_id=None, id=3, status="pending", body="test")
    await dispatch.initialize_job(object(), generic, {22}, now)
    assert generic.status == "no_devices" and generic.body is None


@pytest.mark.asyncio
async def test_dispatch_batch_retries_only_failed_device_and_preserves_session(monkeypatch):
    from app.services import push_dispatch as dispatch
    now = dispatch.utcnow()
    rows = [SimpleNamespace(id=i, user_id=22, subscription_id=i, session_id=i+100, status="pending", attempts=0, next_attempt_at=now) for i in (1,2)]
    job = SimpleNamespace(id=1, notice_id=None, initialized=True, user_ids=[22],
                          deadline_at=now+dispatch.RETRY_WINDOW, url="/notices", body=None,
                          priority="normal", notice_type="normal", key="dispatch:generic:test")
    calls = []
    class Db:
        async def execute(self, statement):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [r for r in rows if r.status == "pending"]))
    class Transport:
        def __init__(self, db): pass
        async def notify_users(self, ids, **kwargs):
            calls.append(kwargs["session_bindings"])
            assert kwargs["notification_key"] == job.key
            return {"results":[{"id":i,"status":"failed" if i==2 and len(calls)==1 else "sent"} for i in calls[-1]]}
    async def no_finalize(*args): pass
    monkeypatch.setattr(dispatch,"AsyncSessionLocal", FakeDbContext)
    monkeypatch.setattr(dispatch,"PushService", Transport)
    monkeypatch.setattr(dispatch,"finish_if_ready", no_finalize)
    await dispatch.process_job(Db(),job,now)
    assert [r.status for r in rows]==["accepted","pending"]
    await dispatch.process_job(Db(),job,rows[1].next_attempt_at)
    assert calls==[{1:101,2:102},{2:102}]
    assert all(r.status=="accepted" for r in rows)


@pytest.mark.asyncio
async def test_dispatch_expired_job_never_contacts_transport(monkeypatch):
    from app.services import push_dispatch as dispatch
    now = dispatch.utcnow()
    job = SimpleNamespace(id=2,deadline_at=now,body="private body")
    class Db:
        async def execute(self, statement):
            assert "push_dispatch_deliveries" in str(statement)
    def forbidden(*args): pytest.fail("expired job cannot send")
    monkeypatch.setattr(dispatch,"PushService", forbidden)
    await dispatch.process_job(Db(),job,now)
    assert job.status=="expired" and job.body is None
