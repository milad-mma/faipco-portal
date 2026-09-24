"""
توابع تقویم شمسی: تاریخ جاری شمسی، تبدیل ماه/سال شمسی به بازه UTC معادل
(برای فیلتر گزارش‌ها)، تعداد روزهای ماه، بازه عددی YYYYMMDD و نام روز هفته.
محاسبه با توجه به منطقه زمانی ایران
(Asia/Tehran) انجام می‌شود، نه UTC خام — وگرنه چند ساعت اول/آخر هر ماه
شمسی ممکن است به‌اشتباه به ماه قبل/بعد نسبت داده شوند.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import jdatetime

_IRAN_TZ = ZoneInfo("Asia/Tehran")  # منطقه زمانی مبنای همه محاسبات تقویمی


def get_current_jalali_year_month() -> tuple[int, int]:
    """خروجی: (سال, ماه) شمسی امروز بر اساس منطقه زمانی ایران."""
    today = jdatetime.date.fromgregorian(date=datetime.now(_IRAN_TZ).date())
    return today.year, today.month


def get_current_jalali_date() -> tuple[int, int, int]:
    """خروجی: (سال, ماه, روز) شمسی امروز بر اساس منطقه زمانی ایران، نه ساعت خام سرور (معمولاً UTC)."""
    today = jdatetime.date.fromgregorian(date=datetime.now(_IRAN_TZ).date())
    return today.year, today.month, today.day


def jalali_month_range_utc(year: int, month: int) -> tuple[datetime, datetime]:
    """ورودی: سال و ماه شمسی. خروجی: بازه [شروع، پایان) آن ماه به‌صورت datetime آگاه از منطقه زمانی UTC."""
    # شروع: نیمه‌شب اول ماه به وقت تهران
    start_jalali = jdatetime.date(year, month, 1)
    start_gregorian = start_jalali.togregorian()
    start_local = datetime(
        start_gregorian.year, start_gregorian.month, start_gregorian.day, tzinfo=_IRAN_TZ
    )

    # پایان: نیمه‌شب اول ماه بعد (اسفند → فروردین سال بعد)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    end_jalali = jdatetime.date(next_year, next_month, 1)
    end_gregorian = end_jalali.togregorian()
    end_local = datetime(end_gregorian.year, end_gregorian.month, end_gregorian.day, tzinfo=_IRAN_TZ)

    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def jalali_year_range_utc(year: int) -> tuple[datetime, datetime]:
    """
    ورودی: سال شمسی. بازه [شروع، پایان) یک سال شمسی کامل (فروردین تا پایان اسفند) را
    به‌صورت datetime آگاه از منطقه زمانی UTC برمی‌گرداند - برای گزارش‌های
    «میانگین یک‌سال اخیر» استفاده می‌شود.
    """
    start, _ = jalali_month_range_utc(year, 1)
    _, end = jalali_month_range_utc(year, 12)
    return start, end


def jalali_days_in_month(year: int, month: int) -> int:
    """
    ورودی: سال و ماه شمسی. خروجی: تعداد روزهای آن ماه (۳۱، ۳۰، یا ۲۹/۳۰ برای اسفند بسته به کبیسه).
    روش: اولین روز ماه بعد به میلادی تبدیل، یک روز با timedelta کم و دوباره به شمسی تبدیل می‌شود.
    """
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    first_day_next_month_gregorian = jdatetime.date(next_year, next_month, 1).togregorian()
    last_day_this_month_gregorian = first_day_next_month_gregorian - timedelta(days=1)  # روز آخر همین ماه به میلادی
    last_day_this_month_jalali = jdatetime.date.fromgregorian(date=last_day_this_month_gregorian)
    return last_day_this_month_jalali.day


def jalali_year_month_to_yyyymmdd_range(year: int, month: int) -> tuple[int, int]:
    """
    ورودی: سال و ماه شمسی. خروجی: (FromDate, ToDate) به فرمت عددی فشرده YYYYMMDD (مثلاً 14050501) — برای
    «گزارش تردد ماهانه» (فرمت رایج ستون تاریخ در نرم‌افزارهای حضور و غیاب
    دستگاهی، طبق AttendanceMapping هر Site).
    """
    days_in_month = jalali_days_in_month(year, month)
    from_date = year * 10000 + month * 100 + 1
    to_date = year * 10000 + month * 100 + days_in_month
    return from_date, to_date


# نام روزهای هفته شمسی، از شنبه تا جمعه — کلید، همان مقدار weekday()
# استاندارد پایتون روی معادل میلادی است (دوشنبه=۰ ... یکشنبه=۶)، نه یک
# قرارداد اختصاصی jdatetime؛ این‌طور از هرگونه ابهام در قرارداد شماره‌گذاری
# روز هفته خودِ jdatetime پرهیز می‌شود.
_PERSIAN_WEEKDAY_NAMES = {
    0: "دوشنبه",
    1: "سه‌شنبه",
    2: "چهارشنبه",
    3: "پنجشنبه",
    4: "جمعه",
    5: "شنبه",
    6: "یکشنبه",
}


def jalali_weekday_name(year: int, month: int, day: int) -> str:
    """
    ورودی: سال، ماه و روز شمسی. خروجی: نام فارسی روز هفته.
    به‌صورت تقویمی محاسبه می‌شود (نه از دیتابیس)، پس برای سایت بدون نگاشت تقویم/تعطیلات هم درست است.
    """
    gregorian_date = jdatetime.date(year, month, day).togregorian()
    return _PERSIAN_WEEKDAY_NAMES[gregorian_date.weekday()]
