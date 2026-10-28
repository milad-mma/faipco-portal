"""
قواعد خالص (بدون دیتابیس) ماژول «اطلاعات بانکی» پرسنل (docs/bank-accounts.md).

- هر بانک در پنل ادمین برای هر فیلد (شماره حساب، شبا، شماره کارت) یکی از حالت‌های required / optional / hidden را دارد.
- نرمال‌سازی: ارقام فارسی/عربی به لاتین، حذف فاصله و خط تیره؛ شبا همیشه «IR» + ۲۴ رقم ذخیره می‌شود.
- اعتبارسنجی: شبا با رقم کنترل IBAN (mod 97)، شماره کارت ۱۶ رقمی با الگوریتم Luhn، شماره حساب ۵ تا ۲۰ رقم (نقطه و
  خط تیره‌ی بین ارقام مجاز است و حذف می‌شود).
"""
from __future__ import annotations

import re

FIELD_MODES = ("required", "optional", "hidden")
FIELDS = {
    "account_number": "شماره حساب",
    "sheba": "شماره شبا",
    "card_number": "شماره کارت",
}

# متن تعهدی که پرسنل قبل از اولین ثبت اطلاعات بانکی می‌پذیرد (عین متن در employee_bank_terms ذخیره می‌شود)
TERMS_TEXT = (
    "حساب‌های بانکی معرفی‌شده باید به نام خودِ پرسنل باشد. در غیر این صورت، مسئولیت هرگونه مشکل و پیامدهای ناشی از "
    "معرفی حساب متعلق به دیگران، بر عهده شخص خواهد بود."
)

_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


class BankRulesError(Exception):
    """خطای اعتبارسنجی قابل نمایش به کاربر."""


def _clean(value: str | None) -> str:
    """ارقام فارسی/عربی → لاتین و حذف فاصله، خط تیره، نقطه و نویسه‌های نامرئی."""
    if value is None:
        return ""
    text = str(value).translate(_DIGIT_MAP)
    return re.sub("[\\s\\-_./\u200c\u200e\u200f]", "", text).upper()


def normalize_sheba(value: str | None) -> str:
    """«IR» + ۲۴ رقم؛ اگر کاربر بدون IR وارد کرده باشد (۲۴ رقم) IR اضافه می‌شود. خالی → ""."""
    text = _clean(value)
    if not text:
        return ""
    if text.isdigit() and len(text) == 24:
        text = "IR" + text
    return text


def is_valid_sheba(sheba: str) -> bool:
    """IR + ۲۴ رقم با رقم کنترل درست (IBAN: چهار نویسه‌ی اول به انتها، حروف به عدد، باقی‌مانده بر ۹۷ = ۱)."""
    if not re.fullmatch(r"IR\d{24}", sheba or ""):
        return False
    rearranged = sheba[4:] + sheba[:4]
    numeric = "".join(str(int(ch, 36)) for ch in rearranged)
    return int(numeric) % 97 == 1


def normalize_card(value: str | None) -> str:
    return _clean(value)


def is_valid_card(card: str) -> bool:
    """۱۶ رقم با الگوریتم Luhn (کارت‌های شتاب)."""
    if not re.fullmatch(r"\d{16}", card or ""):
        return False
    total = 0
    for i, ch in enumerate(reversed(card)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def normalize_account(value: str | None) -> str:
    return _clean(value)


def is_valid_account(account: str) -> bool:
    return bool(re.fullmatch(r"\d{5,20}", account or ""))


def validate_mode(mode: str) -> str:
    if mode not in FIELD_MODES:
        raise BankRulesError("حالت فیلد نامعتبر است (اجباری، اختیاری یا مخفی)")
    return mode


def clean_account_data(modes: dict[str, str], data: dict) -> dict:
    """
    اطلاعات واردشده‌ی یک بانک را بر اساس حالت فیلدهای همان بانک نرمال و اعتبارسنجی می‌کند.
    modes: {"account_number": حالت, "sheba": حالت, "card_number": حالت}. فیلد مخفی ذخیره نمی‌شود (None).
    خروجی: {"account_number", "sheba", "card_number"} (رشته یا None). خطا: BankRulesError با پیام فارسی.
    """
    normalizers = {"account_number": normalize_account, "sheba": normalize_sheba, "card_number": normalize_card}
    validators = {
        "account_number": (is_valid_account, "شماره حساب باید فقط رقم و بین ۵ تا ۲۰ رقم باشد"),
        "sheba": (is_valid_sheba, "شماره شبا نامعتبر است (IR و ۲۴ رقم؛ رقم کنترل درست نیست)"),
        "card_number": (is_valid_card, "شماره کارت نامعتبر است (۱۶ رقم؛ رقم کنترل درست نیست)"),
    }
    result: dict[str, str | None] = {}
    for field, label in FIELDS.items():
        mode = modes.get(field, "hidden")
        if mode == "hidden":
            result[field] = None
            continue
        value = normalizers[field](data.get(field))
        if not value:
            if mode == "required":
                raise BankRulesError(f"{label} الزامی است")
            result[field] = None
            continue
        check, message = validators[field]
        if not check(value):
            raise BankRulesError(message)
        result[field] = value
    return result


def is_complete(modes: dict[str, str], values: dict | None) -> bool:
    """همه‌ی فیلدهای اجباریِ بانک پر شده‌اند؟ (برای «اطلاعات بانکی تکمیل نشده»)."""
    if values is None:
        return False
    return all(values.get(field) for field, mode in modes.items() if mode == "required")


def changed_fields(old: dict | None, new: dict) -> dict:
    """فیلدهای تغییرکرده: {field: [قدیم, جدید]} برای سابقه‌ی تغییرات."""
    old = old or {}
    return {f: [old.get(f), new.get(f)] for f in FIELDS if (old.get(f) or None) != (new.get(f) or None)}


def mask(value: str | None, keep: int = 4) -> str:
    """نمایش امن در سابقه: فقط چند رقم آخر (مثلاً ****1234)."""
    if not value:
        return "—"
    return "*" * max(0, len(value) - keep) + value[-keep:]
