"""
منطق تشخیص «آیا الان وقت اجرای بکاپ زمان‌بندی‌شده است؟» به‌صورت توابع خالص
(Pure Functions)، مستقل از دیتابیس و Scheduler و قابل‌تست.

به‌جای Cron Trigger مستقیم، یک تیک ثابت و کوتاه در Scheduler هر بار is_backup_due
را با تنظیمات فعلی دیتابیس صدا می‌زند؛ چون سرویس با چند Worker مستقل اجرا
می‌شود، این روش باعث می‌شود همه Workerها بدون نیاز به Reschedule به نتیجه
یکسان برسند (همان الگوی Sync Engine در app/core/scheduler.py).

منطقه زمانی: schedule_hour/schedule_minute به وقت محلی Asia/Tehran تفسیر
می‌شوند، ولی last_run_at در دیتابیس همیشه UTC است؛ توابع این ماژول تبدیل را
انجام می‌دهند.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

_TEHRAN_TZ = ZoneInfo("Asia/Tehran")  # منطقه زمانی تفسیر ساعت/دقیقه زمان‌بندی


def _most_recent_daily_occurrence(now_tehran: datetime, hour: int, minute: int) -> datetime:
    """
    ورودی: زمان فعلی به وقت تهران و ساعت/دقیقه زمان‌بندی روزانه.
    خروجی: آخرین لحظه (تا الان) که hour:minute امروز یا دیروز رخ داده، به وقت تهران.
    """
    candidate = now_tehran.replace(hour=hour, minute=minute, second=0, microsecond=0)
    # اگر ساعت امروز هنوز نرسیده، همان ساعتِ دیروز ملاک است
    if candidate > now_tehran:
        candidate -= timedelta(days=1)
    return candidate


def _most_recent_weekly_occurrence(now_tehran: datetime, weekday: int, hour: int, minute: int) -> datetime:
    """
    ورودی: زمان فعلی به وقت تهران، روز هفته و ساعت/دقیقه زمان‌بندی هفتگی.
    خروجی: آخرین لحظه‌ای که «روز weekday، ساعت hour:minute» رخ داده، به وقت تهران.
    قرارداد weekday: ۰=دوشنبه ... ۶=یکشنبه (همان datetime.weekday() پایتون، مطابق مقدار Frontend).
    """
    days_since_target = (now_tehran.weekday() - weekday) % 7  # چند روز از آخرین weekday گذشته
    candidate_date = now_tehran - timedelta(days=days_since_target)
    candidate = candidate_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    # اگر امروز همان روز است ولی ساعتش نرسیده، هفته قبل ملاک است
    if candidate > now_tehran:
        candidate -= timedelta(days=7)
    return candidate


def _most_recent_interval_occurrence(now_tehran: datetime, interval_hours: int) -> datetime:
    """
    ورودی: زمان فعلی به وقت تهران و فاصله اجرا بر حسب ساعت.
    خروجی: آخرین نقطه از یک شبکه زمانی ثابت که از نیمه‌شب امروز (تهران) هر interval_hours ساعت تکرار می‌شود.
    بنابراین اجراها دقیقاً روی مرز این شبکه‌اند و به مدت‌زمان اجرای قبلی وابسته نیستند.
    """
    midnight = now_tehran.replace(hour=0, minute=0, second=0, microsecond=0)
    hours_since_midnight = (now_tehran - midnight).total_seconds() / 3600
    slots_passed = int(hours_since_midnight // interval_hours)  # تعداد بازه‌های کامل سپری‌شده از نیمه‌شب
    return midnight + timedelta(hours=slots_passed * interval_hours)


def is_backup_due(
    *,
    schedule_enabled: bool,
    schedule_type: str,
    schedule_hour: int,
    schedule_minute: int,
    schedule_weekday: int | None,
    schedule_interval_hours: int | None,
    last_run_at: datetime | None,
    now_utc: datetime | None = None,
) -> bool:
    """
    ورودی: تنظیمات زمان‌بندی بکاپ (نوع daily/weekly/interval، ساعت، روز هفته، فاصله) و زمان آخرین اجرا (UTC).
    خروجی: True اگر آخرین موعد زمان‌بندی‌شده بعد از آخرین اجرا باشد، یعنی الان باید بکاپ گرفته شود.
    now_utc اختیاری است (پیش‌فرض: همین لحظه) و در تست‌ها برای نتیجه قطعی پاس داده می‌شود.
    """
    if not schedule_enabled:
        return False

    now_utc = now_utc or datetime.now(timezone.utc)
    now_tehran = now_utc.astimezone(_TEHRAN_TZ)

    # محاسبه آخرین موعد اجرا بر اساس نوع زمان‌بندی؛ تنظیمات ناقص یا نوع ناشناخته یعنی اجرا نشود
    if schedule_type == "interval":
        if not schedule_interval_hours:
            return False
        due_at_tehran = _most_recent_interval_occurrence(now_tehran, schedule_interval_hours)
    elif schedule_type == "daily":
        due_at_tehran = _most_recent_daily_occurrence(now_tehran, schedule_hour, schedule_minute)
    elif schedule_type == "weekly":
        if schedule_weekday is None:
            return False
        due_at_tehran = _most_recent_weekly_occurrence(now_tehran, schedule_weekday, schedule_hour, schedule_minute)
    else:
        return False

    due_at_utc = due_at_tehran.astimezone(timezone.utc)
    # اگر هیچ اجرای قبلی ثبت نشده، بلافاصله موعد است
    if last_run_at is None:
        return True
    return last_run_at < due_at_utc
