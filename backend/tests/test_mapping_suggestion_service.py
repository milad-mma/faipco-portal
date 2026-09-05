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


# ==============================================================================
# مرحله سوم — پیشنهاد بر اساس نمونه داده واقعی
# ==============================================================================

from app.services.mapping_suggestion_service import (  # noqa: E402
    suggest_column_from_samples,
    _looks_like_persian_date,
    _looks_like_compressed_time,
    _looks_like_email,
    _looks_like_mobile,
)


def test_persian_date_pattern_detection():
    assert _looks_like_persian_date([14050524, 14050525, 14050526]) is True
    assert _looks_like_persian_date([14051340]) is False  # ماه ۱۳ نامعتبر
    assert _looks_like_persian_date([25]) is False  # سن، نه تاریخ


def test_compressed_time_pattern_detection():
    assert _looks_like_compressed_time([618, 1401, 2359]) is True
    assert _looks_like_compressed_time([2500]) is False  # ساعت ۲۵ نامعتبر
    assert _looks_like_compressed_time([25]) is True  # یعنی ۰۰:۲۵ - معتبر


def test_email_pattern_detection():
    assert _looks_like_email(["ali@example.com", "sara@test.ir"]) is True
    assert _looks_like_email(["not-an-email", "12345"]) is False


def test_mobile_pattern_detection():
    assert _looks_like_mobile(["09123456789", "09351234567"]) is True
    assert _looks_like_mobile(["12345"]) is False


def test_sample_based_suggestion_finds_misleadingly_named_column():
    """
    مهم‌ترین سناریوی مرحله سوم: ستونی که نامش کاملاً گمراه‌کننده/مبهم
    است (پس مرحله دوم چیزی پیدا نمی‌کند)، ولی مقادیر واقعی‌اش الگوی
    مشخصی دارند - باید از روی همان مقادیر پیدا شود.
    """
    columns_with_samples = {
        "WeirdColumnName": [14050524, 14050525, 14050526, 14050527, 14050528],
        "AnotherOne": ["ali@company.com", "sara@company.com"],
    }
    result_date = suggest_column_from_samples(columns_with_samples, "date")
    assert result_date["column"] == "WeirdColumnName"
    assert result_date["source"] == "نمونه داده"

    result_email = suggest_column_from_samples(columns_with_samples, "email")
    assert result_email["column"] == "AnotherOne"


def test_personnel_code_never_guessed_from_samples():
    """
    یک عدد صحیح ساده (کد پرسنلی) از روی مقادیرش به‌تنهایی از هر ستون
    عددی دیگری (سن، کد واحد) قابل‌تشخیص نیست - این تابع باید همیشه
    None برگرداند، نه یک حدس نامطمئن.
    """
    columns_with_samples = {"SomeNumericColumn": [101, 102, 103, 104, 105]}
    assert suggest_column_from_samples(columns_with_samples, "personnel_code") is None


# ==============================================================================
# پوشش کامل مفاهیم - طبق بازخورد صریح، فقط ایمیل/موبایل/تردد قبلاً
# پوشش داده می‌شد؛ این تست‌ها همه فیلدهای EmployeeMapping و جدول‌های
# جدا (مرجع، عکس، تقویم) را هم تأیید می‌کنند.
# ==============================================================================


def test_full_employee_mapping_all_fields():
    columns = [
        "Emp_No", "NationalCode", "FirstName", "LastName", "Mobile", "Email",
        "BirthDate", "IsActive", "DeptCode", "PositionCode",
    ]
    concepts = [
        "personnel_code", "national_code", "first_name", "last_name", "mobile", "email",
        "birth_date", "is_active", "department", "position",
    ]
    result = suggest_mapping(columns, concepts)
    assert result["national_code"]["column"] == "NationalCode"
    assert result["first_name"]["column"] == "FirstName"
    assert result["last_name"]["column"] == "LastName"
    assert result["birth_date"]["column"] == "BirthDate"
    assert result["is_active"]["column"] == "IsActive"
    assert result["department"]["column"] == "DeptCode"
    assert result["position"]["column"] == "PositionCode"


def test_lookup_table_id_and_name():
    """جدول مرجع (دپارتمان/سمت و مشابه) - مفاهیم عمومی lookup_id/lookup_name."""
    columns = ["ID", "Name", "ExtraField"]
    result = suggest_mapping(columns, ["lookup_id", "lookup_name"])
    assert result["lookup_id"]["column"] == "ID"
    assert result["lookup_name"]["column"] == "Name"


def test_calendar_table_year_and_month():
    columns = ["Year", "Month", "D1", "D2", "D3"]
    result = suggest_mapping(columns, ["calendar_year", "calendar_month"])
    assert result["calendar_year"]["column"] == "Year"
    assert result["calendar_month"]["column"] == "Month"


def test_photo_table_emp_no_and_thumbnail():
    columns = ["Emp_No", "Thumbnail", "FullPhoto"]
    result = suggest_mapping(columns, ["photo_emp_no", "photo_thumbnail"])
    assert result["photo_emp_no"]["column"] == "Emp_No"
    assert result["photo_thumbnail"]["column"] == "Thumbnail"
