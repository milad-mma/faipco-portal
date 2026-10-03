"""مدل‌های ورودی/خروجی API «مشخصات خانوادگی»."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------- ورودی فرم کارمند ----------


class FamilyMemberIn(BaseModel):
    """همسر یا یک فرزند؛ مقادیر خام (نرمال‌سازی و اعتبارسنجی در core/family_rules)."""

    member_type: str
    first_name: str = ""
    last_name: str = ""
    father_name: str | None = None
    national_id: str | None = None
    birth_certificate_no: str | None = None
    birth_date: str | None = None
    marriage_certificate_no: str | None = None
    mobile: str | None = None
    is_employed: bool | None = None
    employer_name: str | None = None
    is_insured: bool | None = None
    receives_child_allowance: bool | None = None
    is_disabled: bool | None = None
    relation: str | None = None
    other_parent_name: str | None = None
    custody: str | None = None
    is_student: bool | None = None
    education_level: str | None = None
    school_name: str | None = None
    is_married: bool | None = None
    marriage_date: str | None = None
    student_cert_expiry: str | None = None
    document_ids: list[int] = Field(default_factory=list, max_length=20)


class FamilyProfileIn(BaseModel):
    """بدنه ثبت فرم: جایگزینی کامل پرونده و اعضا؛ document_ids = مدارک کل پرونده."""

    marital_status: str | None = None
    marriage_date: str | None = None
    separation_date: str | None = None
    is_head_of_household: bool | None = None
    has_children: bool | None = None
    document_ids: list[int] = Field(default_factory=list, max_length=20)
    members: list[FamilyMemberIn] = Field(default_factory=list, max_length=20)


# ---------- خروجی ----------


class FamilyDocumentOut(BaseModel):
    id: int
    doc_type: str
    file_name: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime
    uploaded_jalali: str | None = None
    expires_on: str | None = None  # بر اساس دوره تمدید تنظیمات
    expired: bool = False

    model_config = ConfigDict(from_attributes=True)


class FamilyMemberOut(BaseModel):
    id: int
    member_type: str
    first_name: str
    last_name: str
    father_name: str | None = None
    national_id: str | None = None
    birth_certificate_no: str | None = None
    birth_date: str | None = None
    marriage_certificate_no: str | None = None
    mobile: str | None = None
    is_employed: bool | None = None
    employer_name: str | None = None
    is_insured: bool | None = None
    receives_child_allowance: bool | None = None
    is_disabled: bool | None = None
    relation: str | None = None
    other_parent_name: str | None = None
    custody: str | None = None
    is_student: bool | None = None
    education_level: str | None = None
    school_name: str | None = None
    is_married: bool | None = None
    marriage_date: str | None = None
    student_cert_expiry: str | None = None
    documents: list[FamilyDocumentOut] = []


class FamilyProfileOut(BaseModel):
    """پرونده‌ی جاری (آخرین نسخه‌ی ثبت‌شده توسط کارمند)."""

    id: int
    status: str
    marital_status: str | None = None
    marriage_date: str | None = None
    separation_date: str | None = None
    is_head_of_household: bool | None = None
    has_children: bool | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    effective_date: str | None = None
    approved_at: datetime | None = None
    documents: list[FamilyDocumentOut] = []  # مدارک کل پرونده (بدون مدارک اعضا)
    unlinked_documents: list[FamilyDocumentOut] = []  # آپلودشده ولی هنوز در فرم ثبت نشده
    members: list[FamilyMemberOut] = []


class FamilyMyStatusOut(BaseModel):
    enabled: bool
    can_edit: bool
    lock_reason: str | None = None
    employee: dict | None = None  # {first_name, last_name, personnel_code, gender}
    profile: FamilyProfileOut | None = None
    form: dict  # تنظیمات فیلدها/مدارک/نکات + فهرست گزینه‌ها برای ساخت فرم


class FamilyListItemOut(BaseModel):
    profile_id: int | None = None
    employee_id: int
    personnel_code: str
    first_name: str
    last_name: str
    site_id: int | None = None
    site_name: str | None = None
    department_name: str | None = None
    status: str  # none = فرم ثبت نشده
    marital_status: str | None = None
    sons: int = 0
    daughters: int = 0
    insurance_days: int | None = None
    marriage_eligible: bool | None = None
    eligible_children: int | None = None
    has_pending_changes: bool = False
    warnings: list[str] = []
    effective_date: str | None = None
    submitted_at: datetime | None = None


class FamilyListOut(BaseModel):
    items: list[FamilyListItemOut]
    total: int
    stats: dict


class FamilyDetailOut(BaseModel):
    employee: dict
    profile: FamilyProfileOut
    insurance_days: int | None = None
    hr_note: str | None = None
    approved_data: dict | None = None
    evaluation_current: dict  # شمول بر اساس نسخه‌ی جاری (برای بررسی قبل از تأیید)
    evaluation_approved: dict | None = None  # شمول بر اساس نسخه‌ی تأییدشده
    missing_documents: list[str] = []
    warnings: list[str] = []
    logs: list[dict] = []


class FamilyApproveIn(BaseModel):
    effective_date: str | None = Field(default=None, max_length=10)
    note: str | None = Field(default=None, max_length=2000)


class FamilyReviewNoteIn(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


class FamilyHrFieldsIn(BaseModel):
    insurance_days: int | None = Field(default=None, ge=0, le=20000)
    hr_note: str | None = Field(default=None, max_length=4000)
    clear_insurance_days: bool = False


class FamilySettingsIn(BaseModel):
    """فقط کلیدهای ارسال‌شده اعمال می‌شوند (ادغام در family_rules.merge_settings)."""

    enabled: bool | None = None
    lock_after_approval: bool | None = None
    notes: list[str] | None = None
    fields: dict[str, str] | None = None
    documents: dict[str, dict] | None = None
    rules: dict[str, dict] | None = None
    alerts: dict[str, int | None] | None = None
