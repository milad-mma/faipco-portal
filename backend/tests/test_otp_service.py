"""تست‌های بخش‌های خالص سرویس کد تأیید (OTP) تغییر رمز/موبایل."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services import otp_service


def test_generate_code_is_six_digits():
    for _ in range(200):
        code = otp_service.generate_code()
        assert len(code) == 6 and code.isdigit() and code[0] != "0"


def test_normalize_code_persian_digits_and_spaces():
    assert otp_service.normalize_code(" ۱۲۳ ۴۵۶ ") == "123456"
    assert otp_service.normalize_code(None) == ""


def test_options_otp_required():
    assert not otp_service.OtpOptions().otp_required
    assert otp_service.OtpOptions(channels={"sms": "0912***6789"}).otp_required


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _FakeDb:
    """Session ساختگی: execute همیشه همان ردیف را برمی‌گرداند و commit فقط شمرده می‌شود."""

    def __init__(self, row):
        self.row = row
        self.commits = 0

    async def execute(self, _stmt):
        return _FakeResult(self.row)

    async def commit(self):
        self.commits += 1


def _row(code="123456", destination="09120000000", attempts=0):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        code_hash=otp_service._hash(code),
        destination=destination,
        attempts=attempts,
        used_at=None,
        created_at=now,
        expires_at=now + timedelta(minutes=5),
    )


class _Any:
    """جایگزین ستون‌ها/select در محیط تست (SQLAlchemy واقعی نصب نیست): هر عملگر/متد خودش را برمی‌گرداند."""

    def __getattr__(self, _name):
        return self

    def __call__(self, *_a, **_k):
        return self

    __eq__ = __gt__ = __lt__ = lambda self, _o: self  # noqa: E731
    __hash__ = object.__hash__


@pytest.fixture(autouse=True)
def _fake_query_builders(monkeypatch):
    monkeypatch.setattr(otp_service, "select", _Any())
    monkeypatch.setattr(otp_service, "VerificationCode", _Any())


def _verify(db, code, destination=None):
    return asyncio.run(
        otp_service.verify_and_consume(
            db, SimpleNamespace(id=1), purpose="mobile", code=code, destination=destination
        )
    )


def test_verify_correct_code_consumes_without_commit():
    db = _FakeDb(_row())
    _verify(db, "۱۲۳۴۵۶", destination="09120000000")
    assert db.row.used_at is not None
    assert db.commits == 0  # commit با فراخواننده، همراه تغییر اصلی


def test_verify_wrong_code_counts_and_invalidates():
    db = _FakeDb(_row(attempts=otp_service.MAX_ATTEMPTS - 2))
    try:
        _verify(db, "000000")
        raise AssertionError("expected OtpError")
    except otp_service.OtpError:
        pass
    assert db.row.used_at is None and db.commits == 1
    try:
        _verify(db, "000000")
        raise AssertionError("expected OtpError")
    except otp_service.OtpError:
        pass
    assert db.row.used_at is not None  # پس از سقف تلاش باطل شد


def test_verify_other_destination_rejected():
    db = _FakeDb(_row(destination="09120000000"))
    try:
        _verify(db, "123456", destination="09129999999")
        raise AssertionError("expected OtpError")
    except otp_service.OtpError:
        pass
    assert db.row.used_at is None


def test_verify_missing_code_or_row():
    try:
        _verify(_FakeDb(_row()), "")
        raise AssertionError("expected OtpError")
    except otp_service.OtpError:
        pass
    try:
        _verify(_FakeDb(None), "123456")
        raise AssertionError("expected OtpError")
    except otp_service.OtpError:
        pass


def test_mandatory_password_change_skips_otp():
    first_login = SimpleNamespace(must_change_password=False, employee_id=5, has_custom_password=False)
    flagged = SimpleNamespace(must_change_password=True, employee_id=None, has_custom_password=True)
    normal = SimpleNamespace(must_change_password=False, employee_id=5, has_custom_password=True)
    assert otp_service.is_mandatory_password_change(first_login)
    assert otp_service.is_mandatory_password_change(flagged)
    assert not otp_service.is_mandatory_password_change(normal)
    opts = asyncio.run(otp_service.password_options(None, first_login))
    assert not opts.otp_required
