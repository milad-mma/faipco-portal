"""Offline regression tests for the transactional push boundary (no real notifications)."""
import base64
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
# Reuse this existing module's offline dependency setup, not its test functions.
from tests import test_push_session_and_oa_retry_v933 as fixtures
from app.services import push_dispatch as dispatch, business_push, push_audience
from app.services import push_service, notification_templates
from app.core.push_endpoint_policy import PushHTTPSession, valid_push_endpoint
from app.schemas.push import PushSubscriptionIn
from sqlalchemy.dialects import postgresql


@pytest.mark.parametrize('count', [1, 100, 152, 500, 1000])
@pytest.mark.asyncio
async def test_bulk_finance_events_are_enqueued_once_per_event_in_callers_transaction(monkeypatch, count):
    class Db:
        def __init__(self):
            self.statements = []
            self.flushes = 0
            self.lookups = 0
        async def flush(self):
            self.flushes += 1
        async def execute(self, statement):
            compiled = statement.compile(dialect=postgresql.dialect())
            if str(compiled).startswith('SELECT'):
                self.lookups += 1
                return SimpleNamespace(all=lambda: [(i, i+2000) for i in range(count)])
            self.statements.append(compiled)
        async def commit(self):
            pytest.fail('enqueue must not commit')
    db = Db()
    get_text = AsyncMock(return_value='پرداخت {amount}')
    monkeypatch.setattr(notification_templates, 'get_text', get_text)
    pushes = [(SimpleNamespace(id=70+i), SimpleNamespace(id=722+i), {i}, '/advances?tab=mine', 1,
               'advance.paid', {'amount': str(i)}) for i in range(count)]
    await business_push.queue_workflow_pushes(db, pushes)
    assert db.lookups == db.flushes == 1
    assert get_text.await_count == 1
    assert len(db.statements) == count
    assert len({s.params['key'] for s in db.statements}) == count
    assert db.statements[0].params['key'] == 'dispatch:advance:70:722:paid'
    assert all('ON CONFLICT (key) DO NOTHING' in str(s) for s in db.statements)
    assert db.statements[-1].params['user_ids'] == [count-1+2000]


@pytest.mark.asyncio
async def test_empty_recipient_event_is_traceable_and_has_no_message():
    db = SimpleNamespace(execute=AsyncMock(), commit=AsyncMock())
    await dispatch.enqueue_event_push(db, [], '/profile', 'private', event_key='dispatch:photo:1:approved:transition')
    params = db.execute.call_args.args[0].compile(dialect=postgresql.dialect()).params
    assert params['status'] == 'no_targets' and params['body'] is None
    db.commit.assert_not_awaited()


@pytest.mark.parametrize('url', ['https://fcm.googleapis.com/fcm/send/example', 'https://web.push.apple.com/Qexample',
    'https://updates.push.services.mozilla.com/wpush/v2/example', 'https://db5.notify.windows.com/w/example'])
def test_known_browser_provider_allowed(url):
    assert valid_push_endpoint(url)


@pytest.mark.parametrize('url', ['http://fcm.googleapis.com/fcm/send/test', 'https://127.0.0.1/a',
    'https://169.254.169.254/latest/meta-data', 'https://fcm.googleapis.com.attacker.test/a',
    'https://fcm.googleapis.com@attacker.test/a', 'https://fcm.googleapis.com:444/a',
    'https://fcm.googleapis.com./a', 'https://fcm.googleapis.com/a#fragment', 'https://fcm.googleapis.com\\@evil.test/a'])
def test_unsafe_provider_rejected(url):
    assert not valid_push_endpoint(url)


def test_subscription_key_validation_and_redirect_protection(monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    encode = lambda x: base64.urlsafe_b64encode(x).decode().rstrip('=')
    data = {'endpoint':'https://fcm.googleapis.com/fcm/send/example', 'keys': {'p256dh':encode(key), 'auth':encode(b'1'*16)}}
    assert PushSubscriptionIn.model_validate(data).keys.auth == data['keys']['auth']
    with pytest.raises(ValueError):
        PushSubscriptionIn.model_validate({**data, 'keys': {**data['keys'], 'auth':'x'*22}})
    import requests
    calls = []
    monkeypatch.setattr(requests.Session, 'request', lambda self, method, url, **kw: calls.append(kw))
    with PushHTTPSession() as session:
        session.request('POST', data['endpoint'], allow_redirects=True, verify=False)
        with pytest.raises(ValueError):
            session.request('POST','https://localhost/a')
    assert calls == [{'allow_redirects':False, 'verify':True}]


def test_payload_length_and_non_recursive_template_replacement():
    payload = push_service.bounded_payload({'title':'الف'*200, 'body':'😀'*1000, 'url':'/profile', 'session_marker':'s'})
    assert len(payload.encode()) <= push_service.MAX_PAYLOAD_BYTES
    assert json.loads(payload)['url'] == '/profile'
    assert notification_templates.fill('{name} / {amount}', name='{amount}', amount='100') == '{amount} / 100'


def test_permanent_provider_error_is_terminal_and_429_retry_after_is_respected():
    now = dispatch.utcnow()
    row = SimpleNamespace(attempts=0, status='pending')
    dispatch.apply_delivery_result(row, 'permanent', now, now+timedelta(days=7), error='http_400')
    assert row.status == 'failed' and row.last_error == 'http_400'
    dispatch.apply_delivery_result(row, 'failed', now, now+timedelta(days=7), error='http_429', retry_after=600)
    assert row.status == 'pending' and row.next_attempt_at >= now+timedelta(seconds=600)
    assert push_service.provider_retry_after(SimpleNamespace(headers={'Retry-After':'600'})) == 600


@pytest.mark.asyncio
async def test_current_finance_audience_checks_request_exists(monkeypatch):
    db = SimpleNamespace(get=AsyncMock(return_value=None))
    job = SimpleNamespace(key='dispatch:advance:70:722:paid', user_ids=[20])
    assert await push_audience.restrict_business_audience(db, job) == set()


@pytest.mark.asyncio
async def test_old_oa_retry_without_session_binding_never_resends(monkeypatch):
    oa = fixtures.oa
    monkeypatch.setattr(oa, '_current_recipient', AsyncMock(return_value=({22},'oa.test',{})))
    monkeypatch.setattr(oa.notification_templates, 'render', AsyncMock(return_value='new letter'))
    monkeypatch.setattr(oa, 'PushService', lambda *a: pytest.fail('legacy unbound delivery must never send'))
    event = SimpleNamespace(key='new_letter:23:203', payload={'employee_id':203,'site_id':1,'text_key':'oa.test',
        'url':'/automation/letters/23','_delivery':{'remaining':[7], 'sent':[6], 'stale':[]}})
    state, _ = await oa._deliver_one(fixtures.FakeDb(), event)
    assert state == 'sent' and event.payload['_delivery']['stale'] == [7]
