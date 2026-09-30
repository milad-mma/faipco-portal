"""
قواعد ماژول «مشخصات خانوادگی» (حق تاهل / حق اولاد) — بدون وابستگی به دیتابیس تا قابل تست باشد.

اصل طراحی: پرتال فقط اطلاعات را جمع می‌کند؛ هیچ شرط قانونی در کد ثابت نیست. همه‌ی شرط‌ها
(سن پسر، شرط تحصیل/ازکارافتادگی، توقف دختر با ازدواج/اشتغال، وضعیت کارمند زن، حداقل سابقه بیمه،
سقف تعداد فرزند، مدارک لازم و دوره تمدید آن‌ها و اجباری/اختیاری/مخفی بودن هر فیلد) در تنظیمات
پنل منابع انسانی ذخیره می‌شوند و این ماژول فقط آن تنظیمات را روی داده‌ها اعمال می‌کند.

محتوا:
- ثابت‌ها و تعریف فیلدها/مدارک
- DEFAULT_SETTINGS و sanitize_settings (پاک‌سازی تنظیمات ذخیره‌شده/ورودی)
- validate_payload: اعتبارسنجی و نرمال‌سازی فرم کارمند بر اساس تنظیمات فیلدها
- required_documents: مدارکی که برای یک فرم (با توجه به پاسخ‌ها) لازم است
- evaluate: محاسبه‌ی شمول حق تاهل و تعداد فرزند واجد شرایط در یک تاریخ مبنا
- warnings: هشدارها (نزدیک شدن پسر به سن تعیین‌شده، انقضای مدرک)

تاریخ‌ها همه شمسی و به قالب «YYYY/MM/DD» هستند و به‌صورت تاپل (سال، ماه، روز) مقایسه می‌شوند.
"""
from __future__ import annotations

import re

# ---------- ثابت‌ها ----------

GENDER_MALE = 1
GENDER_FEMALE = 2

MARITAL_STATUSES = {"single": "مجرد", "married": "متاهل", "divorced": "مطلقه", "widowed": "همسر فوت‌شده"}
MEMBER_TYPES = {"spouse": "همسر", "son": "پسر", "daughter": "دختر"}
CHILD_TYPES = ("son", "daughter")
RELATIONS = {"biological": "فرزند خونی", "adopted": "فرزندخوانده", "step": "فرزند همسر"}
CUSTODY_OPTIONS = {"employee": "با خودم", "other_parent": "با والد دیگر", "joint": "مشترک"}

FIELD_MODES = ("required", "optional", "hidden")
PROFILE_STATUSES = {
    "draft": "ثبت نشده",
    "pending": "در انتظار بررسی",
    "approved": "تأیید شده",
    "rejected": "رد شده",
    "returned": "بازگشت برای ویرایش",
}

MAX_MEMBERS = 20
TEXT_MAX = 100

# فیلدهای قابل تنظیم از پنل HR. key = «بخش.ستون»؛ بخش child برای پسر و دختر مشترک است.
# فیلدهای هویتی پایه (وضعیت تاهل، دارای فرزند، نام/نام خانوادگی اعضا، تاریخ تولد فرزند و جنسیت)
# همیشه اجباری‌اند و اینجا نیستند، چون بدون آن‌ها هیچ قاعده‌ای قابل اجرا نیست.
FIELD_DEFS: list[dict] = [
    {"key": "profile.marriage_date", "label": "تاریخ ازدواج", "kind": "date", "default": "required"},
    {"key": "profile.separation_date", "label": "تاریخ طلاق / فوت همسر", "kind": "date", "default": "required"},
    {"key": "profile.is_head_of_household", "label": "سرپرست خانوار هستید؟", "kind": "bool", "default": "optional"},
    {"key": "spouse.father_name", "label": "نام پدر همسر", "kind": "text", "default": "required"},
    {"key": "spouse.national_id", "label": "کد ملی همسر", "kind": "national_id", "default": "required"},
    {"key": "spouse.birth_certificate_no", "label": "شماره شناسنامه همسر", "kind": "text", "default": "optional"},
    {"key": "spouse.birth_date", "label": "تاریخ تولد همسر", "kind": "date", "default": "required"},
    {"key": "spouse.marriage_certificate_no", "label": "شماره سند ازدواج", "kind": "text", "default": "optional"},
    {"key": "spouse.mobile", "label": "موبایل همسر", "kind": "mobile", "default": "optional"},
    {"key": "spouse.is_employed", "label": "همسر شاغل است؟", "kind": "bool", "default": "required"},
    {"key": "spouse.employer_name", "label": "نام محل کار همسر", "kind": "text", "default": "optional"},
    {"key": "spouse.is_insured", "label": "همسر بیمه‌پرداز است؟", "kind": "bool", "default": "optional"},
    {"key": "spouse.receives_child_allowance", "label": "همسر از محل کار خود حق اولاد می‌گیرد؟", "kind": "bool", "default": "optional"},
    {"key": "spouse.is_disabled", "label": "همسر از کار افتاده است؟", "kind": "bool", "default": "optional"},
    {"key": "child.national_id", "label": "کد ملی فرزند", "kind": "national_id", "default": "required"},
    {"key": "child.birth_certificate_no", "label": "شماره شناسنامه فرزند", "kind": "text", "default": "optional"},
    {"key": "child.relation", "label": "نسبت فرزند", "kind": "choice", "default": "required"},
    {"key": "child.other_parent_name", "label": "نام و نام خانوادگی پدر/مادر دیگر", "kind": "text", "default": "optional"},
    {"key": "child.custody", "label": "حضانت فرزند", "kind": "choice", "default": "optional"},
    {"key": "child.is_disabled", "label": "فرزند از کار افتاده است؟", "kind": "bool", "default": "optional"},
    {"key": "son.is_student", "label": "پسر در حال تحصیل است؟", "kind": "bool", "default": "required"},
    {"key": "son.education_level", "label": "مقطع تحصیلی پسر", "kind": "text", "default": "optional"},
    {"key": "son.school_name", "label": "نام مدرسه / دانشگاه پسر", "kind": "text", "default": "optional"},
    {"key": "son.is_employed", "label": "پسر شاغل است؟", "kind": "bool", "default": "optional"},
    {"key": "daughter.is_married", "label": "دختر ازدواج کرده است؟", "kind": "bool", "default": "required"},
    {"key": "daughter.marriage_date", "label": "تاریخ ازدواج دختر", "kind": "date", "default": "optional"},
    {"key": "daughter.is_employed", "label": "دختر شاغل است؟", "kind": "bool", "default": "required"},
]  # fmt: skip
FIELD_KEYS = {f["key"] for f in FIELD_DEFS}
_FIELD_KIND = {f["key"]: f["kind"] for f in FIELD_DEFS}

