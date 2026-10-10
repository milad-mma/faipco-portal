"""تست قواعد تشخیص «مشکل از کجاست» گزارش خطاها، با نمونه‌های واقعی همین پرتال (error_diagnosis.py)."""
from app.services.error_diagnosis import diagnose, needs_action


def _d(**item):
    stats = item.pop("stats", None)
    return diagnose(item, stats)


def test_single_user_network_drop_is_users_internet():
    d = _d(kind="client", category="network", message="ERR_NETWORK: Network Error", last_request="صفحه /notices",
           stats={"distinct_ips_window": 1})
    assert d["key"] == "user_network" and not needs_action(d)


def test_many_users_network_drop_is_server():
    d = _d(kind="client", category="network", message="ECONNABORTED: timeout", stats={"distinct_ips_window": 5})
    assert d["key"] == "server_network" and d["level"] == "critical" and needs_action(d)


def test_value_too_long_is_kara_data():
    msg = ("خطای پیش‌بینی‌نشده در PUT /api/v1/insurance/me — DBAPIError: StringDataRightTruncationError: "
           "value too long for type character varying(11)")
    d = _d(kind="error", category="insurance", source="faipco.http", message=msg, last_user_label="225735")
    assert d["key"] == "kara_data" and d["subject"] == "225735" and needs_action(d)


def test_invalid_column_is_kara_config():
    d = _d(kind="error", category="kara", source="app.services.monthly_attendance_service",
           message="ProgrammingError (207, b\"Invalid column name 'BranchCode'.\")")
    assert d["key"] == "kara_config"


def test_white_screen_is_portal_bug():
    d = _d(kind="client", category="frontend_crash", message="Minified React error #31", last_user_label="222624")
    assert d["key"] == "portal_bug" and d["level"] == "critical"


def test_chunk_error_is_transient():
    d = _d(kind="client", category="frontend_crash", message="Failed to fetch dynamically imported module")
    assert d["key"] == "transient" and not needs_action(d)


def test_slow_kara_route_vs_transient_vs_repeated():
    kara = _d(kind="slow", category="slow", source="GET /api/v1/monthly-attendance/report", message="درخواست کند")
    assert kara["key"] == "kara_slow"
    once = _d(kind="slow", category="slow", source="GET /api/v1/notices/me", message="درخواست کند",
              stats={"occurrences_24h": 1})
    assert once["key"] == "transient" and not needs_action(once)
    many = _d(kind="slow", category="slow", source="GET /api/v1/notices/me", message="درخواست کند",
              stats={"occurrences_24h": 9})
    assert many["key"] == "server_slow"


def test_unhandled_server_error_is_portal_bug_and_unknown_falls_back():
    d = _d(kind="error", category="server", source="faipco.http", message="KeyError: 'x'")
    assert d["key"] == "portal_bug"
    u = _d(kind="error", category="server", source="app.something", message="weird thing")
    assert u["key"] == "unknown" and needs_action(u)


def test_hint_is_kept_in_action_text():
    d = _d(kind="error", category="server", source="app.x", message="weird", hint="راهنمای نمونه")
    assert d["action"].startswith("راهنمای نمونه") and "پشتیبانی" in d["action"]
