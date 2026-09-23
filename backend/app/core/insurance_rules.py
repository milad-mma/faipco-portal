"""
قوانین خالص ماژول «بیمه تکمیلی» - بازسازی دقیق منطق سامانه قدیمی
(insurance.faipco.ir: save.php + assets/js/form.js + config/constants.php).
⚠️ طبق درخواست کاربر: منطق عیناً حفظ شده؛ فقط اعتبارسنجی سمت سرور کامل‌تر
است (در سامانه قدیمی بخشی از اعتبارسنجی فقط در مرورگر بود).
"""
from __future__ import annotations

import re

# ---------- مقادیر ثابت بیمه‌گر (constants.php) ----------
GROUP_CODE = 3
BASE_INSURANCE_CODE = 144
REQUEST_REASON = 23
EMPLOYMENT_TYPE = 1
PREVIOUS_INSURANCE_CODE = 5
COVERAGE_MONTHS = 12
ORGANIZATION_CODE = 9999999

RELATION_SELF = 1
DEPENDENCY_SELF = 3

GENDER_MALE = 1
GENDER_FEMALE = 2
MARITAL_SINGLE = 2
MARITAL_MARRIED = 3

# member_type → (عنوان، حداکثر تعداد، کد نسبت، کد تکفل، جنسیت ثابت یا None)
MEMBER_TYPES: dict[str, dict] = {
    "spouse": {"title": "همسر", "max_count": 1, "relation_code": 2, "dependency_code": 1, "gender": None},
    "son": {"title": "فرزند پسر", "max_count": 99, "relation_code": 7, "dependency_code": 1, "gender": GENDER_MALE},
    "daughter": {"title": "فرزند دختر", "max_count": 99, "relation_code": 8, "dependency_code": 1, "gender": GENDER_FEMALE},
    "father": {"title": "پدر", "max_count": 1, "relation_code": 3, "dependency_code": 2, "gender": GENDER_MALE},
    "mother": {"title": "مادر", "max_count": 1, "relation_code": 4, "dependency_code": 2, "gender": GENDER_FEMALE},
}

ACCOUNT_TYPES = {1: "قرض‌الحسنه جاری", 2: "سپرده کوتاه‌مدت", 3: "سپرده بلندمدت", 4: "قرض‌الحسنه پس‌انداز"}

BANK_CODES = {
    1: "آینده", 2: "اقتصاد نوین", 3: "ایران زمین", 4: "تجارت", 5: "توسعه صادرات", 6: "رفاه کارگران",
    7: "سپه", 8: "صادرات", 9: "کشاورزی", 10: "مسکن", 11: "ملی", 12: "انصار", 13: "رسالت", 14: "شهر",
    15: "صنعت و معدن", 16: "ملت", 17: "پاسارگاد", 18: "توسعه تعاون", 20: "دی", 21: "سامان", 22: "سرمایه",
    23: "سینا", 24: "قرض‌الحسنه مهر ایران", 25: "مالی اعتباری بنیاد", 26: "موسسه مالی و اعتباری عسگریه",
    27: "پارسیان", 28: "پست بانک", 29: "کارآفرین", 30: "سایر", 31: "قوامین", 32: "حکمت ایرانیان", 33: "کوثر",
    34: "گردشگری", 35: "انصارالمجاهدین", 36: "مهراقتصاد", 37: "مرکزی",
}  # fmt: skip

# مدرک کفالت: تصویر/PDF تا ۱۰ مگابایت (upload_doc.php)
DOCUMENT_ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp", "image/tiff", "application/pdf",
}  # fmt: skip
DOCUMENT_MAX_BYTES = 10 * 1024 * 1024

# پیش‌فرض بخش ۴ فرم (قابل ویرایش از پنل - تنظیمات بیمه تکمیلی)
DEFAULT_RATE_TABLE = {
    "unit": "تومان",
    "age_header": "سن",
    "non_dependent_header": "غیر تحت تکفل",
    "dependent_header": "تحت تکفل",
    "rows": [
        {"age_label": "۱ تا ۶۰ سال", "non_dependent": 1380000, "dependent": 690000},
        {"age_label": "۶۱ تا ۷۰ سال", "non_dependent": 2070000, "dependent": 1035000},
        {"age_label": "بالاتر از ۷۱ سال", "non_dependent": 2760000, "dependent": 1380000},
    ],
}
DEFAULT_NOTES = [
    "۵۰ درصد حق بیمه کلیه پرسنل و **افراد تحت تکفل** به عهده شرکت می‌باشد.",
    "حق بیمه **افراد غیر تحت تکفل** ۱۰۰ درصد به عهده پرسنل می‌باشد.",
    "پرداخت هزینه بیمه تکمیلی به صورت ماهانه و به صورت کسر از حقوق انجام خواهد شد.",
    "در مورد پرسنل مونث: همسر، فرزندان، پدر و مادر **غیر تحت تکفل** می‌باشد، مگر با ارائه مستندات قانونی مانند مدرک کفالت یا حضانت.",
    "شماره حساب بانکی حتماً باید به نام بیمه شده اصلی (پرسنل) باشد، در غیر این صورت عواقب هر گونه خطا یا مشکل به عهده ثبت‌نام کننده خواهد بود.",
    "پس از پایان مهلت مقرر، امکان ثبت‌نام یا ویرایش وجود نخواهد داشت، لذا دقت لازم در این خصوص را داشته باشید.",
]

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