# انواع مدرک؛ scope=profile مدرک کل پرونده، scope=member مدرک یک عضو. «شرط» در required_documents است.
DOC_TYPES: dict[str, dict] = {
    "marriage_certificate": {"label": "سند ازدواج", "scope": "profile", "default": "required", "hint": "وقتی متاهل هستید"},
    "separation_document": {"label": "حکم طلاق / گواهی فوت همسر", "scope": "profile", "default": "required", "hint": "وقتی مطلقه یا همسر فوت‌شده هستید"},
    "head_of_household": {"label": "گواهی سرپرستی خانوار", "scope": "profile", "default": "required", "hint": "وقتی سرپرست خانوار هستید"},
    "birth_certificate": {"label": "تصویر شناسنامه", "scope": "member", "default": "required", "hint": "برای همسر و هر فرزند"},
    "student_certificate": {"label": "گواهی اشتغال به تحصیل", "scope": "member", "default": "required", "hint": "برای پسری که در حال تحصیل است", "renewal": 12},
    "disability_certificate": {"label": "گواهی از کار افتادگی", "scope": "member", "default": "required", "hint": "برای عضوی که از کار افتاده است"},
    "custody_ruling": {"label": "حکم حضانت", "scope": "member", "default": "optional", "hint": "برای فرزندی که پس از طلاق حضانتش با شماست"},
}  # fmt: skip

DEFAULT_NOTES = [
    "اطلاعات این فرم پس از بررسی و تأیید واحد منابع انسانی در محاسبه‌ی حق تاهل و حق اولاد استفاده می‌شود.",
    "در صورت هر تغییر (ازدواج، تولد فرزند، طلاق، پایان تحصیل، ازدواج یا اشتغال فرزند) فرم را به‌روز کنید.",
]

DEFAULT_RULES: dict = {
    "marriage": {
        "enabled": True,
        "male_married": True,  # کارمند مرد متاهل مشمول است
        "female_mode": "head_of_household",  # none / head_of_household / married / all_married_or_head
        "min_insurance_days": None,
    },
    "child": {
        "enabled": True,
        "min_insurance_days": 720,
        "max_children": None,  # خالی = بدون سقف
        "female_mode": "spouse_unable",  # none / head_of_household / spouse_unable / all
        "exclude_if_spouse_receives": True,
        "include_adopted": True,
        "include_step": False,
        "require_custody_after_divorce": True,
        "son_max_age": 18,
        "son_extend_if_student": True,
        "son_student_max_age": None,
        "son_require_valid_student_certificate": True,
        "son_extend_if_disabled": True,
        "daughter_stop_on_marriage": True,
        "daughter_stop_on_employment": True,
        "daughter_max_age": None,
        "daughter_extend_if_disabled": True,
    },
}

MARRIAGE_FEMALE_MODES = {
    "none": "مشمول نیست",
    "head_of_household": "فقط سرپرست خانوار",
    "married": "هر کارمند زن متاهل",
    "all_married_or_head": "متاهل یا سرپرست خانوار",
}
CHILD_FEMALE_MODES = {
    "none": "مشمول نیست",
    "head_of_household": "فقط سرپرست خانوار",
    "spouse_unable": "سرپرست خانوار، یا همسر فوت‌شده / از کار افتاده / غیرشاغل / مطلقه",
    "all": "همه‌ی کارمندان زن",
}

DEFAULT_ALERTS = {"son_age_warning_months": 3, "doc_expiry_warning_days": 30}

DEFAULT_SETTINGS: dict = {
    "enabled": True,
    "lock_after_approval": False,
    "notes": DEFAULT_NOTES,
    "fields": {f["key"]: f["default"] for f in FIELD_DEFS},
    "documents": {
        k: {"mode": v["default"], "renewal_months": v.get("renewal")} for k, v in DOC_TYPES.items()
    },
    "rules": DEFAULT_RULES,
    "alerts": DEFAULT_ALERTS,
}


