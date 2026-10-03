"""تست منطق خالص گفتگوی انتقادات و پیشنهادات: محدوده‌ی پاسخ، آشکار شدن هویت و نشانگر «پاسخ جدید»."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest


def _svc():
    pytest.importorskip("sqlalchemy")
    from app.services.feedback_service import FeedbackService

    return FeedbackService


def test_can_reply_scope():
    svc = _svc()
    assert svc._can_reply_to(None, None)  # مجوز سراسری: همه، حتی فرستنده‌ی بدون پرسنل
    assert svc._can_reply_to({1, 2}, 2)
    assert not svc._can_reply_to({1, 2}, 3)
    assert not svc._can_reply_to({1}, None)  # مجوز سایتی ولی فرستنده سایت ندارد
    assert not svc._can_reply_to(set(), 1)


def test_reveal_sender_rules():
    svc = _svc()
    anon = SimpleNamespace(is_anonymous_requested=True, contains_profanity=False)
    flagged = SimpleNamespace(is_anonymous_requested=True, contains_profanity=True)
    public = SimpleNamespace(is_anonymous_requested=False, contains_profanity=False)
    reviewer = SimpleNamespace(is_superuser=False)
    admin = SimpleNamespace(is_superuser=True)
    assert not svc._reveal_sender(anon, reviewer, True)
    assert svc._reveal_sender(anon, admin, True)
    assert svc._reveal_sender(flagged, reviewer, True)
    assert not svc._reveal_sender(flagged, reviewer, False)  # قابلیت خاموش
    assert svc._reveal_sender(public, reviewer, False)


def test_my_item_new_reply_flag():
    svc = _svc()
    from app.models.feedback import FeedbackCategory

    now = datetime.now(timezone.utc)
    fb = SimpleNamespace(
        id=1, category=FeedbackCategory.comment, title="t", message="m", is_anonymous_requested=True,
        status="answered", created_at=now, sender_seen_at=None,
    )
    assert svc._my_item_out(fb, (1, now, False), now).has_new_reply
    fb.sender_seen_at = now + timedelta(seconds=1)
    assert not svc._my_item_out(fb, (1, now, False), now).has_new_reply
    assert not svc._my_item_out(fb, (1, now, True), None).has_new_reply  # فقط پاسخ خود فرستنده
    assert svc._my_item_out(fb, None, None).reply_count == 0
