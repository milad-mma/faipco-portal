"""
توابع خالص «درخواست مرخصی/ماموریت» - طبق تحلیل داده واقعی WF_Requests:

    - نوع ساعتی: Duration = اختلاف StartHour/EndHour، به همان فرمت فشرده
      بدون جداکننده (HMM یا HHMM) که در گزارش تردد ماهانه هم استفاده
      می‌شود - مثلاً ۱۲:۳۶ تا ۱۳:۳۶ یعنی StartHour=1236، EndHour=1336،
      Duration=۱۰۰ (یعنی ۱ ساعت و ۰۰ دقیقه، به همان فرمت فشرده).
    - نوع روزانه: Duration = تعداد روز بین StartDate و EndDate (شامل
      خودِ دو سر بازه).
    - PersianStartDate = تاریخ شمسی StartDate، به فرمت عددی YYYYMMDD
      (مثلاً ۱۴۰۵/۰۶/۲۲ -> ۱۴۰۵۰۶۲۲).
"""
from __future__ import annotations

from datetime import date


class LeaveRequestRulesError(Exception):
    pass


def compact_time_to_minutes(compact: int) -> int:
    """۱۲۳۶ (یعنی ۱۲:۳۶) -> ۷۵۶ دقیقه؛ ۹۳۶ (یعنی ۹:۳۶) -> ۵۷۶ دقیقه."""
    hour, minute = divmod(compact, 100)
    return hour * 60 + minute


def minutes_to_compact_time(total_minutes: int) -> int:
    """۷۵۶ دقیقه -> ۱۲۳۶ (یعنی ۱۲:۳۶)."""
    hour, minute = divmod(total_minutes, 60)
    return hour * 100 + minute


def compute_hourly_duration(start_hour_compact: int, end_hour_compact: int) -> int:
    """
    اختلاف دو ساعتِ فرمت فشرده را به همان فرمت فشرده برمی‌گرداند - مثال
    تأییدشده با داده واقعی: StartHour=1000، EndHour=1200 -> Duration=200
    (یعنی ۲ ساعت و ۰۰ دقیقه).
    """
    diff_minutes = compact_time_to_minutes(end_hour_compact) - compact_time_to_minutes(start_hour_compact)
    if diff_minutes <= 0:
        raise LeaveRequestRulesError("ساعت پایان باید بعد از ساعت شروع باشد")
    return minutes_to_compact_time(diff_minutes)


def compute_daily_duration(start_date: date, end_date: date) -> int:
    """تعداد روز بین دو تاریخ، شامل خودِ دو سر بازه - مثال تأییدشده: همان روز -> ۱."""
    if end_date < start_date:
        raise LeaveRequestRulesError("تاریخ پایان باید بعد یا همان تاریخ شروع باشد")
    return (end_date - start_date).days + 1


def jalali_date_to_compact(jalali_year: int, jalali_month: int, jalali_day: int) -> int:
    """۱۴۰۵، ۶، ۲۲ -> ۱۴۰۵۰۶۲۲ (فرمت مشاهده‌شده در PersianStartDate داده واقعی)."""
    return jalali_year * 10000 + jalali_month * 100 + jalali_day
