"""
منطق «آیا الان وقت اجرای بکاپ زمان‌بندی‌شده است؟» - کاملاً مستقل از
دیتابیس/Scheduler، فقط توابع خالص (Pure Functions) قابل‌تست.

⚠️ چرا یک Cron Trigger مستقیم استفاده نشد (برخلاف پیام تبریک تولد): چون
این سرویس با چند Worker جدا (uvicorn --workers) اجرا می‌شود و هر Worker
APScheduler مستقل خودش را دارد، وقتی Admin زمان‌بندی را از پنل تغییر
می‌دهد، فقط همان Worker ای که درخواست HTTP را گرفته Reschedule می‌شود -
Worker های دیگر با زمان‌بندی قدیمی می‌مانند تا Restart بعدی. به‌جای این،
دقیقاً همان الگوی اثبات‌شده Sync Engine (app/core/scheduler.py) دنبال
می‌شود: یک تیک ثابت و کوتاه (هر چند دقیقه)، که هر بار خودش از دیتابیس
می‌پرسد «طبق تنظیمات فعلی، وقتش رسیده یا نه» - هر Worker مستقل به یک
نتیجه یکسان می‌رسد، بدون نیاز به Reschedule کردن هیچ Job ای.

⚠️ منطقهٔ زمانی: schedule_hour/schedule_minute بر اساس ساعت محلی ایران
(Asia/Tehran) تفسیر می‌شوند - همان‌طور که کاربر پنل انتظار دارد (نه UTC)
- ولی last_run_at در دیتابیس همیشه UTC ذخیره می‌شود؛ همه محاسبات این
ماژول این تبدیل را به‌درستی انجام می‌دهند.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

_TEHRAN_TZ = ZoneInfo("Asia/Tehran")


def _most_recent_daily_occurrence(now_tehran: datetime, hour: int, minute: int) -> datetime:
    """آخرین لحظه‌ای (تا این لحظه) که ساعت hour:minute امروز یا دیروز رخ داده - به وقت تهران."""
    candidate = now_tehran.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate > now_tehran:
        candidate -= timedelta(days=1)
    return candidate


def _most_recent_weekly_occurrence(now_tehran: datetime, weekday: int, hour: int, minute: int) -> datetime:
    """
    آخرین لحظه‌ای که «روز هفته weekday، ساعت hour:minute» رخ داده - به وقت
    تهران. قرارداد weekday: ۰=دوشنبه ... ۶=یکشنبه (همان datetime.weekday()
    استاندارد پایتون، مطابق مقداری که Frontend می‌فرستد).
    """
    days_since_target = (now_tehran.weekday() - weekday) % 7
    candidate_date = now_tehran - timedelta(days=days_since_target)
    candidate = candidate_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate > now_tehran:
        candidate -= timedelta(days=7)
    return candidate


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
    now_utc اختیاری است (پیش‌فرض: همین لحظه) - فقط برای قابل‌تست‌بودن
    قطعی (بدون وابستگی به ساعت واقعی سیستم) در تست‌های واحد پاس داده می‌شود.
    """
    if not schedule_enabled:
        return False

    now_utc = now_utc or datetime.now(timezone.utc)

    if schedule_type == "interval":
        if not schedule_interval_hours:
            return False
        if last_run_at is None:
            return True
        elapsed_hours = (now_utc - last_run_at).total_seconds() / 3600
        return elapsed_hours >= schedule_interval_hours

    now_tehran = now_utc.astimezone(_TEHRAN_TZ)

    if schedule_type == "daily":
        due_at_tehran = _most_recent_daily_occurrence(now_tehran, schedule_hour, schedule_minute)
    elif schedule_type == "weekly":
        if schedule_weekday is None:
            return False
        due_at_tehran = _most_recent_weekly_occurrence(now_tehran, schedule_weekday, schedule_hour, schedule_minute)
    else:
        return False

    due_at_utc = due_at_tehran.astimezone(timezone.utc)
    if last_run_at is None:
        return True
    return last_run_at < due_at_utc
