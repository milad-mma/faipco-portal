"""
تست‌های واحد برای app.core.backup_schedule_logic.is_backup_due.

اجرا: از پوشه backend/  ->  pytest tests/test_backup_schedule_logic.py -v
"""
from datetime import datetime, timedelta, timezone

from app.core.backup_schedule_logic import is_backup_due


def test_disabled_never_due():
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
