"""
تبدیل «سال/ماه شمسی» به بازه UTC معادل — برای فیلترکردن گزارش‌ها بر اساس
تقویم شمسی (مثلاً «فقط این ماه»). محاسبه با توجه به منطقه زمانی ایران
(Asia/Tehran) انجام می‌شود، نه UTC خام — وگرنه چند ساعت اول/آخر هر ماه
شمسی ممکن است به‌اشتباه به ماه قبل/بعد نسبت داده شوند.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import jdatetime

_IRAN_TZ = ZoneInfo("Asia/Tehran")


def get_current_jalali_year_month() -> tuple[int, int]:
    today = jdatetime.date.fromgregorian(date=datetime.now(_IRAN_TZ).date())
    return today.year, today.month


def get_current_jalali_date() -> tuple[int, int, int]:
    """(سال, ماه, روز) شمسی — بر اساس منطقه زمانی ایران، نه ساعت خام سرور
    (که معمولاً UTC است، مخصوصاً روی VPS های تازه‌نصب)."""
    today = jdatetime.date.fromgregorian(date=datetime.now(_IRAN_TZ).date())
    return today.year, today.month, today.day


def jalali_month_range_utc(year: int, month: int) -> tuple[datetime, datetime]:
    """بازه [شروع، پایان) این ماه شمسی را به‌صورت datetime آگاه از منطقه زمانی UTC برمی‌گرداند."""
    start_jalali = jdatetime.date(year, month, 1)
    start_gregorian = start_jalali.togregorian()
    start_local = datetime(
        start_gregorian.year, start_gregorian.month, start_gregorian.day, tzinfo=_IRAN_TZ
    )

    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    end_jalali = jdatetime.date(next_year, next_month, 1)
    end_gregorian = end_jalali.togregorian()
    end_local = datetime(end_gregorian.year, end_gregorian.month, end_gregorian.day, tzinfo=_IRAN_TZ)

    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def jalali_days_in_month(year: int, month: int) -> int:
    """
    تعداد واقعی روزهای یک ماه شمسی — ۳۱ روز برای ماه‌های ۱ تا ۶، ۳۰ روز
    برای ۷ تا ۱۱، و ۲۹ یا ۳۰ روز برای اسفند بسته به کبیسه بودن سال. به‌جای
    هاردکدکردن این ارقام، از خودِ jdatetime (که این محاسبه، شامل تشخیص
    سال کبیسه شمسی، را به‌درستی انجام می‌دهد) استفاده می‌شود — با پیداکردن
    اولین روز ماه بعد، تبدیل به میلادی، کم‌کردن یک روز (با timedelta
    استاندارد پایتون، نه jdatetime، برای اطمینان کامل از صحت محاسبه)، و
    تبدیل دوباره به شمسی.
    """
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    first_day_next_month_gregorian = jdatetime.date(next_year, next_month, 1).togregorian()
    last_day_this_month_gregorian = first_day_next_month_gregorian - timedelta(days=1)
    last_day_this_month_jalali = jdatetime.date.fromgregorian(date=last_day_this_month_gregorian)
    return last_day_this_month_jalali.day


def jalali_year_month_to_yyyymmdd_range(year: int, month: int) -> tuple[int, int]:
    """
    (FromDate, ToDate) به فرمت عددی فشرده YYYYMMDD (مثلاً 14050501) — برای
    «گزارش تردد ماهانه» (فرمت رایج ستون تاریخ در نرم‌افزارهای حضور و غیاب
    دستگاهی، طبق AttendanceMapping هر Site).
    """
    days_in_month = jalali_days_in_month(year, month)
    from_date = year * 10000 + month * 100 + 1
    to_date = year * 10000 + month * 100 + days_in_month
    return from_date, to_date
