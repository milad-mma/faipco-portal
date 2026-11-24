"""Modern client readiness: no network before gate ACK; durable fast wake.

All provider and database interactions here are mocked or SQL compiled.
"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from tests import test_push_session_and_oa_retry_v933 as fixtures
from tests.test_deferred_push_login import MemoryQueue
from app.services import push_dispatch as dispatch, push_service


def payload(ready):
    return SimpleNamespace(client_ready=ready,
        endpoint="https://fcm.googleapis.com/fcm/send/example",
        keys=SimpleNamespace(p256dh="public", auth="auth"))


def compiled(statement):
    return statement.compile(dialect=postgresql.dialect())


def test_unready_devices_are_excluded_but_legacy_null_is_eligible():
    sql = str(compiled(push_service.eligible_subscriptions({20})))
    assert "push_subscriptions.client_ready IS NOT false" in sql
    assert "user_sessions.revoked_at IS NULL" in sql
    assert "user_sessions.user_id = push_subscriptions.user_id" in sql


@pytest.mark.asyncio
async def test_prepare_commits_unready_binding_without_waking(monkeypatch):
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: 739)),
                         commit=AsyncMock(), rollback=AsyncMock())
    wake = AsyncMock()
    monkeypatch.setattr(dispatch, "wake_waiting_jobs", wake)
    await push_service.PushService(db).save_subscription(11, payload(False), session_id=540)
    sql = compiled(db.execute.call_args.args[0])
    assert sql.params["client_ready"] is False
    assert "IS DISTINCT FROM" in str(sql)
    db.commit.assert_awaited_once()
    wake.assert_not_awaited()


@pytest.mark.asyncio
async def test_ready_ack_matches_exact_current_binding_and_wakes_after_commit(monkeypatch):
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: 739)),
                         commit=AsyncMock(), rollback=AsyncMock())
    async def wake(db_arg, uid, *, ready):
        assert db_arg is db and uid == 11 and ready is True
        db.commit.assert_awaited_once()
        return [30], ["letter:1"]
    monkeypatch.setattr(dispatch, "wake_waiting_jobs", wake)
    assert await push_service.PushService(db).confirm_subscription_ready(11, payload(True), session_id=540) == ([30], ["letter:1"], True)
    sql = compiled(db.execute.call_args.args[0])
    for name in ("user_id", "session_id", "endpoint", "p256dh", "auth"):
        assert f"push_subscriptions.{name} =" in str(sql)
    assert 11 in sql.params.values() and 540 in sql.params.values()
    assert sql.params["client_ready"] is True
    assert "ON CONFLICT" not in str(sql)
    assert db.commit.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("exists,expected", [(None, None), (739, ([], [], False))])
async def test_stale_or_duplicate_ack_does_not_rebind_or_wake(monkeypatch, exists, expected):
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
                         scalar=AsyncMock(return_value=exists), commit=AsyncMock(), rollback=AsyncMock())
    wake = AsyncMock()
    monkeypatch.setattr(dispatch, "wake_waiting_jobs", wake)
    assert await push_service.PushService(db).confirm_subscription_ready(11, payload(True), session_id=540) == expected
    wake.assert_not_awaited()
    assert "UPDATE" in str(compiled(db.execute.call_args.args[0]))
    assert "INSERT" not in str(compiled(db.execute.call_args.args[0]))


@pytest.mark.asyncio
async def test_ready_ack_remains_durable_if_queue_hint_fails(monkeypatch):
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: 739)),
                         commit=AsyncMock(), rollback=AsyncMock())
    monkeypatch.setattr(dispatch, "wake_waiting_jobs", AsyncMock(side_effect=RuntimeError("locked")))
    assert await push_service.PushService(db).confirm_subscription_ready(11, payload(True), session_id=540) == ([], [], True)
    db.commit.assert_awaited_once()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_ready_wake_is_due_now_and_does_not_revive_terminal_or_accepted_events(monkeypatch):
    now = dispatch.utcnow()
    monkeypatch.setattr(dispatch, "utcnow", lambda: now)
    monkeypatch.setattr(dispatch, "dispatch_origin", lambda: "https://portal-test.faipco.ir")
    def result(values):
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: values))
    db = SimpleNamespace(execute=AsyncMock(side_effect=[result([30]), result(["letter:1"])]))
    assert await dispatch.wake_waiting_jobs(db, 11, ready=True) == ([30], ["letter:1"])
    first, second = [compiled(call.args[0]) for call in db.execute.call_args_list]
    for sql in (first, second):
        text = str(sql)
        assert now in sql.params.values()
        assert now + dispatch.DEVICE_REGISTRATION_GRACE not in sql.params.values()
        assert "least(" in text and "FOR UPDATE SKIP LOCKED" in text and "RETURNING" in text
        assert [11] in sql.params.values()
        assert "pending" in sql.params.values()
        assert "awaiting_eligible_devices" in sql.params.values()
    assert "NOT (EXISTS" in str(first)
    assert ["pending", "accepted"] in first.params.values()
    assert "push_dispatch_jobs.deadline_at >" in str(first)
    assert "next_attempt_at <=" in str(first)
    assert "recipient_user_ids" in second.params.values()


@pytest.mark.asyncio
async def test_ready_snapshot_immediate_legacy_snapshot_keeps_grace():
    now = dispatch.utcnow()
    db = SimpleNamespace(execute=AsyncMock(side_effect=[
        SimpleNamespace(all=lambda: [(739, 540, 11, True), (741, 541, 12, None)]),
        None,
    ]))
    assert await dispatch.add_devices(db, SimpleNamespace(id=30), {11, 12}, now, recovering=True) == {11, 12}
    sql = compiled(db.execute.call_args_list[1].args[0])
    assert sql.params["next_attempt_at_m0"] == now
    assert sql.params["next_attempt_at_m1"] == now + dispatch.DEVICE_REGISTRATION_GRACE
    assert "ON CONFLICT" in str(sql)


@pytest.mark.asyncio
async def test_ready_recovery_has_no_artificial_delay_but_snapshots_before_send(monkeypatch):
    q = MemoryQueue(monkeypatch, {20})
    now = dispatch.utcnow()
    await q.process(now)
    assert q.job.last_error == "awaiting_eligible_devices"
    ready_at = now + timedelta(seconds=1)
    q.devices = {20: [(739, 540)]}
    q.ready_bindings = {(739, 540)}
    await q.process(ready_at)
    assert not q.calls
    assert q.rows[0].next_attempt_at == ready_at
    assert q.job.next_attempt_at == ready_at
    await q.process(ready_at)
    assert q.calls == [({20}, {739: 540}, q.job.key)]
    assert q.job.status == "accepted" and q.rows[0].attempts == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("ready", [True, False])
async def test_oa_rebound_uses_grace_only_for_legacy_bindings(monkeypatch, ready):
    oa = fixtures.oa
    now = dispatch.utcnow()
    event = SimpleNamespace(id=30, key="letter:1", created_at=now, status="pending",
                            payload={"_delivery": {"remaining": [739], "bindings": {"739": 540}}})
    db = SimpleNamespace(scalar=AsyncMock(return_value=True), commit=AsyncMock(),
                         execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: event)))
    class Context:
        async def __aenter__(self): return db
        async def __aexit__(self, *args): return False
    monkeypatch.setattr(oa, "AsyncSessionLocal", Context)
    monkeypatch.setattr(oa, "_deliver_one", AsyncMock(return_value=("rebound", None)))
    check = AsyncMock(return_value=ready)
    monkeypatch.setattr(oa, "bindings_are_ready", check)
    assert await oa.drain_oa_outbox(limit=1, keys=["letter:1"]) == 1
    check.assert_awaited_once_with(db, {"739": 540})
    delay = (event.next_attempt_at - now).total_seconds()
    assert 0 <= delay < 1 if ready else 30 <= delay < 31
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_fast_drain_is_targeted_and_second_wake_uses_new_session(monkeypatch):
    oa = fixtures.oa
    direct = AsyncMock(return_value=1)
    letters = AsyncMock(return_value=1)
    monkeypatch.setattr(dispatch, "drain_push_dispatch_jobs", direct)
    monkeypatch.setattr(oa, "drain_oa_outbox", letters)
    monkeypatch.setattr(dispatch.asyncio, "sleep", AsyncMock())
    db = SimpleNamespace(commit=AsyncMock())
    class Context:
        async def __aenter__(self): return db
        async def __aexit__(self, *args): return False
    monkeypatch.setattr(dispatch, "AsyncSessionLocal", Context)
    wake = AsyncMock(return_value=([31], ["letter:2"]))
    monkeypatch.setattr(dispatch, "wake_waiting_jobs", wake)
    await dispatch.drain_ready_jobs(11, [30], ["letter:1"])
    assert [c.kwargs["job_ids"] for c in direct.call_args_list] == [[30], [31]]
    assert [c.kwargs["keys"] for c in letters.call_args_list] == [["letter:1"], ["letter:2"]]
    wake.assert_awaited_once_with(db, 11, ready=True)
    db.commit.assert_awaited_once()
