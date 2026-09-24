"""
تست‌های واحد برای app.core.backup_schedule_logic.is_backup_due: حالت غیرفعال،
زمان‌بندی روزانه، هفتگی و چندساعتی (شبکه زمانی ثابت) با now_utc قطعی.

اجرا: از پوشه backend/  ->  pytest tests/test_backup_schedule_logic.py -v
"""
from datetime import datetime, timedelta, timezone

from app.core.backup_schedule_logic import is_backup_due


def test_disabled_never_due():
    """زمان‌بندی غیرفعال هیچ‌وقت موعد نیست."""
    assert (
        is_backup_due(
            schedule_enabled=False,
            schedule_type="daily",
            schedule_hour=3,
            schedule_minute=0,
            schedule_weekday=None,
            schedule_interval_hours=None,
            last_run_at=None,
        )
        is False
    )


def test_daily_no_previous_run_is_due():
    """روزانه بدون اجرای قبلی: بلافاصله موعد است."""
    now_utc = datetime(2026, 9, 1, 22, 30, tzinfo=timezone.utc)  # ۰۲:۰۰ تهران روز بعد
    assert (
        is_backup_due(
            schedule_enabled=True,
            schedule_type="daily",
            schedule_hour=3,
            schedule_minute=0,
            schedule_weekday=None,
            schedule_interval_hours=None,
            last_run_at=None,
            now_utc=now_utc,
        )
        is True
    )


def test_daily_already_ran_recently_not_due():
    """روزانه با اجرای یک ساعت پیش (بعد از آخرین موعد): موعد نیست."""
    now_utc = datetime(2026, 9, 1, 22, 30, tzinfo=timezone.utc)
    last_run = now_utc - timedelta(hours=1)
    assert (
        is_backup_due(
            schedule_enabled=True,
            schedule_type="daily",
            schedule_hour=3,
            schedule_minute=0,
            schedule_weekday=None,
            schedule_interval_hours=None,
            last_run_at=last_run,
            now_utc=now_utc,
        )
        is False
    )


def test_daily_ran_yesterday_and_time_passed_today_is_due():
    """روزانه با اجرای دیروز و گذشتن ساعت امروز: موعد است."""
    now_utc = datetime(2026, 9, 2, 6, 30, tzinfo=timezone.utc)  # ۱۰:۰۰ تهران - بعد از ۳ صبح
    last_run = now_utc - timedelta(days=1, hours=1)
    assert (
        is_backup_due(
            schedule_enabled=True,
            schedule_type="daily",
            schedule_hour=3,
            schedule_minute=0,
            schedule_weekday=None,
            schedule_interval_hours=None,
            last_run_at=last_run,
            now_utc=now_utc,
        )
        is True
    )


def test_interval_not_enough_time_elapsed():
    """هر ۶ ساعت، اجرای قبلی در همان اسلات فعلی: موعد نیست."""
    now_utc = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    last_run = now_utc - timedelta(hours=3)
    assert (
        is_backup_due(
            schedule_enabled=True,
            schedule_type="interval",
            schedule_hour=0,
            schedule_minute=0,
            schedule_weekday=None,
            schedule_interval_hours=6,
            last_run_at=last_run,
            now_utc=now_utc,
        )
        is False
    )


def test_interval_enough_time_elapsed():
    """هر ۶ ساعت، اجرای قبلی قبل از شروع اسلات فعلی: موعد است."""
    now_utc = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    last_run = now_utc - timedelta(hours=7)
    assert (
        is_backup_due(
            schedule_enabled=True,
            schedule_type="interval",
            schedule_hour=0,
            schedule_minute=0,
            schedule_weekday=None,
            schedule_interval_hours=6,
            last_run_at=last_run,
            now_utc=now_utc,
        )
        is True
    )


def test_interval_no_previous_run_is_due():
    """چندساعتی بدون اجرای قبلی: موعد است."""
    assert (
        is_backup_due(
            schedule_enabled=True,
            schedule_type="interval",
            schedule_hour=0,
            schedule_minute=0,
            schedule_weekday=None,
            schedule_interval_hours=6,
            last_run_at=None,
        )
        is True
    )


def test_interval_missing_hours_never_due():
    """چندساعتی بدون مقدار schedule_interval_hours: هرگز موعد نیست."""
    assert (
        is_backup_due(
            schedule_enabled=True,
            schedule_type="interval",
            schedule_hour=0,
            schedule_minute=0,
            schedule_weekday=None,
            schedule_interval_hours=None,
            last_run_at=None,
        )
        is False
    )