class InsuranceRuleError(ValueError):
    pass


def to_english_digits(value: str) -> str:
    return (value or "").translate(_PERSIAN_DIGITS)


def normalize_national_id(value: str) -> str:
    """۹ رقمی → با صفر ابتدایی (normalizeNationalId)."""
    text = to_english_digits(value).strip()
    return "0" + text if len(text) == 9 else text


def normalize_mobile(value: str) -> str:
    text = to_english_digits(value).strip()
    return "0" + text if len(text) == 10 and not text.startswith("0") else text


def normalize_sheba(value: str) -> str:
    text = to_english_digits(value).strip().upper()
    return re.sub(r"^IR", "", text)


def is_valid_national_id(value: str) -> bool:
    """الگوریتم کد ملی (validateNationalId در form.js)."""
    nid = normalize_national_id(value)
    if len(nid) != 10 or not nid.isdigit() or len(set(nid)) == 1:
        return False
    total = sum(int(nid[i]) * (10 - i) for i in range(9))
    rem = total % 11
    check = int(nid[9])
    return check == rem if rem < 2 else check == 11 - rem


def is_valid_jalali_date(value: str) -> bool:
    return bool(re.fullmatch(r"\d{4}/\d{2}/\d{2}", to_english_digits(value).strip()))


def is_valid_mobile(value: str) -> bool:
    return bool(re.fullmatch(r"0?9\d{9}", to_english_digits(value).strip()))


def format_jalali_compact(value: str | None) -> str:
    """«13700521» → «1370/05/21» (formatDate)؛ بقیه بدون تغییر."""
    text = to_english_digits(value or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}/{text[4:6]}/{text[6:8]}"
    return text


def needs_kafala(employee_gender: int, member_type: str) -> bool:
    """مدرک کفالت: پرسنل زن → همه اعضا؛ پرسنل مرد → فقط پدر و مادر."""
    return employee_gender == GENDER_FEMALE or member_type in ("father", "mother")


def validate_main(data: dict, employee_national_id: str) -> dict:
    """
    اعتبارسنجی شخص اصلی (save.php + validateForm). خروجی: مقادیر نرمال‌شده.
    """
    errors: list[str] = []
    required = {
        "father_name": "نام پدر",
        "birth_certificate_no": "شماره شناسنامه",
        "mobile_number": "شماره تماس",
        "marital_status": "وضعیت تاهل",
        "insurance_no": "شماره بیمه",
        "bank_code": "بانک",
        "account_number": "شماره حساب",
        "sheba": "شماره شبا",
        "account_type": "نوع حساب",
        "account_owner": "نام صاحب حساب",
        "account_owner_national_id": "کد ملی صاحب حساب",
    }
    for key, label in required.items():
        if str(data.get(key) or "").strip() == "":
            errors.append(f"فیلد {label} اجباری است.")

    owner_nid = normalize_national_id(str(data.get("account_owner_national_id") or ""))
    if owner_nid != normalize_national_id(employee_national_id or ""):
        errors.append("کد ملی صاحب حساب باید با کد ملی شخص اصلی یکسان باشد.")

    sheba = normalize_sheba(str(data.get("sheba") or ""))
    if not re.fullmatch(r"\d{24}", sheba):
        errors.append("شماره شبا باید ۲۴ رقم باشد.")

    insurance_no = to_english_digits(str(data.get("insurance_no") or "")).strip()
    if not re.fullmatch(r"\d{10}", insurance_no):
        errors.append("شماره بیمه تامین اجتماعی باید دقیقاً ۱۰ رقم باشد.")

    mobile = normalize_mobile(str(data.get("mobile_number") or ""))
    if not is_valid_mobile(mobile):
        errors.append("شماره موبایل معتبر نیست.")

    try:
        marital = int(data.get("marital_status"))
    except (TypeError, ValueError):
        marital = 0
    if marital not in (MARITAL_SINGLE, MARITAL_MARRIED):
        errors.append("وضعیت تاهل نامعتبر است.")
    try:
        bank_code = int(data.get("bank_code"))
    except (TypeError, ValueError):
        bank_code = 0
    if bank_code not in BANK_CODES:
        errors.append("بانک نامعتبر است.")
    try:
        account_type = int(data.get("account_type"))
    except (TypeError, ValueError):
        account_type = 0
    if account_type not in ACCOUNT_TYPES:
        errors.append("نوع حساب نامعتبر است.")

    if errors:
        raise InsuranceRuleError(" | ".join(errors))

    return {
        "father_name": str(data["father_name"]).strip()[:100],
        "birth_certificate_no": to_english_digits(str(data["birth_certificate_no"])).strip()[:20],
        "mobile_number": mobile[:11],
        "marital_status": marital,
        "insurance_no": insurance_no,
        "bank_code": bank_code,
        "account_number": to_english_digits(str(data["account_number"])).strip()[:40],
        "sheba": sheba,
        "account_type": account_type,
        "account_owner": str(data["account_owner"]).strip()[:200],
        "account_owner_national_id": owner_nid,
    }


