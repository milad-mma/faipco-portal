"""
تبدیل «سال/ماه شمسی» به بازه UTC معادل — برای فیلترکردن گزارش‌ها بر اساس
تقویم شمسی (مثلاً «فقط این ماه»). محاسبه با توجه به منطقه زمانی ایران
(Asia/Tehran) انجام می‌شود، نه UTC خام — وگرنه چند ساعت اول/آخر هر ماه
شمسی ممکن است به‌اشتباه به ماه قبل/بعد نسبت داده شوند.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import jdatetime

_IRAN_TZ = ZoneInfo("Asia/Tehran")


def get_current_jalali_year_month() -> tuple[int, int]:
    today = jdatetime.date.fromgregorian(date=datetime.now(_IRAN_TZ).date())
    return today.year, today.month


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
