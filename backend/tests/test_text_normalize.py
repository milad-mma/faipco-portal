"""تست یکسان‌سازی متن جست‌وجو (ارقام فارسی/عربی و ي/ك عربی)."""
from app.core.text_normalize import normalize_search_text


def test_persian_and_arabic_digits():
    assert normalize_search_text("۱۲۳۴۵") == "12345"
    assert normalize_search_text("٠٦٧٨٩") == "06789"
    assert normalize_search_text("کد ۴۱۳۵۰") == "کد 41350"


def test_arabic_letters_to_persian():
    assert normalize_search_text("علي كريمي") == "علی کریمی"
    assert normalize_search_text("موسى") == "موسی"


def test_invisible_chars_and_zwnj():
    assert normalize_search_text("​۱۲﻿۳ ") == "123"
    assert normalize_search_text("علی‌اکبر") == "علی‌اکبر"  # نیم‌فاصله می‌ماند


def test_empty():
    assert normalize_search_text(None) == ""
    assert normalize_search_text("  ") == ""
