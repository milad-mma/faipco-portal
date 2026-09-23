from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InsuranceMemberIn(BaseModel):
    member_type: str
    first_name: str = ""
    last_name: str = ""
    father_name: str = ""
    birth_date: str = ""
    marital_status: int | None = None
    national_id: str = ""
    birth_certificate_no: str = ""
    kafala_status: str | None = None
    # شناسه موقت سمت کلاینت برای اتصال مدرک آپلودشده قبل از ثبت نهایی
    client_key: str | None = Field(default=None, max_length=64)
    # شناسه مدرک آپلودشده (POST /insurance/documents) - برای «کفالت: بله»
    document_id: int | None = None
    # عضو موجود (ویرایش): مدرک قبلی نگه داشته شود
    id: int | None = None


class InsuranceRegistrationIn(BaseModel):
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
    id: int
    file_name: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InsuranceMemberOut(BaseModel):
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
    """اطلاعات فقط‌نمایشی شخص اصلی (از پرسنل) + آماده بودن برای ثبت‌نام."""

    personnel_code: str
    first_name: str
    last_name: str
    national_id: str | None
    mobile: str | None
    birth_date: str | None
    employment_date: str | None
    gender: int | None
    # چه چیزی کم است (تاریخ تولد/استخدام/جنسیت/کد ملی از Sync نیامده)
    missing: list[str]


class InsuranceMyStatusOut(BaseModel):
    enabled: bool
    employee: InsuranceEmployeeOut | None
    registration: InsuranceRegistrationOut | None
    rate_table: dict
    notes: list[str]
    bank_codes: dict[int, str]
    account_types: dict[int, str]
    member_types: dict[str, dict]


class InsuranceSettingsOut(BaseModel):
    enabled: bool
    rate_table: dict
    notes: list[str]


class InsuranceSettingsIn(BaseModel):
    enabled: bool | None = None
    rate_table: dict | None = None
    notes: list[str] | None = None


class InsuranceListItemOut(BaseModel):
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
    items: list[InsuranceListItemOut]
    total: int
    registered: int
    eligible: int
