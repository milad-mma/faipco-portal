"""
توابع خالص (بدون دیتابیس) برای محاسبه فیلدهای عددی یک ردیف WF_Requests:

    - نوع ساعتی: Duration = اختلاف StartHour/EndHour، به همان فرمت فشرده
      بدون جداکننده (HMM یا HHMM) که در گزارش تردد ماهانه هم استفاده
      می‌شود - مثلاً ۱۲:۳۶ تا ۱۳:۳۶ یعنی StartHour=1236، EndHour=1336،
      Duration=۱۰۰ (یعنی ۱ ساعت و ۰۰ دقیقه، به همان فرمت فشرده).
    - نوع روزانه: Duration = تعداد روز بین StartDate و EndDate (شامل
      خودِ دو سر بازه).
    - PersianStartDate = تاریخ شمسی StartDate، به فرمت عددی YYYYMMDD
      (مثلاً ۱۴۰۵/۰۶/۲۲ -> ۱۴۰۵۰۶۲۲).

شامل: خطای LeaveRequestRulesError، تبدیل بین فرمت فشرده ساعت و دقیقه،
محاسبه مدت ساعتی/روزانه و تبدیل تاریخ شمسی به عدد فشرده.
"""
from __future__ import annotations

from datetime import date


class LeaveRequestRulesError(Exception):
    """خطای اعتبارسنجی قواعد درخواست (مثلاً ساعت پایان قبل از شروع)؛ پیام آن قابل نمایش به کاربر است."""
    pass


def compact_time_to_minutes(compact: int) -> int:
    """ساعت فشرده (HHMM) را به تعداد دقیقه از ابتدای روز تبدیل می‌کند: ۱۲۳۶ (یعنی ۱۲:۳۶) -> ۷۵۶ دقیقه؛ ۹۳۶ (یعنی ۹:۳۶) -> ۵۷۶ دقیقه."""
    hour, minute = divmod(compact, 100)  # دو رقم آخر دقیقه، بقیه ساعت
    return hour * 60 + minute


def minutes_to_compact_time(total_minutes: int) -> int:
    """تعداد دقیقه را به ساعت فشرده (HHMM) برمی‌گرداند: ۷۵۶ دقیقه -> ۱۲۳۶ (یعنی ۱۲:۳۶)."""
    hour, minute = divmod(total_minutes, 60)  # ساعت کامل و دقیقه باقی‌مانده
    return hour * 100 + minute


def compute_hourly_duration(start_hour_compact: int, end_hour_compact: int) -> int:
    """
    ورودی: ساعت شروع و پایان به فرمت فشرده (HHMM).
    اختلاف آن‌ها را به همان فرمت فشرده برمی‌گرداند - مثلاً StartHour=1000،
    EndHour=1200 -> Duration=200 (یعنی ۲ ساعت و ۰۰ دقیقه). پایان قبل یا برابر شروع خطا می‌دهد.
    """
    diff_minutes = compact_time_to_minutes(end_hour_compact) - compact_time_to_minutes(start_hour_compact)
    # بازه صفر یا منفی معتبر نیست
    if diff_minutes <= 0:
        raise LeaveRequestRulesError("ساعت پایان باید بعد از ساعت شروع باشد")
    return minutes_to_compact_time(diff_minutes)


def compute_daily_duration(start_date: date, end_date: date) -> int:
    """ورودی: تاریخ شروع و پایان. تعداد روز بین دو تاریخ را شامل خودِ دو سر بازه برمی‌گرداند (همان روز -> ۱)؛ پایان قبل از شروع خطا می‌دهد."""
    # پایان باید همان روز یا بعد از شروع باشد
    if end_date < start_date:
        raise LeaveRequestRulesError("تاریخ پایان باید بعد یا همان تاریخ شروع باشد")
    return (end_date - start_date).days + 1


def jalali_date_to_compact(jalali_year: int, jalali_month: int, jalali_day: int) -> int:
    """سال/ماه/روز شمسی را به عدد فشرده YYYYMMDD تبدیل می‌کند: ۱۴۰۵، ۶، ۲۲ -> ۱۴۰۵۰۶۲۲ (فرمت ستون PersianStartDate)."""
    return jalali_year * 10000 + jalali_month * 100 + jalali_day