def validate_members(members: list[dict], employee: dict, main_marital: int, main_mobile: str) -> list[dict]:
    """
    اعضای خانواده - همان قواعد form.js/save.php:
    - همسر فقط اگر متاهل؛ حداکثر ۱ همسر، ۱ پدر، ۱ مادر
    - جنسیت همسر برعکس فرد اصلی؛ تاهل همسر = متاهل
    - فرد اصلی مرد: نام پدر فرزندان = نام او؛ نام خانوادگی فرزندان و پدر = نام خانوادگی او
    - شماره تماس همه اعضا = شماره تماس فرد اصلی
    - کفالت (needs_kafala): انتخاب اجباری؛ «بله» → مدرک اجباری (در سرویس با وجود فایل چک می‌شود)
    """
    emp_gender = int(employee["gender"])
    counts: dict[str, int] = {}
    result: list[dict] = []
    for index, m in enumerate(members or []):
        mtype = str(m.get("member_type") or "").strip()
        cfg = MEMBER_TYPES.get(mtype)
        if cfg is None:
            raise InsuranceRuleError("نوع عضو خانواده نامعتبر است.")
        counts[mtype] = counts.get(mtype, 0) + 1
        if counts[mtype] > cfg["max_count"]:
            raise InsuranceRuleError(f"حداکثر تعداد {cfg['title']} ثبت شده است.")
        if mtype == "spouse" and main_marital != MARITAL_MARRIED:
            raise InsuranceRuleError("برای افراد مجرد امکان ثبت همسر وجود ندارد.")

        # جنسیت و تاهل
        if mtype == "spouse":
            gender = GENDER_FEMALE if emp_gender == GENDER_MALE else GENDER_MALE
            marital = MARITAL_MARRIED
        else:
            gender = cfg["gender"]
            try:
                marital = int(m.get("marital_status") or 0)
            except (TypeError, ValueError):
                marital = 0
            if marital not in (MARITAL_SINGLE, MARITAL_MARRIED):
                raise InsuranceRuleError(f"وضعیت تاهل {cfg['title']} را انتخاب کنید.")

        # نام پدر / نام خانوادگی ثابت برای فرد اصلی مرد
        father_name = str(m.get("father_name") or "").strip()
        last_name = str(m.get("last_name") or "").strip()
        if emp_gender == GENDER_MALE and mtype in ("son", "daughter"):
            father_name = employee["first_name"]
            last_name = employee["last_name"]
        if emp_gender == GENDER_MALE and mtype == "father":
            last_name = employee["last_name"]

        first_name = str(m.get("first_name") or "").strip()
        birth_date = to_english_digits(str(m.get("birth_date") or "")).strip()
        national_id = normalize_national_id(str(m.get("national_id") or ""))
        birth_cert = to_english_digits(str(m.get("birth_certificate_no") or "")).strip()

        label = cfg["title"] if cfg["max_count"] == 1 else f"{cfg['title']} {counts[mtype]}"
        if not first_name or not last_name or not father_name or not birth_cert:
            raise InsuranceRuleError(f"همه فیلدهای {label} را کامل کنید.")
        if not is_valid_jalali_date(birth_date):
            raise InsuranceRuleError(f"تاریخ تولد {label} باید به صورت ۱۳۷۰/۰۱/۰۱ باشد.")
        if not is_valid_national_id(national_id):
            raise InsuranceRuleError(f"کد ملی {label} معتبر نیست.")

        kafala = None
        if needs_kafala(emp_gender, mtype):
            kafala = str(m.get("kafala_status") or "").strip()
            if kafala not in ("yes", "no"):
                raise InsuranceRuleError(f"وضعیت تکفل {label} را مشخص کنید.")

        result.append(
            {
                "member_type": mtype,
                "relation_code": cfg["relation_code"],
                "dependency_code": cfg["dependency_code"],
                "first_name": first_name[:100],
                "last_name": last_name[:100],
                "father_name": father_name[:100],
                "birth_date": birth_date,
                "gender": gender,
                "marital_status": marital,
                "national_id": national_id,
                "birth_certificate_no": birth_cert[:20],
                "mobile_number": main_mobile,
                "kafala_status": kafala,
                "sort_order": index,
                "client_key": m.get("client_key"),
            }
        )
    return result