class FamilyRuleError(ValueError):
    """خطای اعتبارسنجی قابل نمایش به کاربر (پیام فارسی)."""


# ---------- تاریخ و ارقام ----------

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def to_english_digits(value) -> str:
    return str(value or "").translate(_DIGITS)


def parse_jalali(value) -> tuple[int, int, int] | None:
    """«1403/7/5»، «1403-07-05» یا «14030705» → (1403, 7, 5)؛ تاریخ نامعتبر → None."""
    text = to_english_digits(value).strip()
    if not text:
        return None
    m = re.fullmatch(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", text) or re.fullmatch(r"(\d{4})(\d{2})(\d{2})", text)
    if not m:
        return None
    y, mo, d = (int(g) for g in m.groups())
    if not (1300 <= y <= 1500 and 1 <= mo <= 12 and 1 <= d <= _month_days(mo)):
        return None
    return y, mo, d


def format_jalali(t: tuple[int, int, int] | None) -> str | None:
    return f"{t[0]:04d}/{t[1]:02d}/{t[2]:02d}" if t else None


def _month_days(month: int) -> int:
    """حداکثر روز ماه شمسی (اسفند ۳۰ برای سال کبیسه پذیرفته می‌شود)."""
    return 31 if month <= 6 else 30


def add_months(t: tuple[int, int, int], months: int) -> tuple[int, int, int]:
    """افزودن n ماه به تاریخ شمسی؛ روز در صورت لزوم به آخر ماه مقصد محدود می‌شود (اسفند = ۲۹)."""
    total = t[0] * 12 + (t[1] - 1) + months
    y, mo = divmod(total, 12)
    mo += 1
    limit = 29 if mo == 12 else _month_days(mo)
    return y, mo, min(t[2], limit)


def age_on(birth: tuple[int, int, int], ref: tuple[int, int, int]) -> int:
    """سن کامل (سال) در تاریخ ref."""
    years = ref[0] - birth[0]
    if (ref[1], ref[2]) < (birth[1], birth[2]):
        years -= 1
    return years


def is_valid_national_id(value: str) -> bool:
    """صحت کد ملی با رقم کنترل؛ کدهای تک‌رقمی تکراری رد می‌شوند."""
    nid = to_english_digits(value).strip()
    if len(nid) == 9:
        nid = "0" + nid
    if len(nid) != 10 or not nid.isdigit() or len(set(nid)) == 1:
        return False
    rem = sum(int(nid[i]) * (10 - i) for i in range(9)) % 11
    check = int(nid[9])
    return check == rem if rem < 2 else check == 11 - rem


# ---------- تنظیمات ----------


def _int_or_none(value, lo: int = 0, hi: int = 100000) -> int | None:
    if value in (None, ""):
        return None
    try:
        n = int(to_english_digits(value))
    except (TypeError, ValueError):
        return None
    return max(lo, min(hi, n))


def sanitize_settings(value) -> dict:
    """
    تنظیمات ذخیره‌شده یا ورودی را با پیش‌فرض‌ها ادغام و پاک‌سازی می‌کند و همیشه ساختار کامل برمی‌گرداند.
    کلید ناشناخته دور ریخته می‌شود و مقدار نامعتبر با پیش‌فرض جایگزین می‌شود.
    """
    src = value if isinstance(value, dict) else {}
    out: dict = {
        "enabled": bool(src.get("enabled", DEFAULT_SETTINGS["enabled"])),
        "lock_after_approval": bool(src.get("lock_after_approval", DEFAULT_SETTINGS["lock_after_approval"])),
    }
    notes = src.get("notes")
    if isinstance(notes, list):
        out["notes"] = [str(n).strip()[:500] for n in notes[:30] if str(n).strip()]
    else:
        out["notes"] = list(DEFAULT_NOTES)

    fields_in = src.get("fields") if isinstance(src.get("fields"), dict) else {}
    out["fields"] = {}
    for f in FIELD_DEFS:
        mode = fields_in.get(f["key"])
        out["fields"][f["key"]] = mode if mode in FIELD_MODES else f["default"]

    docs_in = src.get("documents") if isinstance(src.get("documents"), dict) else {}
    out["documents"] = {}
    for key, spec in DOC_TYPES.items():
        d = docs_in.get(key) if isinstance(docs_in.get(key), dict) else {}
        mode = d.get("mode")
        renewal = _int_or_none(d.get("renewal_months"), 1, 120) if "renewal_months" in d else spec.get("renewal")
        out["documents"][key] = {"mode": mode if mode in FIELD_MODES else spec["default"], "renewal_months": renewal}

    rules_in = src.get("rules") if isinstance(src.get("rules"), dict) else {}
    m_in = rules_in.get("marriage") if isinstance(rules_in.get("marriage"), dict) else {}
    c_in = rules_in.get("child") if isinstance(rules_in.get("child"), dict) else {}
    md, cd = DEFAULT_RULES["marriage"], DEFAULT_RULES["child"]

    def _b(src_d, dflt, k):
        return bool(src_d[k]) if k in src_d and src_d[k] is not None else dflt[k]

    def _n(src_d, dflt, k, lo=0, hi=100000):
        return _int_or_none(src_d[k], lo, hi) if k in src_d else dflt[k]

    out["rules"] = {
        "marriage": {
            "enabled": _b(m_in, md, "enabled"),
            "male_married": _b(m_in, md, "male_married"),
            "female_mode": m_in.get("female_mode") if m_in.get("female_mode") in MARRIAGE_FEMALE_MODES else md["female_mode"],
            "min_insurance_days": _n(m_in, md, "min_insurance_days", 0, 20000),
        },
        "child": {
            "enabled": _b(c_in, cd, "enabled"),
            "min_insurance_days": _n(c_in, cd, "min_insurance_days", 0, 20000),
            "max_children": _n(c_in, cd, "max_children", 1, 50),
            "female_mode": c_in.get("female_mode") if c_in.get("female_mode") in CHILD_FEMALE_MODES else cd["female_mode"],
            "exclude_if_spouse_receives": _b(c_in, cd, "exclude_if_spouse_receives"),
            "include_adopted": _b(c_in, cd, "include_adopted"),
            "include_step": _b(c_in, cd, "include_step"),
            "require_custody_after_divorce": _b(c_in, cd, "require_custody_after_divorce"),
            "son_max_age": _n(c_in, cd, "son_max_age", 1, 99) or cd["son_max_age"],
            "son_extend_if_student": _b(c_in, cd, "son_extend_if_student"),
            "son_student_max_age": _n(c_in, cd, "son_student_max_age", 1, 99),
            "son_require_valid_student_certificate": _b(c_in, cd, "son_require_valid_student_certificate"),
            "son_extend_if_disabled": _b(c_in, cd, "son_extend_if_disabled"),
            "daughter_stop_on_marriage": _b(c_in, cd, "daughter_stop_on_marriage"),
            "daughter_stop_on_employment": _b(c_in, cd, "daughter_stop_on_employment"),
            "daughter_max_age": _n(c_in, cd, "daughter_max_age", 1, 99),
            "daughter_extend_if_disabled": _b(c_in, cd, "daughter_extend_if_disabled"),
        },
    }
    a_in = src.get("alerts") if isinstance(src.get("alerts"), dict) else {}
    out["alerts"] = {
        "son_age_warning_months": _int_or_none(a_in.get("son_age_warning_months"), 0, 36)
        if "son_age_warning_months" in a_in
        else DEFAULT_ALERTS["son_age_warning_months"],
        "doc_expiry_warning_days": _int_or_none(a_in.get("doc_expiry_warning_days"), 0, 365)
        if "doc_expiry_warning_days" in a_in
        else DEFAULT_ALERTS["doc_expiry_warning_days"],
    }
    return out


def merge_settings(current: dict, patch: dict) -> dict:
    """patch را (یک سطح عمیق‌تر برای fields/documents/rules/alerts) روی تنظیمات فعلی ادغام و پاک‌سازی می‌کند."""
    merged = {**current}
    for key, value in (patch or {}).items():
        if value is None:
            continue
        if key in ("fields", "alerts") and isinstance(value, dict):
            merged[key] = {**current.get(key, {}), **value}
        elif key == "documents" and isinstance(value, dict):
            merged["documents"] = {
                k: {**current["documents"].get(k, {}), **(value.get(k) if isinstance(value.get(k), dict) else {})}
                for k in current["documents"]
            }
        elif key == "rules" and isinstance(value, dict):
            merged["rules"] = {
                "marriage": {**current["rules"]["marriage"], **(value.get("marriage") or {})},
                "child": {**current["rules"]["child"], **(value.get("child") or {})},
            }
        else:
            merged[key] = value
    return sanitize_settings(merged)


# ---------- اعتبارسنجی فرم ----------

_MEMBER_TEXT = ("first_name", "last_name", "father_name", "birth_certificate_no", "marriage_certificate_no",
                "employer_name", "other_parent_name", "education_level", "school_name")  # fmt: skip
_MEMBER_BOOL = ("is_employed", "is_insured", "receives_child_allowance", "is_disabled", "is_student", "is_married")
# ترتیب مهم است: پاسخ‌های بله/خیر اول پردازش می‌شوند تا فیلدهای وابسته (نام محل کار، مقطع تحصیلی، ...) بدانند مرتبط‌اند یا نه
MEMBER_COLUMNS = _MEMBER_BOOL + _MEMBER_TEXT + ("national_id", "birth_date", "mobile", "relation", "custody", "marriage_date")


def _to_bool(value) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "بله"):
        return True
    if text in ("0", "false", "no", "خیر"):
        return False
    return None


