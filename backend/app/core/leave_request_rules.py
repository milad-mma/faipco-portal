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


def compute_hourly_duration(start_hour_compact: int, end_hour_compact: int, overnight: bool = False) -> int:
    """
    ورودی: ساعت شروع و پایان به فرمت فشرده (HHMM).
    اختلاف آن‌ها را به همان فرمت فشرده برمی‌گرداند - مثلاً StartHour=1000،
    EndHour=1200 -> Duration=200 (یعنی ۲ ساعت و ۰۰ دقیقه). پایان قبل یا برابر شروع خطا می‌دهد،
    مگر overnight=True (شیفت شب، مثل کاراوب: ۲۳۰۰ تا ۱۰۰ -> ۲۰۰).
    """
    diff_minutes = compact_time_to_minutes(end_hour_compact) - compact_time_to_minutes(start_hour_compact)
    if overnight and diff_minutes < 0:
        diff_minutes += 24 * 60
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


# ---------- بازه‌ی شیفت روز (محدودیت مرخصی ساعتی و مجوز خروج؛ docs/leave-requests.md) ----------

MIN_WORKING_SHIFT_MINUTES = 30  # شیفتی که کوتاه‌تر باشد (مثل پنجشنبه‌ی دفتر مرکزی: ۷:۳۰ تا ۷:۳۱) روز کاری نیست


def shift_window(start: int | None, end: int | None, added_day, kasr: int | None = None) -> dict | None:
    """
    ساعت شروع/پایان شیفت یک روز (HHMM، مثل ستون‌های Shifts کاراوب) را به بازه‌ی قابل مقایسه تبدیل می‌کند.
    خروجی: {"start": ..., "end": ..., "crosses_midnight": bool, "off_day": False} که end برای شیفت شب (AddedDay)
    به‌صورت +۲۴۰۰ است (مثل کاراوب)؛ اگر کسر شیفت صفر یا بازه کمتر از ۳۰ دقیقه باشد {"off_day": True}؛
    اگر ساعت‌ها خالی باشند None (بدون محدودیت).
    """
    if kasr is not None and int(kasr) == 0:
        return {"off_day": True}
    if start is None or end is None:
        return None
    start, end = int(start), int(end)
    crosses = bool(added_day) or end < start
    end_ext = end + 2400 if crosses else end
    if compact_time_to_minutes(end_ext) - compact_time_to_minutes(start) < MIN_WORKING_SHIFT_MINUTES:
        return {"off_day": True}
    return {"start": start, "end": end_ext, "crosses_midnight": crosses, "off_day": False}


def _fmt(compact: int) -> str:
    compact = compact % 2400
    return f"{compact // 100:02d}:{compact % 100:02d}"


def window_label(window: dict) -> str:
    """متن «ساعت کاری شما در این روز: ۰۶:۳۰ تا ۱۴:۳۰» (شیفت شب: «… تا ۰۲:۳۰ بامداد روز بعد»)."""
    tail = " بامداد روز بعد" if window.get("crosses_midnight") else ""
    return f"ساعت کاری شما در این روز: {_fmt(window['start'])} تا {_fmt(window['end'])}{tail}"


def _on_shift_axis(window: dict, compact: int) -> int:
    """ساعت وارد‌شده (۰ تا ۲۳۵۹) را روی محور شیفت می‌برد: در شیفت شب، ساعت‌های قبل از شروع شیفت (بامداد) +۲۴۰۰ می‌شوند."""
    if window.get("crosses_midnight") and compact < window["start"]:
        return compact + 2400
    return compact


def crosses_midnight(window: dict | None, start_hour: int, end_hour: int) -> bool:
    """آیا این بازه‌ی ساعتی در شیفت شبِ این روز از ۰۰:۰۰ عبور می‌کند (مثل ۲۳:۰۰ تا ۰۱:۰۰)؟"""
    return bool(window and window.get("crosses_midnight")) and end_hour < start_hour


def kara_day_offset(window: dict | None, start_hour: int) -> int:
    """
    روز تقویمی ثبت در کاراوب نسبت به تاریخ شیفت: درخواست/خروجی که از بعد از نیمه‌شبِ شیفت شب شروع می‌شود (مثلاً ۰۱:۰۰ یا
    مجوز خروج ۰۳:۰۰) با تاریخ روز بعد ثبت می‌شود، چون تردد دستگاه هم همان تاریخ را دارد. خروجی ۰ یا ۱.
    """
    if not window or not window.get("crosses_midnight"):
        return 0
    return 1 if start_hour < window["start"] else 0


def validate_hourly_in_shift(window: dict | None, start_hour: int, end_hour: int) -> None:
    """
    مرخصی ساعتی فقط داخل ساعت رسمی شیفت همان روز. window=None یعنی شیفتی پیدا نشد (بدون محدودیت).
    شیفت شب: ساعت‌های بعد از نیمه‌شب تا پایان شیفت هم مجازند و یک درخواست می‌تواند از ۰۰:۰۰ عبور کند (مثل کاراوب:
    یک ردیف ۲۳۰۰ تا ۱۰۰ با مدت ۲۰۰). بعد از پایان رسمی شیفت باید «مجوز خروج» ثبت شود.
    """
    if window is None:
        return
    if window.get("off_day"):
        raise LeaveRequestRulesError("این روز طبق شیفت شما روز کاری نیست")
    if end_hour == start_hour or (end_hour < start_hour and not window.get("crosses_midnight")):
        raise LeaveRequestRulesError("ساعت پایان باید بعد از ساعت شروع باشد")
    s, e = _on_shift_axis(window, start_hour), _on_shift_axis(window, end_hour)
    if e <= s or s < window["start"] or e > window["end"]:
        tail = " برای بعد از پایان شیفت «مجوز خروج» ثبت کنید." if e > window["end"] else ""
        raise LeaveRequestRulesError(f"ساعت مرخصی باید داخل ساعت کاری همان روز باشد. {window_label(window)}.{tail}")