def test_weekly_correct_day_no_previous_run_is_due():
    """هفتگی در روز درست بعد از ساعت تعیین‌شده و بدون اجرای قبلی: موعد است."""
    # 2026-09-01 سه‌شنبه است -> weekday()=1 (دوشنبه=۰)
    now_utc = datetime(2026, 9, 1, 6, 30, tzinfo=timezone.utc)  # ۱۰:۰۰ تهران
    assert (
        is_backup_due(
            schedule_enabled=True,
            schedule_type="weekly",
            schedule_hour=3,
            schedule_minute=0,
            schedule_weekday=1,
            schedule_interval_hours=None,
            last_run_at=None,
            now_utc=now_utc,
        )
        is True
    )


def test_weekly_wrong_day_not_due():
    """هفتگی برای دوشنبه، وقتی دوشنبه اجرا شده و امروز سه‌شنبه است: موعد نیست."""
    # 2026-09-01 سه‌شنبه (weekday=1) - زمان‌بندی برای دوشنبه (weekday=0)،
    # هنوز به دوشنبه بعدی نرسیده و از دوشنبه قبلی هم اجرا شده
    now_utc = datetime(2026, 9, 1, 6, 30, tzinfo=timezone.utc)
    last_monday_run = now_utc - timedelta(days=1, hours=1)  # دوشنبه (روز قبل) اجرا شده
    assert (
        is_backup_due(
            schedule_enabled=True,
            schedule_type="weekly",
            schedule_hour=3,
            schedule_minute=0,
            schedule_weekday=0,
            schedule_interval_hours=None,
            last_run_at=last_monday_run,
            now_utc=now_utc,
        )
        is False
    )


def test_weekly_missing_weekday_never_due():
    """هفتگی بدون schedule_weekday: هرگز موعد نیست."""
    assert (
        is_backup_due(
            schedule_enabled=True,
            schedule_type="weekly",
            schedule_hour=3,
            schedule_minute=0,
            schedule_weekday=None,
            schedule_interval_hours=None,
            last_run_at=None,
        )
        is False
    )


def test_interval_anchored_to_fixed_grid_not_completion_time():
    """
    زمان‌بندی «هر ۱ ساعت» روی شبکه ثابت: صرف‌نظر از لحظه تکمیل اجرای قبلی (۱۲:۰۹ یا ۱۲:۴۷)،
    موعد بعدی دقیقاً اسلات ثابت بعدی (۱۳:۰۰ تهران) است، نه «تکمیل + ۱ ساعت».
    """
    # ۱۲:۰۹ تهران = ۰۸:۳۹ UTC
    last_run_early_completion = datetime(2026, 9, 1, 8, 39, tzinfo=timezone.utc)
    # ۱۲:۴۷ تهران = ۰۹:۱۷ UTC - همان بازه ساعتی، لحظه تکمیل متفاوت
    last_run_late_completion = datetime(2026, 9, 1, 9, 17, tzinfo=timezone.utc)

    # قبل از رسیدن به ۱۳:۰۰ تهران (۰۹:۳۰ UTC) - هیچ‌کدام نباید due باشند
    check_before_boundary = datetime(2026, 9, 1, 9, 25, tzinfo=timezone.utc)  # = ۱۲:۵۵ تهران
    for last_run in (last_run_early_completion, last_run_late_completion):
        assert (
            is_backup_due(
                schedule_enabled=True,
                schedule_type="interval",
                schedule_hour=0,
                schedule_minute=0,
                schedule_weekday=None,
                schedule_interval_hours=1,
                last_run_at=last_run,
                now_utc=check_before_boundary,
            )
            is False
        )

    # بعد از رسیدن به ۱۳:۰۰ تهران - هر دو باید هم‌زمان due شوند (نه هرکدام
    # جدا بر اساس لحظه تکمیل خودش)
    check_after_boundary = datetime(2026, 9, 1, 9, 35, tzinfo=timezone.utc)  # = ۱۳:۰۵ تهران
    for last_run in (last_run_early_completion, last_run_late_completion):
        assert (
            is_backup_due(
                schedule_enabled=True,
                schedule_type="interval",
                schedule_hour=0,
                schedule_minute=0,
                schedule_weekday=None,
                schedule_interval_hours=1,
                last_run_at=last_run,
                now_utc=check_after_boundary,
            )
            is True
        )