def _member_field_key(member_type: str, column: str) -> str | None:
    """کلید تنظیم فیلد یک ستون عضو (برای پسر/دختر اول بخش اختصاصی، سپس بخش مشترک child)."""
    if member_type == "spouse":
        key = f"spouse.{column}"
        return key if key in FIELD_KEYS else None
    for section in (member_type, "child"):
        key = f"{section}.{column}"
        if key in FIELD_KEYS:
            return key
    return None


def _member_field_applies(member_type: str, column: str, member: dict) -> bool:
    """فیلدهای وابسته فقط وقتی پاسخ والد «بله» است معنی دارند."""
    if column in ("employer_name", "is_insured"):
        return member.get("is_employed") is True
    if column in ("education_level", "school_name"):
        return member.get("is_student") is True
    if column == "marriage_date" and member_type == "daughter":
        return member.get("is_married") is True
    return True


def _normalize_value(kind: str, raw, label: str):
    """مقدار یک فیلد را بر اساس نوعش نرمال و اعتبارسنجی می‌کند؛ خالی → None."""
    if kind == "bool":
        return _to_bool(raw)
    text = to_english_digits(raw).strip() if kind in ("date", "national_id", "mobile") else str(raw or "").strip()
    if not text:
        return None
    if kind == "date":
        t = parse_jalali(text)
        if t is None:
            raise FamilyRuleError(f"{label} نامعتبر است (قالب درست: ۱۴۰۳/۰۷/۲۰).")
        return format_jalali(t)
    if kind == "national_id":
        if len(text) == 9:
            text = "0" + text
        if not is_valid_national_id(text):
            raise FamilyRuleError(f"{label} نامعتبر است.")
        return text
    if kind == "mobile":
        if len(text) == 10 and text.startswith("9"):
            text = "0" + text
        if not re.fullmatch(r"09\d{9}", text):
            raise FamilyRuleError(f"{label} نامعتبر است.")
        return text
    return text[:TEXT_MAX]


