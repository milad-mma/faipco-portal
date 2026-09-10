"""
تست‌های واحد توابع خالص «درخواست مرخصی/ماموریت» - همه مقادیر انتظار
مستقیماً از داده واقعی WF_Requests (که کاربر برای تست ثبت و تأیید/رد
کرده بود) گرفته شده‌اند.
"""
from datetime import date

from app.core.leave_request_rules import (
    LeaveRequestRulesError,
    compact_time_to_minutes,
    compute_daily_duration,
    compute_hourly_duration,
    jalali_date_to_compact,
    minutes_to_compact_time,
)


def test_compact_time_to_minutes():
    assert compact_time_to_minutes(1236) == 12 * 60 + 36
    assert compact_time_to_minutes(800) == 8 * 60


def test_minutes_to_compact_time_round_trip():
    assert minutes_to_compact_time(compact_time_to_minutes(1236)) == 1236
    assert minutes_to_compact_time(60) == 100  # ۱ ساعت دقیقاً


def test_compute_hourly_duration_matches_real_data():
    """مقادیر مستقیماً از رکوردهای واقعی تست‌شده کاربر."""
    assert compute_hourly_duration(1236, 1336) == 100
    assert compute_hourly_duration(1200, 1400) == 200
    assert compute_hourly_duration(1000, 1200) == 200
    assert compute_hourly_duration(800, 1000) == 200


def test_compute_hourly_duration_rejects_non_positive_range():
    try:
        compute_hourly_duration(1200, 1200)
        assert False, "باید خطا می‌داد"
    except LeaveRequestRulesError:
        pass
    try:
        compute_hourly_duration(1300, 1200)
        assert False, "باید خطا می‌داد"
    except LeaveRequestRulesError:
        pass


def test_compute_daily_duration_matches_real_data():
    """مقادیر مستقیماً از رکوردهای واقعی تست‌شده کاربر."""
    assert compute_daily_duration(date(2026, 9, 13), date(2026, 9, 13)) == 1
    assert compute_daily_duration(date(2026, 9, 15), date(2026, 9, 16)) == 2


def test_compute_daily_duration_rejects_end_before_start():
    try:
        compute_daily_duration(date(2026, 9, 16), date(2026, 9, 15))
        assert False, "باید خطا می‌داد"
    except LeaveRequestRulesError:
        pass


def test_jalali_date_to_compact_matches_real_data():
    assert jalali_date_to_compact(1405, 6, 22) == 14050622
    assert jalali_date_to_compact(1405, 6, 19) == 14050619
