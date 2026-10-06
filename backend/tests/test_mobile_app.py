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
    # فقط هشدار (باتری) → هنوز سالم؛ اعلان الزامی است (Migration 104)
    warn = svc.device_issues(_device(battery_unrestricted=False), MobileAppSettings(), True)
    assert svc.is_healthy(warn)
    assert not svc.is_healthy(svc.device_issues(_device(perm_notifications=False), MobileAppSettings(), True))
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


def _ev(**kw):
    from datetime import datetime, timezone

    base = dict(
        id="e1", transition="enter", site_id=1, latitude=35.0, longitude=51.0, accuracy=20.0, is_mock=False,
        occurred_at=int(datetime.now(timezone.utc).timestamp() * 1000),
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_geofence_event_rejection_rules():
    svc = _svc()
    from datetime import datetime, timedelta, timezone

    site = SimpleNamespace(gps_radius_meters=200)
    now = datetime.now(timezone.utc)
    assert svc._event_rejection(_ev(), site, 150.0, now) is None
    assert svc._event_rejection(_ev(), site, 219.0, now) is None  # شعاع ۲۰۰ + دقت ۲۰
    assert svc._event_rejection(_ev(), site, 221.0, now) == "out_of_range"
    assert svc._event_rejection(_ev(latitude=None), site, None, now) == "no_location"
    assert svc._event_rejection(_ev(is_mock=True), site, 10.0, now) == "mock"
    # خروج: بیرون حصار و حتی بدون مختصات پذیرفته می‌شود؛ از عمق داخل حصار رد می‌شود
    assert svc._event_rejection(_ev(transition="exit"), site, 900.0, now) is None
    assert svc._event_rejection(_ev(transition="exit", latitude=None), site, None, now) is None
    assert svc._event_rejection(_ev(transition="exit"), site, 10.0, now) == "out_of_range"
    # زمان: رویداد صف‌شده‌ی ۱۰ ساعته پذیرفته، ۳ روزه یا آینده رد
    old = int((now - timedelta(hours=10)).timestamp() * 1000)
    assert svc._event_rejection(_ev(occurred_at=old), site, 10.0, now) is None
    too_old = int((now - timedelta(days=3)).timestamp() * 1000)
    assert svc._event_rejection(_ev(occurred_at=too_old), site, 10.0, now) == "bad_time"
    future = int((now + timedelta(minutes=10)).timestamp() * 1000)
    assert svc._event_rejection(_ev(occurred_at=future), site, 10.0, now) == "bad_time"


def test_resolve_event_time_uses_device_stopwatch_not_clock():
    """زمان رویداد = زمان رسیدن به سرور منهای فاصله‌ی کرنومتر؛ ساعت دستکاری‌شده‌ی گوشی اثری ندارد."""
    svc = _svc()
    received = datetime(2026, 10, 6, 6, 0, tzinfo=timezone.utc)
    fake_clock = int((received - timedelta(hours=3)).timestamp() * 1000)  # ساعت گوشی ۳ ساعت عقب کشیده شده
    at, uncertain, valid = svc.resolve_event_time(fake_clock, 1_000_000, 7, 1_000_000 + 30 * 60_000, 7, received)
    assert at == received - timedelta(minutes=30) and not uncertain and valid
    # گوشی بین رویداد و ارسال خاموش/روشن شده ← ساعت گوشی، «نامطمئن»
    real = int((received - timedelta(minutes=10)).timestamp() * 1000)
    at, uncertain, valid = svc.resolve_event_time(real, 5_000_000, 7, 60_000, 8, received)
    assert at == received - timedelta(minutes=10) and uncertain and valid
    # اندروید ۶ (بدون شماره‌ی روشن شدن): کرنومتر عقب رفته ← نامطمئن
    _, uncertain, _ = svc.resolve_event_time(real, 5_000_000, None, 60_000, None, received)
    assert uncertain
    # اندروید ۶: فاصله‌ی ساعت گوشی با فاصله‌ی کرنومتر جور است ← همان روشن شدن، زمان دقیق
    now_wall = real + 10 * 60_000
    at, uncertain, _ = svc.resolve_event_time(real, 1_000_000, None, 1_000_000 + 10 * 60_000, None, received, now_wall)
    assert at == received - timedelta(minutes=10) and not uncertain
    # اندروید ۶ و گوشی خاموش/روشن شده (کرنومتر کمتر از فاصله‌ی واقعی) ← نامطمئن
    _, uncertain, _ = svc.resolve_event_time(real, 1_000_000, None, 1_000_000 + 60_000, None, received, now_wall)
    assert uncertain
    # عدد خیلی بزرگ (درخواست دستکاری‌شده) خطا نمی‌دهد، فقط نامعتبر است
    _, _, valid = svc.resolve_event_time(real, 0, 7, 10**13, 7, received)
    assert not valid
    # قدیمی‌تر از ۴۸ ساعت ← نامعتبر
    _, _, valid = svc.resolve_event_time(real, 0, 7, 49 * 3600_000, 7, received)
    assert not valid
    # نسخه‌ی قدیمی اپ (بدون کرنومتر) ← رفتار قبلی
    at, uncertain, valid = svc.resolve_event_time(real, None, None, None, None, received)
    assert at == received - timedelta(minutes=10) and not uncertain and valid