def validate_payload(payload: dict, settings: dict, today: tuple[int, int, int]) -> dict:
    """
    فرم کارمند را با تنظیمات فیلدها اعتبارسنجی و نرمال می‌کند.
    خروجی: {marital_status, marriage_date, separation_date, is_head_of_household, has_children, members: [...]}
    فیلد «مخفی» یا غیرمرتبط همیشه None ذخیره می‌شود؛ فیلد «اجباری» مرتبط نباید خالی باشد.
    """
    fields = settings["fields"]
    marital = payload.get("marital_status")
    if marital not in MARITAL_STATUSES:
        raise FamilyRuleError("وضعیت تاهل را انتخاب کنید.")
    has_children = _to_bool(payload.get("has_children"))
    if has_children is None:
        raise FamilyRuleError("مشخص کنید که فرزند دارید یا نه.")

    out: dict = {"marital_status": marital, "has_children": has_children}

    def profile_field(column: str, applies: bool):
        key = f"profile.{column}"
        mode = fields.get(key, "optional")
        if mode == "hidden" or not applies:
            return None
        label = next(f["label"] for f in FIELD_DEFS if f["key"] == key)
        value = _normalize_value(_FIELD_KIND[key], payload.get(column), label)
        if value is None and mode == "required":
            raise FamilyRuleError(f"«{label}» را وارد کنید.")
        return value

    out["marriage_date"] = profile_field("marriage_date", marital == "married")
    out["separation_date"] = profile_field("separation_date", marital in ("divorced", "widowed"))
    out["is_head_of_household"] = profile_field("is_head_of_household", True)
    for key in ("marriage_date", "separation_date"):
        if out[key] and parse_jalali(out[key]) > today:
            raise FamilyRuleError("تاریخ ازدواج / طلاق نمی‌تواند در آینده باشد.")

    members_in = payload.get("members") or []
    if not isinstance(members_in, list):
        raise FamilyRuleError("فهرست اعضا نامعتبر است.")
    if len(members_in) > MAX_MEMBERS:
        raise FamilyRuleError(f"حداکثر {MAX_MEMBERS} عضو مجاز است.")
    spouses = [m for m in members_in if (m or {}).get("member_type") == "spouse"]
    children = [m for m in members_in if (m or {}).get("member_type") in CHILD_TYPES]
    if len(spouses) + len(children) != len(members_in):
        raise FamilyRuleError("نوع عضو نامعتبر است.")
    if marital == "married" and len(spouses) != 1:
        raise FamilyRuleError("مشخصات همسر را وارد کنید.")
    if marital != "married" and spouses:
        raise FamilyRuleError("مشخصات همسر فقط برای وضعیت «متاهل» ثبت می‌شود.")
    if has_children and not children:
        raise FamilyRuleError("مشخصات حداقل یک فرزند را وارد کنید.")
    if not has_children and children:
        raise FamilyRuleError("گزینه «دارای فرزند» را انتخاب کنید یا فرزندان را حذف کنید.")

    members: list[dict] = []
    seen_nid: set[str] = set()
    child_no = {"son": 0, "daughter": 0}
    for raw in spouses + children:
        mtype = raw["member_type"]
        if mtype in CHILD_TYPES:
            child_no[mtype] += 1
            who = f"{MEMBER_TYPES[mtype]} {child_no[mtype]}"
        else:
            who = "همسر"
        m: dict = {"member_type": mtype}
        first = str(raw.get("first_name") or "").strip()[:TEXT_MAX]
        last = str(raw.get("last_name") or "").strip()[:TEXT_MAX]
        if not first or not last:
            raise FamilyRuleError(f"نام و نام خانوادگی {who} را وارد کنید.")
        m["first_name"], m["last_name"] = first, last
        for col in MEMBER_COLUMNS:
            if col in ("first_name", "last_name"):
                continue
            key = _member_field_key(mtype, col)
            always_required = col == "birth_date" and mtype in CHILD_TYPES
            if key is None and not always_required:
                m[col] = None
                continue
            mode = "required" if always_required else fields.get(key, "optional")
            if mode == "hidden" or not _member_field_applies(mtype, col, m):
                m[col] = None
                continue
            label = f"{_FIELD_LABELS.get(col, col)} {who}"
            kind = "date" if always_required else _FIELD_KIND[key]
            if kind == "choice":
                options = RELATIONS if col == "relation" else CUSTODY_OPTIONS
                value = raw.get(col) if raw.get(col) in options else None
            else:
                value = _normalize_value(kind, raw.get(col), label)
            if value is None and mode == "required":
                raise FamilyRuleError(f"«{label}» را {'مشخص' if kind in ('bool', 'choice') else 'وارد'} کنید.")
            m[col] = value
        if m.get("birth_date") and parse_jalali(m["birth_date"]) > today:
            raise FamilyRuleError(f"تاریخ تولد {who} نمی‌تواند در آینده باشد.")
        if m.get("national_id"):
            if m["national_id"] in seen_nid:
                raise FamilyRuleError(f"کد ملی {who} تکراری است.")
            seen_nid.add(m["national_id"])
        if mtype in CHILD_TYPES and m.get("relation") is None:
            m["relation"] = "biological"  # فیلد مخفی/اختیاری خالی = فرزند خونی
        members.append(m)
    out["members"] = members
    return out


