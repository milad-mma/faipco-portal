"""Deferred notification regression tests; no real devices or external DB writes."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
import sys
import types

import pytest
from sqlalchemy.dialects import postgresql

from tests import test_push_session_and_oa_retry_v933 as fixtures
from app.services import push_dispatch as dispatch, push_audience, push_service


class Result:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows

    def scalar_one(self):
        return self.rows[0]


class MemoryQueue:
    """Emulate the delivery queries; retain real dispatcher state transitions."""
    def __init__(self, monkeypatch, ids):
        self.audience = set(ids)
        self.devices = {}
        self.rows = []
        self.calls = []
        self.missing = set()
        self.job = SimpleNamespace(id=1, key="dispatch:advance:70:722:paid", notice_id=None,
            user_ids=sorted(ids), initialized=False, status="pending", body="payment",
            url="/advances?tab=mine", priority="normal", notice_type="normal",
            deadline_at=dispatch.utcnow()+dispatch.RETRY_WINDOW, next_attempt_at=dispatch.utcnow())
        monkeypatch.setattr(dispatch, "current_audience", self.current_audience)
        monkeypatch.setattr(dispatch, "add_devices", self.add_devices)
        monkeypatch.setattr(dispatch, "AsyncSessionLocal", fixtures.FakeDbContext)
        monkeypatch.setattr(dispatch, "PushService", lambda db: self)

    async def current_audience(self, db, job, now):
        return self.audience & set(job.user_ids)

    async def add_devices(self, db, job, ids, due):
        found = set()
        for uid in ids:
            for sid, session in self.devices.get(uid, []):
                found.add(uid)
                if any((r.subscription_id, r.session_id) == (sid, session) for r in self.rows):
                    continue
                self.rows.append(SimpleNamespace(id=len(self.rows)+1, user_id=uid,
                    subscription_id=sid, session_id=session, status="pending", attempts=0,
                    next_attempt_at=due, accepted_at=None, last_error=None))
        return found

    async def flush(self):
        pass

    async def execute(self, statement):
        sql = str(statement)
        if "GROUP BY" in sql:
            return Result([(state, sum(r.status == state for r in self.rows))
                           for state in {r.status for r in self.rows}])
        if "SELECT DISTINCT" in sql:
            return Result(list({r.user_id for r in self.rows if r.status in ("pending", "accepted")}))
        if "min(" in sql:
            return Result([min(r.next_attempt_at for r in self.rows if r.status == "pending")])
        if "ORDER BY" in sql:
            due = next(v for k, v in statement.compile().params.items() if k.startswith("next_attempt_at"))
            return Result([r for r in self.rows if r.status == "pending" and r.next_attempt_at <= due][:dispatch.BATCH_SIZE])
        raise AssertionError(sql)

    async def notify_users(self, ids, **kwargs):
        self.calls.append((set(ids), kwargs["session_bindings"], kwargs["notification_key"]))
        return {"results": [{"id": sid, "status": "sent"} for sid, session in
                            kwargs["session_bindings"].items() if (sid, session) not in self.missing]}

    async def process(self, now=None):
        await dispatch.process_job(self, self.job, now or self.job.next_attempt_at)


@pytest.mark.asyncio
async def test_paid_event_waits_without_device_then_rebinds_to_new_login(monkeypatch):
    q = MemoryQueue(monkeypatch, {20})
    await q.process()
    assert q.job.status == "pending" and q.job.no_device_count == 1
    assert q.job.body == "payment" and not q.rows and not q.calls
    assert q.job.last_error == "awaiting_eligible_devices"
    q.devices = {20: [(709, 81)], 19: [(710, 82)]}
    await q.process()
    assert not q.calls  # the new registration receives its grace interval
    assert [(r.user_id, r.session_id) for r in q.rows] == [(20, 81)]
    await q.process()
    assert q.calls == [({20}, {709: 81}, q.job.key)]
    assert q.job.status == "accepted" and q.job.no_device_count == 0 and q.job.body is None
    assert q.rows[0].attempts == 1


@pytest.mark.asyncio
async def test_group_waits_only_for_unaccepted_accounts(monkeypatch):
    q = MemoryQueue(monkeypatch, {20, 21})
    q.devices = {20: [(709, 81)]}
    await q.process()  # initial snapshot
    await q.process()  # first accepted
    assert q.job.status == "pending" and q.job.no_device_count == 1
    q.devices = {20: [(711, 83)], 21: [(712, 84)]}
    await q.process()  # new binding only for 21
    await q.process()
    assert q.calls == [({20}, {709: 81}, q.job.key), ({21}, {712: 84}, q.job.key)]
    assert q.job.status == "accepted" and q.job.no_device_count == 0


@pytest.mark.asyncio
async def test_old_revoked_binding_is_not_reused_but_new_session_can_recover(monkeypatch):
    q = MemoryQueue(monkeypatch, {20})
    q.devices = {20: [(709, 81)]}
    await q.process()
    q.missing.add((709, 81))
    q.devices = {}
    await q.process()
    assert q.job.status == "pending" and q.rows[0].status == "ineligible"
    q.devices = {20: [(709, 82)]}
    await q.process()
    await q.process()
    assert q.calls == [({20}, {709: 81}, q.job.key), ({20}, {709: 82}, q.job.key)]
    assert [r.status for r in q.rows] == ["ineligible", "accepted"]
    assert q.job.no_device_count == 0 and q.job.status == "partial"


@pytest.mark.asyncio
async def test_revoked_domain_audience_never_gets_deferred_event(monkeypatch):
    q = MemoryQueue(monkeypatch, {20})
    await q.process()
    q.audience.clear()
    q.devices = {20: [(709, 81)]}
    await q.process()
    assert not q.calls and not q.rows and q.job.body is None
    assert q.job.status == "not_accepted"


@pytest.mark.asyncio
async def test_scope_check_on_new_binding_blocks_send(monkeypatch):
    q = MemoryQueue(monkeypatch, {20})
    await q.process()
    q.devices = {20: [(709, 81)]}
    await q.process()
    monkeypatch.setattr(push_audience, "restrict_delivery_audience", AsyncMock(return_value=set()))
    await q.process()
    assert not q.calls and q.rows[0].status == "ineligible"
    assert q.job.body is None


@pytest.mark.parametrize("key,allowed", [
    ("dispatch:advance:70:722:paid", True), ("dispatch:loan:1:2:paid", True),
    ("dispatch:leave:123:1.abc:approver_pending", True),
    ("dispatch:leave:123:legacy:approver_pending", False),
    ("dispatch:leave:unknown:1.abc:approved", False),
    ("dispatch:generic:old", False), ("dispatch:unknown:1:2:x", False),
    ("dispatch:photo:1:approved:transition", True),
    ("dispatch:evaluation:20:2026-11-24:reminder", True),
])
def test_explicit_events_only(key, allowed):
    assert dispatch.can_defer(SimpleNamespace(notice_id=None, key=key)) == allowed


@pytest.mark.asyncio
async def test_registration_wakes_only_pending_original_account(monkeypatch):
    db = SimpleNamespace(execute=AsyncMock())
    monkeypatch.setattr(dispatch, "dispatch_origin", lambda: "https://portal-test.faipco.ir")
    await dispatch.wake_waiting_jobs(db, 20)
    assert db.execute.await_count == 2
    for call in db.execute.call_args_list:
        sql = call.args[0].compile(dialect=postgresql.dialect())
        assert "FOR UPDATE SKIP LOCKED" in str(sql) and "@>" in str(sql)
        assert [20] in sql.params.values()
        assert "pending" in sql.params.values() and "awaiting_eligible_devices" in sql.params.values()
        assert "LIMIT" in str(sql)
    assert "https://portal-test.faipco.ir" in db.execute.call_args_list[0].args[0].compile(dialect=postgresql.dialect()).params.values()


@pytest.mark.asyncio
async def test_subscription_wake_failure_does_not_fail_registration(monkeypatch):
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: 709)),
                         commit=AsyncMock(), rollback=AsyncMock())
    async def wake(db_arg, uid):
        assert uid == 20 and db.commit.await_count == 1
        raise RuntimeError("wake failure")
    monkeypatch.setattr(dispatch, "wake_waiting_jobs", wake)
    payload = SimpleNamespace(endpoint="https://fcm.googleapis.com/fcm/send/test", keys=SimpleNamespace(p256dh="key", auth="auth"))
    await push_service.PushService(db).save_subscription(20, payload, session_id=81)
    db.commit.assert_awaited_once()
    db.rollback.assert_awaited_once()
    sql = db.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    assert "IS DISTINCT FROM" in str(sql) and "RETURNING" in str(sql)


@pytest.mark.asyncio
async def test_unchanged_registration_does_not_wake_again(monkeypatch):
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
                         commit=AsyncMock(), rollback=AsyncMock())
    wake = AsyncMock()
    monkeypatch.setattr(dispatch, "wake_waiting_jobs", wake)
    payload = SimpleNamespace(endpoint="https://fcm.googleapis.com/fcm/send/test", keys=SimpleNamespace(p256dh="key", auth="auth"))
    await push_service.PushService(db).save_subscription(20, payload, session_id=81)
    wake.assert_not_awaited()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_oa_waits_then_rebinds_without_changing_confidentiality(monkeypatch):
    oa = fixtures.oa
    bindings = {}
    calls = []
    async def snapshot(db, ids):
        assert ids == {20}
        return dict(bindings)
    async def send(ids, **kwargs):
        assert ids == {20} and kwargs["body"] == "confidential"
        calls.append(kwargs["session_bindings"])
        return {"results": [{"id": sid, "status": "sent"} for sid in kwargs["session_bindings"]]}
    monkeypatch.setattr(oa, "_current_recipient", AsyncMock(return_value=({20}, "automation.confidential", {})))
    monkeypatch.setattr(oa, "_snapshot_bindings", snapshot)
    monkeypatch.setattr(oa.notification_templates, "render", AsyncMock(return_value="confidential"))
    monkeypatch.setattr(oa, "AsyncSessionLocal", fixtures.FakeDbContext)
    monkeypatch.setattr(oa, "PushService", lambda db: SimpleNamespace(notify_users=send))
    db = fixtures.FakeDb()
    event = SimpleNamespace(key="new_letter:23:203:x", created_at=dispatch.utcnow(),
        payload={"employee_id":203,"site_id":1,"url":"/automation/letters/23","text_key":"automation.confidential"})
    assert (await oa._deliver_one(db, event))[0] == "waiting"
    assert (await oa._deliver_one(db, event))[0] == "waiting"
    assert not db.added and not calls
    bindings["709"] = 81
    assert (await oa._deliver_one(db, event))[0] == "rebound"
    assert not calls
    assert (await oa._deliver_one(db, event))[0] == "sent"
    assert calls == [{709:81}]
    assert event.payload["_delivery"]["recipient_user_ids"] == [20]
    assert len(db.added) == 1


@pytest.mark.asyncio
async def test_oa_waiting_job_does_not_follow_different_account(monkeypatch):
    oa = fixtures.oa
    recipient = AsyncMock(return_value=({20}, "automation.confidential", {}))
    monkeypatch.setattr(oa, "_current_recipient", recipient)
    monkeypatch.setattr(oa, "_snapshot_bindings", AsyncMock(return_value={}))
    db = fixtures.FakeDb()
    event = SimpleNamespace(key="new_letter:23:203:x", created_at=dispatch.utcnow(),
        payload={"employee_id":203,"site_id":1,"url":"/automation/letters/23","text_key":"automation.confidential"})
    assert (await oa._deliver_one(db, event))[0] == "waiting"
    recipient.return_value = ({21}, "automation.confidential", {})
    monkeypatch.setattr(oa, "PushService", lambda db: pytest.fail("different account must not receive"))
    assert (await oa._deliver_one(db, event))[0] == "skipped"


@pytest.mark.asyncio
async def test_oa_old_binding_replaced_only_after_no_acceptance(monkeypatch):
    oa = fixtures.oa
    bindings = {"709":81}
    calls = []
    async def snapshot(db, ids): return dict(bindings)
    async def send(ids, **kwargs):
        calls.append(kwargs["session_bindings"])
        return {"results": [] if len(calls)==1 else [{"id":709,"status":"sent"}]}
    monkeypatch.setattr(oa, "_current_recipient", AsyncMock(return_value=({20}, "automation.new", {})))
    monkeypatch.setattr(oa, "_snapshot_bindings", snapshot)
    monkeypatch.setattr(oa.notification_templates, "render", AsyncMock(return_value="new"))
    monkeypatch.setattr(oa, "AsyncSessionLocal", fixtures.FakeDbContext)
    monkeypatch.setattr(oa, "PushService", lambda db: SimpleNamespace(notify_users=send))
    db = fixtures.FakeDb()
    event = SimpleNamespace(key="new_letter:23:203:x", created_at=dispatch.utcnow(),
        payload={"employee_id":203,"site_id":1,"url":"/automation/letters/23","text_key":"automation.new"})
    assert (await oa._deliver_one(db, event))[0] == "initialized"
    assert (await oa._deliver_one(db, event))[0] == "waiting"
    assert (await oa._deliver_one(db, event))[0] == "waiting"  # same old pair, never resend
    bindings["709"] = 82
    assert (await oa._deliver_one(db, event))[0] == "rebound"
    assert (await oa._deliver_one(db, event))[0] == "sent"
    assert calls == [{709:81}, {709:82}]
    assert event.payload["_delivery"]["seen_bindings"] == ["709:81", "709:82"]


@pytest.mark.asyncio
async def test_leave_revalidates_current_site_and_actual_cartable(monkeypatch):
    employee = SimpleNamespace(site_id=1)
    service = SimpleNamespace(list_pending_for_approver=AsyncMock(return_value=[
        {"request_id":123,"status":"pending","awaiting_hr":False}]))
    module = types.ModuleType("app.services.leave_request_service")
    module.LeaveRequestService = lambda db: service
    monkeypatch.setitem(sys.modules, module.__name__, module)
    db = SimpleNamespace(execute=AsyncMock(return_value=Result([(20, employee)])))
    job = SimpleNamespace(key="dispatch:leave:123:1.abc:approver_pending")
    now = dispatch.utcnow()
    assert await push_audience.restrict_delivery_audience(db, job, {20}, now) == {20}
    service.list_pending_for_approver.assert_awaited_once_with(employee, request_id=123)
    sql = db.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    assert "employees.site_id" in str(sql) and 1 in sql.params.values()
    service.list_pending_for_approver.return_value = []
    assert await push_audience.restrict_delivery_audience(db, job, {20}, now) == set()
    service.list_pending_for_approver.side_effect = TimeoutError("KaraWeb offline")
    with pytest.raises(TimeoutError):
        await push_audience.restrict_delivery_audience(db, job, {20}, now)
