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


# ---------- بازه‌ی شیفت (داده‌ی واقعی Shifts کاراوب: ۱۴ روزکار، ۱۹ شبکار، ۲۲ دفتر مرکزی) ----------
from app.core.leave_request_rules import (  # noqa: E402
    crosses_midnight,
    kara_day_offset,
    shift_window,
    validate_exit_after_shift,
    validate_hourly_in_shift,
    window_label,
)


def _raises(fn, *args):
    try:
        fn(*args)
    except LeaveRequestRulesError as e:
        return str(e)
    raise AssertionError("expected LeaveRequestRulesError")


def test_shift_window_day_night_and_off():
    assert shift_window(630, 1430, 0, 800) == {"start": 630, "end": 1430, "crosses_midnight": False, "off_day": False}
    assert shift_window(1830, 230, 1, 800) == {"start": 1830, "end": 2630, "crosses_midnight": True, "off_day": False}
    assert shift_window(730, 731, 0, 0) == {"off_day": True}  # پنجشنبه‌ی دفتر مرکزی (کسر صفر)
    assert shift_window(730, 731, 0, None) == {"off_day": True}  # بازه‌ی یک‌دقیقه‌ای
    assert shift_window(None, None, 0, None) is None
    assert window_label(shift_window(1830, 230, 1)) == "ساعت کاری شما در این روز: 18:30 تا 02:30 بامداد روز بعد"


def test_hourly_inside_day_shift():
    w = shift_window(630, 1430, 0)
    validate_hourly_in_shift(w, 630, 1430)
    validate_hourly_in_shift(w, 1000, 1200)
    assert "داخل ساعت کاری" in _raises(validate_hourly_in_shift, w, 600, 800)
    assert "داخل ساعت کاری" in _raises(validate_hourly_in_shift, w, 1400, 1500)
    validate_hourly_in_shift(None, 100, 300)  # شیفت نامعلوم: بدون محدودیت


def test_hourly_night_shift_after_midnight():
    w = shift_window(1830, 230, 1)
    validate_hourly_in_shift(w, 1900, 2300)
    validate_hourly_in_shift(w, 0, 230)
    validate_hourly_in_shift(w, 100, 200)
    validate_hourly_in_shift(w, 2300, 100)  # عبور از نیمه‌شب در یک درخواست (مثل درخواست ۲۶۲ کاراوب)
    validate_hourly_in_shift(w, 1830, 230)
    assert "مجوز خروج" in _raises(validate_hourly_in_shift, w, 2300, 300)  # بعد از پایان رسمی
    assert "داخل ساعت کاری" in _raises(validate_hourly_in_shift, w, 200, 300)
    assert "بعد از ساعت شروع" in _raises(validate_hourly_in_shift, shift_window(630, 1430, 0), 1200, 1000)
    assert "داخل ساعت کاری" in _raises(validate_hourly_in_shift, w, 1700, 1900)


def test_hourly_off_day_blocked():
    assert _raises(validate_hourly_in_shift, {"off_day": True}, 800, 900) == "این روز طبق شیفت شما روز کاری نیست"


def test_exit_after_shift():
    day = shift_window(630, 1430, 0)
    validate_exit_after_shift(day, 1430)
    validate_exit_after_shift(day, 2000)
    assert "پایان شیفت" in _raises(validate_exit_after_shift, day, 1400)
    night = shift_window(1830, 230, 1)
    validate_exit_after_shift(night, 230)
    validate_exit_after_shift(night, 900)
    assert "پایان شیفت" in _raises(validate_exit_after_shift, night, 2300)
    validate_exit_after_shift({"off_day": True}, 1000)
    validate_exit_after_shift(None, 1000)


def test_overnight_duration_and_kara_day():
    assert compute_hourly_duration(2300, 100, overnight=True) == 200  # همان Duration درخواست ۲۶۲
    _raises(compute_hourly_duration, 2300, 100)
    night, day = shift_window(1830, 230, 1), shift_window(630, 1430, 0)
    assert crosses_midnight(night, 2300, 100) and not crosses_midnight(night, 100, 200)
    assert not crosses_midnight(day, 2300, 100)
    assert kara_day_offset(night, 2300) == 0
    assert kara_day_offset(night, 100) == 1  # بامداد = تاریخ تقویمی روز بعد
    assert kara_day_offset(night, 300) == 1  # مجوز خروج بعد از ۰۲:۳۰
    assert kara_day_offset(day, 100) == 0
    assert kara_day_offset(None, 100) == 0


def test_forgotten_punch_not_before_shift_start():
    from app.core.leave_request_rules import validate_forgotten_punch_time as v

    day, night = shift_window(630, 1430, 0), shift_window(1830, 230, 1)
    v(day, day, 630)
    v(day, day, 1830)  # بعد از پایان شیفت (اضافه‌کار) مجاز
    assert "06:30" in _raises(v, day, day, 615)
    assert "18:30" in _raises(v, night, day, 1800)
    v(night, night, 630)  # خروج بامداد بعد از شبکاری روز قبل
    v(day, night, 600)  # بعد از شبکاری، امروز روزکار
    v({"off_day": True}, day, 900)
    v(None, None, 300)