_FIELD_LABELS = {
    "father_name": "نام پدر", "national_id": "کد ملی", "birth_certificate_no": "شماره شناسنامه",
    "birth_date": "تاریخ تولد", "marriage_certificate_no": "شماره سند ازدواج", "mobile": "موبایل",
    "is_employed": "وضعیت اشتغال", "employer_name": "نام محل کار", "is_insured": "وضعیت بیمه",
    "receives_child_allowance": "دریافت حق اولاد", "is_disabled": "وضعیت از کار افتادگی",
    "relation": "نسبت", "other_parent_name": "نام پدر/مادر دیگر", "custody": "حضانت",
    "is_student": "وضعیت تحصیل", "education_level": "مقطع تحصیلی", "school_name": "نام مدرسه/دانشگاه",
    "is_married": "وضعیت ازدواج", "marriage_date": "تاریخ ازدواج",
}  # fmt: skip


# ---------- مدارک ----------


def document_condition(doc_type: str, data: dict, member: dict | None) -> bool:
    """آیا این نوع مدرک با پاسخ‌های فرم موضوعیت دارد؟"""
    marital = data.get("marital_status")
    if doc_type == "marriage_certificate":
        return marital == "married"
    if doc_type == "separation_document":
        return marital in ("divorced", "widowed")
    if doc_type == "head_of_household":
        return data.get("is_head_of_household") is True
    if member is None:
        return False
    mtype = member.get("member_type")
    if doc_type == "birth_certificate":
        return True
    if doc_type == "student_certificate":
        return mtype == "son" and member.get("is_student") is True
    if doc_type == "disability_certificate":
        return member.get("is_disabled") is True
    if doc_type == "custody_ruling":
        return mtype in CHILD_TYPES and marital == "divorced" and member.get("custody") == "employee"
    return False


def allowed_documents(settings: dict, data: dict, member: dict | None) -> list[str]:
    """انواع مدرکی که برای پرونده (member=None) یا یک عضو قابل آپلود است (مخفی‌ها حذف)."""
    scope = "profile" if member is None else "member"
    return [
        k for k, spec in DOC_TYPES.items()
        if spec["scope"] == scope and settings["documents"][k]["mode"] != "hidden" and document_condition(k, data, member)
    ]  # fmt: skip


def missing_documents(settings: dict, data: dict) -> list[str]:
    """
    مدارک اجباریِ موضوع‌دار که در data پیوست نشده‌اند (پیام‌های فارسی).
    data["docs"] و member["docs"]: فهرست {doc_type, ...} پیوست‌شده.
    """
    missing: list[str] = []
    have = {d.get("doc_type") for d in data.get("docs") or []}
    for k in allowed_documents(settings, data, None):
        if settings["documents"][k]["mode"] == "required" and k not in have:
            missing.append(DOC_TYPES[k]["label"])
    counters = {"son": 0, "daughter": 0}
    for m in data.get("members") or []:
        mtype = m.get("member_type")
        if mtype in counters:
            counters[mtype] += 1
            who = f"{MEMBER_TYPES[mtype]} {counters[mtype]}"
        else:
            who = "همسر"
        mh = {d.get("doc_type") for d in m.get("docs") or []}
        for k in allowed_documents(settings, data, m):
            if settings["documents"][k]["mode"] == "required" and k not in mh:
                missing.append(f"{DOC_TYPES[k]['label']} ({who})")
    return missing


def document_expiry(settings: dict, doc: dict) -> tuple[int, int, int] | None:
    """تاریخ انقضای یک مدرک = تاریخ آپلود (شمسی) + دوره تمدید تنظیم‌شده؛ بدون دوره → None."""
    months = (settings["documents"].get(doc.get("doc_type")) or {}).get("renewal_months")
    uploaded = parse_jalali(doc.get("uploaded"))
    if not months or uploaded is None:
        return None
    return add_months(uploaded, months)


