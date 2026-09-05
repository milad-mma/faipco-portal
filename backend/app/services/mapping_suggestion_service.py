"""
سرویس «پیشنهاد نگاشت بر اساس نام ستون» - مرحله دوم از طرح سه‌مرحله‌ای
نگاشت داینامیک (کشف ساختار -> پیشنهاد بر اساس نام -> پیشنهاد بر اساس
نمونه داده واقعی).

⚠️ این سرویس هیچ تصمیمی «قطعی» نمی‌گیرد و هیچ داده‌ای نمی‌خواند/نمی‌نویسد
- فقط یک الگوریتم خالص (بدون I/O) است که روی نام ستون‌هایی که از قبل
کشف شده‌اند (مرحله اول) اجرا می‌شود. خروجی همیشه فقط «پیشنهاد» است؛
تأیید نهایی همیشه دستی و توسط مدیر در فرم Mapping انجام می‌شود.
"""
from __future__ import annotations

import re

_HIGH = "بالا"
_MEDIUM = "متوسط"

# هر مفهوم موردنیاز Mapping ها (EmployeeMapping/AttendanceMapping)، با دو
# سطح کلیدواژه: «بالا» (نام‌های رایج و اختصاصی، شانس تطبیق تصادفی کم) و
# «متوسط» (کلیدواژه‌های عمومی‌تر که ممکن است با ستون‌های نامرتبط هم
# تصادفاً هم‌خوانی داشته باشند).
FIELD_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "personnel_code": {
        _HIGH: [
            "emp_no", "empno", "emp_code", "empcode", "personnel_code", "personnelcode",
            "prs_code", "prscode", "کد_پرسنلی", "کدپرسنلی",
        ],
        _MEDIUM: ["emp", "personnel", "prs", "پرسنل", "کد"],
    },
    "email": {
        _HIGH: ["email", "e_mail", "ایمیل"],
        _MEDIUM: ["mail"],
    },
    "mobile": {
        _HIGH: ["mobile", "cell_phone", "cellphone", "موبایل"],
        _MEDIUM: ["phone", "tel", "cell", "همراه", "تلفن"],
    },
    "date": {
        _HIGH: ["attendance_date", "attendancedate", "log_date", "logdate", "تاریخ"],
        _MEDIUM: ["date", "tarikh", "day", "روز"],
    },
    "time": {
        _HIGH: ["attendance_time", "attendancetime", "log_time", "logtime", "ساعت"],
        _MEDIUM: ["time", "hour", "clock"],
    },
    "enter_date": {
        _HIGH: ["enter_date", "enterdate", "in_date", "indate", "تاریخ_ورود", "تاریخورود"],
        _MEDIUM: ["entry_date", "entrydate"],
    },
    "enter_time": {
        _HIGH: ["enter_time", "entertime", "in_time", "intime", "ساعت_ورود", "ساعتورود"],
        _MEDIUM: ["entry_time", "entrytime"],
    },
    "exit_date": {
        _HIGH: ["exit_date", "exitdate", "out_date", "outdate", "تاریخ_خروج", "تاریخخروج"],
        _MEDIUM: ["leave_date", "leavedate"],
    },
    "exit_time": {
        _HIGH: ["exit_time", "exittime", "out_time", "outtime", "ساعت_خروج", "ساعتخروج"],
        _MEDIUM: ["leave_time", "leavetime"],
    },
}


def _normalize(name: str) -> str:
    return re.sub(r"[_\s]+", "", name).strip().lower()


def suggest_column_for_field(column_names: list[str], concept: str) -> dict | None:
    """
    برای یک مفهوم مشخص (کلیدهای FIELD_KEYWORDS، مثلاً "personnel_code")،
    بین لیست نام ستون‌های خام یک جدول، بهترین ستون کاندید را پیشنهاد
    می‌دهد - یا None اگر هیچ‌کدام حتی با کلیدواژه‌های سطح «متوسط» هم‌خوانی
    نداشتند.
    """
    patterns = FIELD_KEYWORDS.get(concept)
    if not patterns:
        return None

    candidates: list[tuple[int, str, str, str]] = []
    for level in (_HIGH, _MEDIUM):
        for keyword in patterns[level]:
            normalized_keyword = _normalize(keyword)
            if not normalized_keyword:
                continue
            for column in column_names:
                normalized_column = _normalize(column)
                if not normalized_column:
                    continue
                if normalized_keyword == normalized_column:
                    candidates.append((0, level, column, keyword))
                elif normalized_keyword in normalized_column:
                    candidates.append((len(normalized_column) - len(normalized_keyword), level, column, keyword))
        if candidates:
            # اگر توی سطح «بالا» چیزی پیدا شد، دیگر سراغ «متوسط» نمی‌رویم
            break

    if not candidates:
        return None

    # اولویت با کمترین اختلاف طول - یعنی تطبیق دقیق‌تر/کم‌حاشیه‌تر
    candidates.sort(key=lambda c: c[0])
    _diff, best_level, best_column, best_keyword = candidates[0]
    return {"column": best_column, "confidence": best_level, "matched_keyword": best_keyword}


def suggest_mapping(column_names: list[str], concepts: list[str]) -> dict[str, dict | None]:
    """
    برای یک لیست از مفاهیم موردنیاز (مثلاً برای EmployeeMapping:
    ["personnel_code", "email", "mobile"])، برای هرکدام یک پیشنهاد (یا
    None اگر چیزی پیدا نشد) برمی‌گرداند.

    ⚠️ عمداً یک ستون می‌تواند برای چند مفهوم مختلف هم‌زمان پیشنهاد شود
    (مثلاً اگر دو مفهوم هر دو با یک ستون مبهم هم‌خوانی داشته باشند) -
    این تابع هیچ تلاشی برای حذف این‌گونه تداخل نمی‌کند؛ تشخیص و رفع آن
    هم به عهده مدیر (در همان فرم Mapping، با دیدن پیشنهادها) گذاشته
    شده است.
    """
    return {concept: suggest_column_for_field(column_names, concept) for concept in concepts}
