"""تست‌های بخش‌های خالص امنیت ورود: پله‌های قفل، IP معاف، اعتبارسنجی تنظیمات و کپچا."""
import pytest

pytest.importorskip("pydantic")

from app.schemas.login_security import LoginSecuritySettings  # noqa: E402


def _tier():
    pytest.importorskip("sqlalchemy")
    from app.core.rate_limit import _tier_seconds

    return _tier_seconds


def test_default_tiers_match_previous_behavior():
    _tier_seconds = _tier()
    assert [_tier_seconds(n) for n in (3, 6, 9, 12, 30)] == [60, 300, 3600, 3600, 3600]


def test_custom_tiers():
    _tier_seconds = _tier()
    secs = [120, 600]
    assert _tier_seconds(5, 5, secs) == 120
    assert _tier_seconds(10, 5, secs) == 600
    assert _tier_seconds(50, 5, secs) == 600  # بعد از آخرین پله همان می‌ماند


def test_settings_defaults_and_validation():
    cfg = LoginSecuritySettings()
    assert cfg.attempts_per_tier == 3 and cfg.lock_minutes == [1, 5, 60]
    cfg = LoginSecuritySettings(exempt_ips=[" 192.168.1.10 ", "10.0.0.0/8", "10.0.0.0/8", ""])
    assert cfg.exempt_ips == ["192.168.1.10/32", "10.0.0.0/8"]
    with pytest.raises(Exception):
        LoginSecuritySettings(exempt_ips=["not-an-ip"])
    with pytest.raises(Exception):
        LoginSecuritySettings(lock_minutes=[0])


def test_exempt_ip_matching():
    pytest.importorskip("sqlalchemy")
    import app.services.login_security_service as svc
    cfg = LoginSecuritySettings(exempt_ips=["192.168.1.0/24"])
    assert svc.is_exempt_ip(cfg, "192.168.1.55")
    assert svc.is_exempt_ip(cfg, "::ffff:192.168.1.55")
    assert not svc.is_exempt_ip(cfg, "192.168.2.1")
    assert not svc.is_exempt_ip(cfg, "unknown")
    assert not svc.ip_limit_applies(cfg, "192.168.1.55")
    assert svc.ip_limit_applies(cfg, "5.6.7.8")
    assert not svc.ip_limit_applies(LoginSecuritySettings(ip_limit_enabled=False), "5.6.7.8")


def test_describe_key():
    pytest.importorskip("sqlalchemy")
    import app.services.login_security_service as svc
    assert svc.describe_key("ip:1.2.3.4") == ("ip", "1.2.3.4")
    assert svc.describe_key("reset-password:1.2.3.4") == ("reset", "1.2.3.4")
    assert svc.describe_key("41350") == ("identifier", "41350")


def test_captcha_image_and_answer():
    pytest.importorskip("PIL")
    from app.core.captcha import CAPTCHA_LENGTH, random_answer, render_captcha_png

    answer = random_answer()
    assert len(answer) == CAPTCHA_LENGTH and set(answer) <= set("23456789")
    assert render_captcha_png(answer)[:8] == b"\x89PNG\r\n\x1a\n"
