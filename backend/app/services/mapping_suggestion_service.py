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
    "national_code": {
        _HIGH: [
            "national_code", "nationalcode", "melli_code", "mellicode", "code_melli", "codemelli",
            "کد_ملی", "کدملی",
        ],
        _MEDIUM: ["national", "melli", "ملی"],
    },
    "first_name": {
        _HIGH: ["first_name", "firstname", "fname", "نام_کوچک", "نامکوچک"],
        _MEDIUM: ["نام"],
    },
    "last_name": {
        _HIGH: [
            "last_name", "lastname", "lname", "family_name", "familyname", "surname",
            "نام_خانوادگی", "نامخانوادگی", "فامیل",
        ],
        _MEDIUM: [],
    },
    "birth_date": {
        _HIGH: ["birth_date", "birthdate", "date_of_birth", "dateofbirth", "تاریخ_تولد", "تاریختولد"],
        _MEDIUM: ["dob", "birth", "تولد"],
    },
    "is_active": {
        _HIGH: ["is_active", "isactive", "active_status", "activestatus", "فعال_غیرفعال"],
        _MEDIUM: ["active", "enabled", "status", "فعال", "وضعیت"],
    },
    "department": {
        _HIGH: [
            "department_code", "departmentcode", "dept_code", "deptcode", "کد_واحد", "کدواحد",
            "کد_دپارتمان",
        ],
        _MEDIUM: ["department", "dept", "واحد", "دپارتمان", "بخش"],
    },
    "position": {
        _HIGH: ["position_code", "positioncode", "job_title", "jobtitle", "کد_سمت", "کدسمت"],
        _MEDIUM: ["position", "title", "سمت", "پست", "شغل"],
    },
    "photo_emp_no": {
        # همان کلیدواژه‌های personnel_code - ستون کد پرسنلی داخل جدول عکس معمولاً همان نام‌ها را دارد
        _HIGH: [
            "emp_no", "empno", "emp_code", "empcode", "personnel_code", "personnelcode",
            "prs_code", "prscode", "کد_پرسنلی", "کدپرسنلی",
        ],
        _MEDIUM: ["emp", "personnel", "prs", "پرسنل", "کد"],
    },
    "photo_thumbnail": {
        _HIGH: ["thumbnail", "photo_thumb", "photothumb", "عکس_پرسنلی", "عکسپرسنلی"],
        _MEDIUM: ["photo", "image", "picture", "pic", "عکس", "تصویر"],
    },
    # ⚠️ این دو مفهوم عمداً «عمومی» تعریف شده‌اند - چون هم برای جدول مرجع
    # دپارتمان و هم جدول مرجع سمت شغلی (و هر جدول مرجع مشابه دیگری در
    # آینده) به‌طور یکسان قابل‌استفاده‌اند؛ نیازی به یک مفهوم جداگانه
    # به‌ازای هر جدول مرجع نیست.
    "lookup_id": {
        _HIGH: ["id", "code", "pk", "شناسه", "کد"],
        _MEDIUM: [],
    },
    "lookup_name": {
        _HIGH: ["name", "title", "نام", "عنوان"],
        _MEDIUM: [],
    },
    "calendar_year": {
        _HIGH: ["year", "shamsi_year", "jalali_year", "سال"],
        _MEDIUM: [],
    },
    "calendar_month": {
        _HIGH: ["month", "shamsi_month", "jalali_month", "ماه"],
        _MEDIUM: [],
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


# ==============================================================================
# مرحله سوم — پیشنهاد بر اساس نمونه داده واقعی (برای مفاهیمی که نام
# ستون به‌تنهایی کافی نبوده است)
# ==============================================================================


def _to_int_or_none(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _looks_like_persian_date(values: list) -> bool:
    """آیا همه مقادیر عدد ۸ رقمی با ماه/روز معتبر (شبیه ۱۴۰۵۰۵۲۴) هستند؟"""
    numbers = [n for n in (_to_int_or_none(v) for v in values) if n is not None]
    if not numbers:
        return False
    for n in numbers:
        if not (13000101 <= n <= 14501231):
            return False
        month, day = (n // 100) % 100, n % 100
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return False
    return True


def _looks_like_compressed_time(values: list) -> bool:
    """آیا همه مقادیر عدد فشرده ساعت معتبر (مثل 618 برای 06:18) هستند؟"""
    numbers = [n for n in (_to_int_or_none(v) for v in values) if n is not None]
    if not numbers:
        return False
    for n in numbers:
        s = str(n)
        if len(s) <= 2:
            hour, minute = 0, n
        elif len(s) == 3:
            hour, minute = int(s[0]), int(s[1:3])
        elif len(s) == 4:
            hour, minute = int(s[0:2]), int(s[2:4])
        else:
            return False
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return False
    return True


def _looks_like_email(values: list) -> bool:
    strings = [str(v).strip() for v in values if v is not None and str(v).strip()]
    if not strings:
        return False
    return all("@" in s and "." in s.rsplit("@", 1)[-1] for s in strings)


def _looks_like_mobile(values: list) -> bool:
    strings = [re.sub(r"\D", "", str(v)) for v in values if v is not None and str(v).strip()]
    strings = [s for s in strings if s]
    if not strings:
        return False
    return all(len(s) == 11 and s.startswith("0") for s in strings)


# ⚠️ عمداً "personnel_code" اینجا نیست - یک عدد صحیح ساده (مثلاً کد
# پرسنلی) از روی مقادیرش به‌تنهایی از هر ستون عددی دیگری (مثلاً سن،
# کد واحد سازمانی) قابل‌تشخیص نیست؛ هیچ الگوی قابل‌اتکایی برای آن وجود
# ندارد، پس تلاش برای حدس‌زدنش از روی نمونه فقط ریسک پیشنهاد غلط دارد.
_PATTERN_DETECTORS = {
    "email": _looks_like_email,
    "mobile": _looks_like_mobile,
    "date": _looks_like_persian_date,
    "time": _looks_like_compressed_time,
    "enter_date": _looks_like_persian_date,
    "exit_date": _looks_like_persian_date,
    "enter_time": _looks_like_compressed_time,
    "exit_time": _looks_like_compressed_time,
}

_MAX_COLUMNS_TO_SAMPLE = 30  # جلوگیری از تعداد کوئری بی‌رویه برای جدول‌های خیلی پهن


def suggest_column_from_samples(columns_with_samples: dict[str, list], concept: str) -> dict | None:
    """
    columns_with_samples: {نام ستون خام: [چند مقدار نمونه واقعی]}. برای
    مفاهیمی که تشخیص از روی نام ستون کافی نبوده، بررسی می‌کند آیا مقادیر
    واقعی یکی از ستون‌ها با الگوی مورد انتظار همان مفهوم هم‌خوانی دارد.
    """
    detector = _PATTERN_DETECTORS.get(concept)
    if detector is None:
        return None
    for column, values in columns_with_samples.items():
        non_null = [v for v in values if v is not None]
        if not non_null:
            continue
        if detector(non_null):
            return {"column": column, "confidence": _HIGH, "matched_keyword": None, "source": "نمونه داده"}
    return None


async def suggest_mapping_with_samples(adapter, table_name: str, column_names: list[str], concepts: list[str]) -> dict:
    """
    ترکیب مرحله دوم (نام ستون) و سوم (نمونه داده واقعی): ابتدا برای هر
    مفهوم، پیشنهاد بر اساس نام امتحان می‌شود؛ فقط برای مفاهیمی که هیچ
    پیشنهادی از روی نام پیدا نشد (و اصلاً الگوی نمونه‌ای برایشان تعریف
    شده - نه "personnel_code")، چند مقدار واقعی از ستون‌های هنوز
    بلاتکلیف خوانده و الگوی داده بررسی می‌شود.

    adapter: یک نمونه از BaseSiteAdapter، از قبل متصل‌شده به دیتابیس این
    سایت (نگاه کنید به app/services/schema_discovery_service.py برای
    نحوه ساختنش).
    """
    name_based = suggest_mapping(column_names, concepts)
    missing_concepts = [c for c in concepts if name_based[c] is None and c in _PATTERN_DETECTORS]
    if not missing_concepts:
        return name_based

    # فقط ستون‌هایی که هنوز برای هیچ مفهومی پیشنهاد نشده‌اند را نمونه‌گیری کن
    already_suggested_columns = {s["column"] for s in name_based.values() if s is not None}
    candidate_columns = [c for c in column_names if c not in already_suggested_columns][:_MAX_COLUMNS_TO_SAMPLE]

    samples: dict[str, list] = {}
    for column in candidate_columns:
        try:
            samples[column] = await adapter.sample_column_values(table_name, column, limit=5)
        except Exception:  # noqa: BLE001 - خطای یک ستون نباید کل فرایند پیشنهاد را متوقف کند
            samples[column] = []

    result = dict(name_based)
    for concept in missing_concepts:
        result[concept] = suggest_column_from_samples(samples, concept)
    return result
