"""
یکسان‌سازی متن جست‌وجو: کاربر با کیبورد فارسی یا عربی هم باید مقادیری را که با ارقام لاتین
(و حروف فارسی) ذخیره شده‌اند پیدا کند.

- ارقام فارسی (۰-۹) و عربی (٠-٩) ← لاتین
- «ي»، «ى» و «ك» عربی ← «ی» و «ک» فارسی
- حذف کاراکترهای نامرئی (به جز نیم‌فاصله که در نام‌های فارسی معنی دارد) و فاصله‌ی ابتدا/انتها

برای رمز عبور استفاده نمی‌شود.
"""
from __future__ import annotations

_TRANSLATION = str.maketrans(
    {
        **{fa: str(i) for i, fa in enumerate("۰۱۲۳۴۵۶۷۸۹")},
        **{ar: str(i) for i, ar in enumerate("٠١٢٣٤٥٦٧٨٩")},
        "ي": "ی",
        "ى": "ی",
        "ك": "ک",
        "​": None,
        "‍": None,
        "‎": None,
        "‏": None,
        "﻿": None,
    }
)


def normalize_search_text(value: str | None) -> str:
    """ورودی: متن خام جست‌وجو. خروجی: متن یکسان‌شده (برای None رشته‌ی خالی)."""
    if value is None:
        return ""
    return str(value).translate(_TRANSLATION).strip()
