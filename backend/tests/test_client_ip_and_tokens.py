"""تست‌های سخت‌سازی امنیتی (audit 2026-10-05): تشخیص IP کلاینت (C2)، ابطال توکن با iat (H2) و تشخیص کد کوتاه (C3)."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")  # ماژول‌های زیر به FastAPI/SQLAlchemy وابسته‌اند؛ در محیط بدون وابستگی رد می‌شود

from app.core.ip_allowlist import get_client_ip  # noqa: E402
from app.core.security import is_token_revoked_by_password_change  # noqa: E402


def _request(headers: dict | None = None, client_host: str | None = "127.0.0.1"):
    """شبیه‌ساز Request با هدرهای حروف‌کوچک (مثل Starlette) و client اختیاری."""
    lowered = {k.lower(): v for k, v in (headers or {}).items()}
    client = SimpleNamespace(host=client_host) if client_host else None
    return SimpleNamespace(headers=lowered, client=client)


def _patch_trusted(monkeypatch, *ips):
    import app.core.ip_allowlist as mod

    monkeypatch.setattr(mod, "_trusted_proxies", lambda: {"127.0.0.1", "::1", *ips})


def test_direct_client_behind_local_nginx(monkeypatch):
    _patch_trusted(monkeypatch)
    # کلاینت XFF جعلی می‌فرستد؛ Nginx محلی X-Real-IP را با IP اتصال جایگزین و IP اتصال را به XFF می‌افزاید
    req = _request({"X-Real-IP": "10.0.0.5", "X-Forwarded-For": "1.2.3.4, 10.0.0.5"})
    assert get_client_ip(req) == "10.0.0.5"
    req = _request({"X-Real-IP": "10.0.0.5", "X-Forwarded-For": "1.2.3.4"})
    assert get_client_ip(req) == "10.0.0.5"


def test_external_reverse_proxy_is_skipped(monkeypatch):
    _patch_trusted(monkeypatch, "203.0.113.9")
    # پراکسی خارجی معتبر → Nginx: X-Real-IP = پراکسی؛ XFF = «جعلی, کلاینت واقعی, پراکسی»
    req = _request({"X-Real-IP": "203.0.113.9", "X-Forwarded-For": "1.2.3.4, 5.6.7.8, 203.0.113.9"})
    assert get_client_ip(req) == "5.6.7.8"
    # بدون پراکسی خارجی تنظیم‌شده، همان IP پراکسی برمی‌گردد (نه مقدار جعلی کلاینت)
    _patch_trusted(monkeypatch)
    assert get_client_ip(req) == "203.0.113.9"


def test_forwarded_for_uses_last_untrusted(monkeypatch):
    _patch_trusted(monkeypatch)
    req = _request({"X-Forwarded-For": "1.2.3.4, 5.6.7.8 , 10.0.0.9"})
    assert get_client_ip(req) == "10.0.0.9"


def test_falls_back_to_client_host(monkeypatch):
    _patch_trusted(monkeypatch)
    assert get_client_ip(_request({}, "192.168.1.20")) == "192.168.1.20"
    assert get_client_ip(_request({"X-Forwarded-For": " , "}, "192.168.1.21")) == "192.168.1.21"


def test_unknown_without_client():
    assert get_client_ip(_request({}, None)) == "unknown"


def test_token_revocation_by_iat():
    changed = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    before = int((changed - timedelta(minutes=1)).timestamp())
    after = int((changed + timedelta(seconds=1)).timestamp())
    assert is_token_revoked_by_password_change({"iat": before}, changed) is True
    assert is_token_revoked_by_password_change({"iat": after}, changed) is False
    assert is_token_revoked_by_password_change({"iat": before}, None) is False
    # توکن قدیمی بدون iat تا انقضای طبیعی پذیرفته می‌شود؛ iat خراب رد می‌شود
    assert is_token_revoked_by_password_change({}, changed) is False
    assert is_token_revoked_by_password_change({"iat": "x"}, changed) is True
    # مقدار naive از دیتابیس UTC فرض می‌شود
    assert is_token_revoked_by_password_change({"iat": before}, changed.replace(tzinfo=None)) is True


def test_is_short_code():
    from app.services.password_reset_service import is_short_code

    assert is_short_code("123456") is True
    assert is_short_code("۱۲۳ ۴۵۶") is True  # ارقام فارسی و فاصله
    assert is_short_code("12345") is False
    assert is_short_code("abcdef") is False
    assert is_short_code("x" * 43) is False  # توکن طولانی لینک ایمیل
