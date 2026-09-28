"""تست منطق خالص اپ اندروید: مشکلات/سلامت گوشی، زمان رویداد و تشخیص اندروید."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest


def _svc():
    pytest.importorskip("sqlalchemy")
    import app.services.mobile_app_service as svc

    return svc


def _device(**kw):
    now = datetime.now(timezone.utc)
    base = dict(
        revoked_at=None, perm_fine_location=True, perm_background_location=True, location_enabled=True,
        geofences_registered=True, status_reported_at=now, app_version_code=5, perm_notifications=True,
        battery_unrestricted=True,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_healthy_device():
    svc = _svc()
    from app.schemas.mobile import MobileAppSettings

    issues = svc.device_issues(_device(), MobileAppSettings(), has_sites=True)
    assert issues == [] and svc.is_healthy(issues)


def test_blocking_and_warning_issues():
    svc = _svc()
    from app.schemas.mobile import MobileAppSettings

    cfg = MobileAppSettings(min_version_code=6, status_stale_days=3)
    old = datetime.now(timezone.utc) - timedelta(days=4)
    issues = svc.device_issues(
        _device(perm_background_location=False, status_reported_at=old, perm_notifications=False), cfg, has_sites=True
    )
    assert issues == ["no_background_location", "stale", "outdated", "no_notifications"]
    assert not svc.is_healthy(issues)
    # فقط هشدار (اعلان/باتری) → هنوز سالم
    warn = svc.device_issues(_device(perm_notifications=False, battery_unrestricted=False), MobileAppSettings(), True)
    assert svc.is_healthy(warn)
    # بدون سایت دارای GPS، ثبت نشدن محدوده مشکل نیست
    assert "no_geofences" not in svc.device_issues(_device(geofences_registered=False), MobileAppSettings(), False)
    assert svc.device_issues(_device(revoked_at=datetime.now(timezone.utc)), MobileAppSettings(), True) == ["revoked"]


def test_event_time_clamped():
    svc = _svc()
    received = datetime(2026, 9, 28, 8, 0, tzinfo=timezone.utc)
    ok = received - timedelta(minutes=30)
    assert svc._event_time(int(ok.timestamp() * 1000), received) == ok
    future = received + timedelta(hours=1)
    assert svc._event_time(int(future.timestamp() * 1000), received) == received
    ancient = received - timedelta(days=10)
    assert svc._event_time(int(ancient.timestamp() * 1000), received) == received


def test_android_user_agent():
    from app.core.request_context import is_android_user_agent

    assert is_android_user_agent("Mozilla/5.0 (Linux; Android 13; SM-A536E) AppleWebKit/537.36 Chrome/120 Mobile")
    assert not is_android_user_agent("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)")
    assert not is_android_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120")
    assert not is_android_user_agent(None)
