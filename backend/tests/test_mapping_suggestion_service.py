"""
تست‌های واحد سرویس «پیشنهاد نگاشت بر اساس نام ستون»
(app/services/mapping_suggestion_service.py) - یک الگوریتم خالص بدون I/O.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.mapping_suggestion_service import suggest_column_for_field, suggest_mapping


def test_classic_attendance_table_kara():
    """جدول تردد کلاسیک با Emp_No/F_Date/F_Time - الگوی اصلی این پروژه."""
    columns = ["Emp_No", "F_Date", "F_Time", "Name", "Dept"]
    result = suggest_mapping(columns, ["personnel_code", "date", "time"])
    assert result["personnel_code"] == {"column": "Emp_No", "confidence": "بالا", "matched_keyword": "emp_no"}
    assert result["date"]["column"] == "F_Date"
    assert result["time"]["column"] == "F_Time"


def test_enter_exit_columns_mode():
    """الگوی چهار ستون جدای ورود/خروج."""
    columns = ["PersonnelCode", "EnterDate", "EnterTime", "ExitDate", "ExitTime"]
    result = suggest_mapping(columns, ["personnel_code", "enter_date", "enter_time", "exit_date", "exit_time"])
    assert result["personnel_code"]["column"] == "PersonnelCode"
    assert result["enter_date"]["column"] == "EnterDate"
    assert result["enter_time"]["column"] == "EnterTime"
    assert result["exit_date"]["column"] == "ExitDate"
    assert result["exit_time"]["column"] == "ExitTime"


def test_employee_mapping_email_and_mobile():
    columns = ["ID", "FirstName", "LastName", "Email", "MobileNumber", "PersonnelCode"]
    result = suggest_mapping(columns, ["personnel_code", "email", "mobile"])
    assert result["email"]["column"] == "Email"
    assert result["mobile"]["column"] == "MobileNumber"


def test_ambiguous_columns_get_no_false_positive():
    """
    مهم‌ترین تست: ستون‌های کاملاً بی‌معنی/کدگذاری‌شده نباید هیچ پیشنهاد
    غلطی بگیرند - سکوت (None) همیشه بهتر از یک پیشنهاد اشتباه است.
    """
    columns = ["F1", "C001", "X"]
    result = suggest_mapping(columns, ["personnel_code", "email"])
    assert result["personnel_code"] is None
    assert result["email"] is None


def test_persian_column_names():
    columns = ["کدپرسنلی", "تاریخ", "ساعت"]
    result = suggest_mapping(columns, ["personnel_code", "date", "time"])
    assert result["personnel_code"]["column"] == "کدپرسنلی"
    assert result["date"]["column"] == "تاریخ"
    assert result["time"]["column"] == "ساعت"


def test_unknown_concept_returns_none():
    assert suggest_column_for_field(["Emp_No"], "totally_unknown_concept") is None


def test_no_matching_column_returns_none():
    assert suggest_column_for_field(["RandomColumnXYZ"], "email") is None


def test_exact_match_preferred_over_substring_match():
    """
    اگر هم یک تطبیق دقیق و هم یک تطبیق جزئی (substring) وجود داشته باشد،
    تطبیق دقیق باید انتخاب شود (اختلاف طول صفر، اولویت بالاتر).
    """
    columns = ["email", "contact_email_backup"]
    result = suggest_column_for_field(columns, "email")
    assert result["column"] == "email"