# ---------- محاسبه‌ی شمول ----------


def _member_name(m: dict) -> str:
    return f"{m.get('first_name') or ''} {m.get('last_name') or ''}".strip()


def evaluate(
    data: dict,
    employee_gender: int | None,
    insurance_days: int | None,
    settings: dict,
    as_of: tuple[int, int, int],
) -> dict:
    """
    شمول حق تاهل و فرزندان واجد شرایط را بر اساس تنظیمات HR در تاریخ as_of حساب می‌کند.
    data همان ساختار خروجی validate_payload است به‌علاوه‌ی docs (برای اعتبار گواهی تحصیل).
    خروجی:
      marriage: {eligible: bool|None, reason}
      child: {eligible_count, total, blocked_reason, children: [{name, member_type, age, eligible, reason}]}
    eligible=None یعنی قاعده در تنظیمات غیرفعال است.
    """
    rules = settings["rules"]
    marital = data.get("marital_status")
    head = data.get("is_head_of_household") is True
    members = data.get("members") or []
    spouse = next((m for m in members if m.get("member_type") == "spouse"), None)

    # --- حق تاهل ---
    mr = rules["marriage"]
    if not mr["enabled"]:
        marriage = {"eligible": None, "reason": "در تنظیمات غیرفعال است"}
    elif employee_gender not in (GENDER_MALE, GENDER_FEMALE):
        marriage = {"eligible": False, "reason": "جنسیت پرسنل مشخص نیست"}
    else:
        married = marital == "married"
        married_since = parse_jalali(data.get("marriage_date"))
        if married and married_since and married_since > as_of:
            married = False
        if employee_gender == GENDER_MALE:
            ok, reason = (married and mr["male_married"]), ("متاهل" if married else "متاهل نیست")
            if married and not mr["male_married"]:
                reason = "کارمند مرد طبق تنظیمات مشمول نیست"
        else:
            mode = mr["female_mode"]
            ok = (
                (mode == "head_of_household" and head)
                or (mode == "married" and married)
                or (mode == "all_married_or_head" and (married or head))
            )
            reason = "مشمول (" + ("سرپرست خانوار" if head else "متاهل") + ")" if ok else (
                "کارمند زن طبق تنظیمات مشمول نیست" if mode == "none" else f"شرط کارمند زن: {MARRIAGE_FEMALE_MODES[mode]}"
            )
        if ok and mr["min_insurance_days"]:
            if insurance_days is None:
                ok, reason = False, "سابقه بیمه ثبت نشده"
            elif insurance_days < mr["min_insurance_days"]:
                ok, reason = False, f"سابقه بیمه کمتر از {mr['min_insurance_days']} روز"
        marriage = {"eligible": bool(ok), "reason": reason}

    # --- حق اولاد ---
    cr = rules["child"]
    kids = [m for m in members if m.get("member_type") in CHILD_TYPES]
    index_of = {id(m): i for i, m in enumerate(members)}
    result_children: list[dict] = []
    blocked: str | None = None
    if not cr["enabled"]:
        blocked = "در تنظیمات غیرفعال است"
    elif employee_gender not in (GENDER_MALE, GENDER_FEMALE):
        blocked = "جنسیت پرسنل مشخص نیست"
    else:
        if employee_gender == GENDER_FEMALE:
            mode = cr["female_mode"]
            spouse_unable = (
                marital in ("divorced", "widowed")
                or (spouse is not None and (spouse.get("is_disabled") is True or spouse.get("is_employed") is False))
            )
            allowed = (
                mode == "all"
                or (mode == "head_of_household" and head)
                or (mode == "spouse_unable" and (head or spouse_unable))
            )
            if not allowed:
                blocked = "کارمند زن طبق تنظیمات مشمول نیست" if mode == "none" else f"شرط کارمند زن: {CHILD_FEMALE_MODES[mode]}"
        if blocked is None and cr["exclude_if_spouse_receives"] and spouse and spouse.get("receives_child_allowance") is True:
            blocked = "همسر از محل کار خود حق اولاد می‌گیرد"
        if blocked is None and cr["min_insurance_days"]:
            if insurance_days is None:
                blocked = "سابقه بیمه ثبت نشده"
            elif insurance_days < cr["min_insurance_days"]:
                blocked = f"سابقه بیمه کمتر از {cr['min_insurance_days']} روز"

    # ترتیب از بزرگ‌ترین فرزند (سقف تعداد روی فرزندان بزرگ‌تر اعمال می‌شود)
    ordered = sorted(kids, key=lambda k: parse_jalali(k.get("birth_date")) or (9999, 12, 31))
    eligible_count = 0
    for kid in ordered:
        birth = parse_jalali(kid.get("birth_date"))
        age = age_on(birth, as_of) if birth else None
        entry = {
            "member_index": index_of[id(kid)],
            "name": _member_name(kid),
            "member_type": kid.get("member_type"),
            "birth_date": kid.get("birth_date"),
            "age": age,
            "eligible": False,
            "reason": "",
        }
        ok, reason = _child_eligible(kid, data, settings, as_of, age)
        if blocked is not None:
            ok, reason = False, blocked
        if ok and cr["max_children"] and eligible_count >= cr["max_children"]:
            ok, reason = False, f"خارج از سقف {cr['max_children']} فرزند"
        entry["eligible"], entry["reason"] = ok, reason
        if ok:
            eligible_count += 1
        result_children.append(entry)

    return {
        "marriage": marriage,
        "child": {
            "eligible_count": eligible_count,
            "total": len(kids),
            "blocked_reason": blocked,
            "children": result_children,
        },
    }


