"""
قواعد خالص شماره‌گذاری دبیرخانه (سند مرجع بخش ۷):
- الگو `{prefix}/{yyyy}/{seq:06}` — مثال `01/1405/000125`
- پیشوند: ۱ تا ۱۰ نویسه، فقط رقم و حروف لاتین؛ یکتا بین دبیرخانه‌ها (یکتایی در دیتابیس)؛ پس از اولین شماره قفل.
"""
from __future__ import annotations

import re

PREFIX_RE = re.compile(r"^[A-Za-z0-9]{1,10}$")
NUMBER_RE = re.compile(r"^([A-Za-z0-9]{1,10})/(\d{4})/(\d{6,})$")


class NumberingError(ValueError):
    """خطای قابل نمایش."""


def clean_prefix(value: str | None) -> str:
    v = (value or "").strip()
    if not PREFIX_RE.match(v):
        raise NumberingError("پیشوند باید ۱ تا ۱۰ نویسه و فقط رقم یا حروف لاتین باشد (بدون / و فاصله)")
    return v


def format_number(prefix: str, jalali_year: int, seq: int) -> str:
    if seq < 1:
        raise NumberingError("شماره‌ی ترتیبی نامعتبر است")
    if not 1300 <= jalali_year <= 1999:
        raise NumberingError("سال شمسی نامعتبر است")
    return f"{clean_prefix(prefix)}/{jalali_year}/{seq:06d}"


def parse_number(number: str) -> tuple[str, int, int] | None:
    m = NUMBER_RE.match((number or "").strip())
    if not m:
        return None
    return m.group(1), int(m.group(2)), int(m.group(3))


MISSING_PREFIX_MESSAGE = "پیشوند شماره‌ی دبیرخانه‌ی این سایت در تنظیمات اتوماسیون تعیین نشده است"
