"""مدل‌های ورودی/خروجی API بیمه تکمیلی."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InsuranceMemberIn(BaseModel):
    """یک عضو خانواده در فرم ثبت‌نام (مقادیر خام؛ نرمال‌سازی در insurance_rules)."""

    member_type: str
    first_name: str = ""
    last_name: str = ""
    father_name: str = ""
    birth_date: str = ""
    marital_status: int | None = None
    national_id: str = ""
    birth_certificate_no: str = ""
    kafala_status: str | None = None  # yes / no / None
    client_key: str | None = Field(default=None, max_length=64)  # شناسه موقت سمت فرم (استفاده نمی‌شود، برای سازگاری)
    document_id: int | None = None  # شناسه مدرک آپلودشده؛ برای «تکفل: بله» الزامی
    id: int | None = None  # شناسه عضو قبلی هنگام ویرایش


class InsuranceRegistrationIn(BaseModel):
    """بدنه ثبت/ویرایش ثبت‌نام: فیلدهای قابل ویرایش شخص اصلی + فهرست کامل اعضا."""

    father_name: str = ""
    birth_certificate_no: str = ""
    mobile_number: str = ""
    marital_status: int | None = None
    insurance_no: str = ""
    bank_code: int | None = None
    account_number: str = ""
    sheba: str = ""
    account_type: int | None = None
    account_owner: str = ""
    account_owner_national_id: str = ""
    members: list[InsuranceMemberIn] = []


class InsuranceDocumentOut(BaseModel):
    """مشخصات یک مدرک (بدون محتوای فایل)."""

    id: int
    file_name: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InsuranceMemberOut(BaseModel):
    """یک عضو خانواده همراه مدرکش، برای نمایش/ویرایش."""

    id: int
    member_type: str
    relation_code: int
    dependency_code: int
    first_name: str
    last_name: str
    father_name: str
    birth_date: str
    gender: int
    marital_status: int
    national_id: str
    birth_certificate_no: str
    mobile_number: str
    kafala_status: str | None
    document: InsuranceDocumentOut | None = None

    model_config = ConfigDict(from_attributes=True)


class InsuranceRegistrationOut(BaseModel):
    """ثبت‌نام کامل یک پرسنل با اعضا."""

    id: int
    employee_id: int
    personnel_code: str
    first_name: str
    last_name: str
    father_name: str
    birth_date: str
    gender: int
    marital_status: int
    national_id: str
    birth_certificate_no: str
    mobile_number: str
    employment_date: str
    insurance_no: str
    bank_code: int
    account_number: str
    sheba: str
    account_type: int
    account_owner: str
    account_owner_national_id: str
    created_at: datetime
    updated_at: datetime
    members: list[InsuranceMemberOut] = []

    model_config = ConfigDict(from_attributes=True)


class InsuranceEmployeeOut(BaseModel):
    """اطلاعات فقط‌نمایشی شخص اصلی (از جدول پرسنل) و فهرست فیلدهایی که هنوز از کاراوب نیامده‌اند."""

    personnel_code: str
    first_name: str
    last_name: str
    national_id: str | None
    mobile: str | None
    birth_date: str | None
    employment_date: str | None
    gender: int | None
    missing: list[str]  # نام فیلدهای خالی (مثلاً «تاریخ استخدام»)؛ خالی = آماده ثبت‌نام


class InsuranceMyStatusOut(BaseModel):
    """همه چیزی که صفحه ثبت‌نام پرسنل لازم دارد: وضعیت ماژول، پرسنل، ثبت‌نام قبلی، نرخ‌ها، فهرست‌ها."""

    enabled: bool
    employee: InsuranceEmployeeOut | None
    registration: InsuranceRegistrationOut | None
    rate_table: dict
    notes: list[str]
    bank_codes: dict[int, str]
    account_types: dict[int, str]
    member_types: dict[str, dict]


class InsuranceSettingsOut(BaseModel):
    """تنظیمات ماژول: فعال بودن، جدول نرخ، توضیحات."""

    enabled: bool
    rate_table: dict
    notes: list[str]


class InsuranceSettingsIn(BaseModel):
    """به‌روزرسانی جزئی تنظیمات؛ فقط فیلدهای ارسالی تغییر می‌کنند."""

    enabled: bool | None = None
    rate_table: dict | None = None
    notes: list[str] | None = None


class InsuranceListItemOut(BaseModel):
    """یک ردیف فهرست مدیریتی ثبت‌نام‌ها."""

    id: int
    employee_id: int
    personnel_code: str
    first_name: str
    last_name: str
    national_id: str
    mobile_number: str
    site_id: int | None
    site_name: str | None
    department_name: str | None
    members_count: int
    documents_count: int
    created_at: datetime
    updated_at: datetime


class InsuranceListOut(BaseModel):
    """فهرست صفحه‌بندی‌شده + آمار: تعداد ثبت‌نام‌شده و تعداد پرسنل فعال."""

    items: list[InsuranceListItemOut]
    total: int
    registered: int
    eligible: int