def _child_eligible(kid: dict, data: dict, settings: dict, as_of, age: int | None) -> tuple[bool, str]:
    """شرایط اختصاصی یک فرزند (بدون شرط‌های کلی کارمند)."""
    cr = settings["rules"]["child"]
    if age is None:
        return False, "تاریخ تولد ثبت نشده"
    if age < 0:
        return False, "هنوز متولد نشده"
    relation = kid.get("relation") or "biological"
    if relation == "adopted" and not cr["include_adopted"]:
        return False, "فرزندخوانده طبق تنظیمات مشمول نیست"
    if relation == "step" and not cr["include_step"]:
        return False, "فرزند همسر طبق تنظیمات مشمول نیست"
    if (
        cr["require_custody_after_divorce"]
        and data.get("marital_status") == "divorced"
        and kid.get("custody") not in ("employee", "joint")
    ):
        return False, "حضانت با کارمند نیست"
    disabled = kid.get("is_disabled") is True
    if kid.get("member_type") == "son":
        if age < cr["son_max_age"]:
            return True, "مشمول"
        if cr["son_extend_if_disabled"] and disabled:
            return True, "مشمول (از کار افتاده)"
        if cr["son_extend_if_student"] and kid.get("is_student") is True:
            if cr["son_student_max_age"] and age >= cr["son_student_max_age"]:
                return False, f"بیش از {cr['son_student_max_age']} سال (سقف سن تحصیل)"
            if cr["son_require_valid_student_certificate"] and not _has_valid_doc(kid, "student_certificate", settings, as_of):
                return False, "گواهی تحصیل معتبر ندارد"
            return True, "مشمول (در حال تحصیل)"
        return False, f"پسر {cr['son_max_age']} سال یا بیشتر"
    # دختر
    if cr["daughter_stop_on_marriage"] and kid.get("is_married") is True:
        married_since = parse_jalali(kid.get("marriage_date"))
        if married_since is None or married_since <= as_of:
            return False, "ازدواج کرده"
    if cr["daughter_stop_on_employment"] and kid.get("is_employed") is True:
        return False, "شاغل است"
    if cr["daughter_max_age"] and age >= cr["daughter_max_age"]:
        if cr["daughter_extend_if_disabled"] and disabled:
            return True, "مشمول (از کار افتاده)"
        return False, f"دختر {cr['daughter_max_age']} سال یا بیشتر"
    return True, "مشمول"


def _has_valid_doc(member: dict, doc_type: str, settings: dict, as_of) -> bool:
    for doc in member.get("docs") or []:
        if doc.get("doc_type") != doc_type:
            continue
        expiry = document_expiry(settings, doc)
        if expiry is None or expiry >= as_of:
            return True
    return False


# ---------- هشدارها ----------


def warnings(data: dict, settings: dict, today: tuple[int, int, int]) -> list[str]:
    """
    هشدارهای یک پرونده در تاریخ today:
    - پسری که در بازه‌ی تنظیم‌شده به سن سقف می‌رسد
    - مدرکی که منقضی شده یا در بازه‌ی تنظیم‌شده منقضی می‌شود
    """
    out: list[str] = []
    alerts = settings["alerts"]
    son_max = settings["rules"]["child"]["son_max_age"]
    warn_months = alerts.get("son_age_warning_months") or 0
    for m in data.get("members") or []:
        if m.get("member_type") == "son" and warn_months:
            birth = parse_jalali(m.get("birth_date"))
            if birth:
                reach = (birth[0] + son_max, birth[1], 29 if birth[1] == 12 and birth[2] == 30 else birth[2])
                if today <= reach <= add_months(today, warn_months):
                    out.append(f"{_member_name(m)} در {format_jalali(reach)} به {son_max} سالگی می‌رسد")
    warn_days = alerts.get("doc_expiry_warning_days") or 0
    # مقایسه‌ی شمسی بدون تبدیل تقویم: بازه‌ی روز به ماه گرد می‌شود (هر ۳۰ روز یک ماه، حداقل یک ماه)
    horizon = add_months(today, max(1, round(warn_days / 30))) if warn_days else today

    def _check(doc: dict, owner: str):
        expiry = document_expiry(settings, doc)
        if expiry is None:
            return
        label = DOC_TYPES.get(doc.get("doc_type"), {}).get("label", "مدرک")
        if expiry < today:
            out.append(f"{label} {owner} در {format_jalali(expiry)} منقضی شده است")
        elif warn_days and expiry <= horizon:
            out.append(f"{label} {owner} در {format_jalali(expiry)} منقضی می‌شود")

    for doc in data.get("docs") or []:
        _check(doc, "")
    for m in data.get("members") or []:
        for doc in m.get("docs") or []:
            _check(doc, _member_name(m))
    return [w.replace("  ", " ") for w in out]