def validate_exit_after_shift(window: dict | None, exit_hour: int) -> None:
    """
    مجوز خروج: ساعت خروج باید از پایان شیفت همان روز به بعد باشد (روز غیرکاری یا شیفت نامعلوم: بدون محدودیت).
    شیفت شب: پایان در بامداد روز بعد است، پس خروج مجاز از پایان شیفت تا قبل از شروع شیفت بعدی است.
    """
    if window is None or window.get("off_day"):
        return
    end = window["end"]
    if window.get("crosses_midnight"):
        ok = (end - 2400) <= exit_hour < window["start"]
    else:
        ok = exit_hour >= end
    if not ok:
        raise LeaveRequestRulesError(
            f"ساعت خروج باید از پایان شیفت همان روز ({_fmt(end)}) به بعد باشد. {window_label(window)}"
        )


def validate_forgotten_punch_time(window: dict | None, prev_window: dict | None, punch_hour: int) -> None:
    """
    تردد فراموش‌شده نباید قبل از شروع شیفت همان روز باشد؛ پایان شیفت مهم نیست (ممکن است اضافه‌کار مانده باشد) — دستور کاربر.
    بدون محدودیت: شیفت نامعلوم، روز غیرکاری (کار در روز تعطیل)، و ساعت‌های بامدادِ ادامه‌ی شیفت شبِ روز قبل (قبل از شروع
    شیفت امروز، مثلاً خروج ۰۶:۳۰ بعد از شبکاری).
    """
    if window is None or window.get("off_day"):
        return
    if prev_window and prev_window.get("crosses_midnight") and punch_hour < window["start"]:
        return
    if punch_hour < window["start"]:
        raise LeaveRequestRulesError(
            f"ساعت تردد نمی‌تواند قبل از شروع شیفت شما در این روز ({_fmt(window['start'])}) باشد"
        )


# ---------- انتقال تأییدکننده (ترک کار / تغییر تنظیمات؛ docs/leave-requests.md) ----------

ACCEPT_CODE_CANCELLED = 22  # ابطال‌شده در کاراوب


def needs_reassign(row: dict, *, inactive: set[int], only_from: set[int] | None = None) -> bool:
    """
    درخواست کاراوب باید به تأییدکننده‌ی دیگری منتقل شود؟ فقط درخواستِ بدون تصمیم و ابطال‌نشده که تأییدکننده‌ی فعلی‌اش
    در only_from است (تغییر تنظیمات / ترک کار مشخص) یا — بدون only_from — ترک کار کرده است.
    """
    if row.get("IsFinalApproved") is not None or row.get("AcceptCode") == ACCEPT_CODE_CANCELLED:
        return False
    cur = row.get("CurEmpNo")
    if cur is None:
        return False
    cur = int(cur)
    return cur in only_from if only_from is not None else cur in inactive


def reassign_stage(row: dict, *, forgotten_cards: set, moved_ids: set[int] | None, hr_codes: set[int]) -> str:
    """
    مرحله‌ی درخواست: "hr" (تردد فراموش‌شده‌ای که سرپرست تأیید و به منابع انسانی ارجاع داده) یا "supervisor".
    با جدول ارجاع (moved_ids) از روی ردیف WF_MoveUp؛ بدون آن، تأییدکننده‌ی فعلی = مسئول منابع انسانی (فعلی/قبلی).
    """
    if row.get("CardNo") not in forgotten_cards:
        return "supervisor"
    if moved_ids is not None:
        return "hr" if row.get("RequestId") in moved_ids else "supervisor"
    return "hr" if row.get("CurEmpNo") in hr_codes else "supervisor"


def valid_target(current: int, target: int | None, requester: int | None, inactive: set[int]) -> int | None:
    """تأییدکننده‌ی جدید معتبر است اگر پیدا شده، فعال، غیر از فعلی و غیر از خودِ درخواست‌دهنده باشد؛ وگرنه None."""
    if target is None or target == current or target == requester or target in inactive:
        return None
    return target


# ---------- جانشین مدیران کاراوب (WF_Substitute؛ docs/leave-requests.md «جانشین») ----------


def can_act_on(approver: int, current: int | None, requester: int | None, substitutes: dict[int, int]) -> bool:
    """
    آیا approver می‌تواند روی درخواستی که پیش current است تصمیم بگیرد؟ خودِ current، یا جانشین فعالِ او
    (substitutes: مدیر → جانشین). هیچ‌کس — حتی به‌عنوان جانشین — درخواست خودش را تأیید نمی‌کند (مثل کاراوب، ۳۰۶).
    """
    if current is None:
        return False
    if approver == current:
        return True
    return substitutes.get(current) == approver and requester != approver


def managers_of_substitute(substitute: int, substitutes: dict[int, int]) -> set[int]:
    """مدیرانی که این فرد الان جانشین فعالشان است."""
    return {manager for manager, sub in substitutes.items() if sub == substitute and manager != substitute}
