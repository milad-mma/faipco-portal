"""
Schema های Pydantic ماژول «درخواست مرخصی/ماموریت».

شامل ورودی/خروجی endpoint های ادمین (نگاشت کاراوب، نوع‌های درخواست، فهرست‌های مرجع،
تأییدکننده واحد، مسئول نیروی انسانی، وضعیت ماژول)، ثبت درخواست توسط پرسنل،
نمایش نرمالایزشده یک درخواست، تصمیم تأییدکننده و ویرایش مدیریتی.
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.services.kara_schema import LEAVE_SCHEMA_DEFAULTS, validate_schema


class EmployeeBrief(BaseModel):
    """خلاصه یک پرسنل - داخل خروجی تأییدکننده واحد و مسئول نیروی انسانی استفاده می‌شود."""

    id: int
    personnel_code: str
    first_name: str
    last_name: str

    model_config = ConfigDict(from_attributes=True)


# ---------- تنظیمات ادمین: Mapping ----------


class LeaveRequestMappingIn(BaseModel):
    """ورودی PUT /sites/{site_id}/mapping - نام جدول/ستون‌های کاراوب؛ مقادیر پیش‌فرض همان نام‌های کاراوب هستند."""

    table_name: str = "WF_Requests"
    request_id_column: str = "RequestId"
    emp_no_column: str = "Emp_No"
    submitting_date_column: str = "SubmittingDate"
    card_no_column: str = "Card_No"
    start_date_column: str = "StartDate"
    end_date_column: str = "EndDate"
    start_hour_column: str = "StartHour"
    end_hour_column: str = "EndHour"
    duration_column: str = "Duration"
    is_final_approved_column: str = "IsFinalApproved"
    approval_by_manager_column: str = "ApprovalByManagerEmp_No"
    approval_date_column: str = "ApprovalDate"
    operations_id_column: str = "OperationsID"
    description_column: str = "Description"
    cur_emp_no_column: str = "CurEmp_NO"
    manager_idea_column: str = "ManagerIdea"
    is_first_time_shift_column: str = "IsFirstTimeShift"
    persian_start_date_column: str = "PersianStartDate"
    application_id_column: str = "ApplicationId"
    source_column: str = "Source"
    destination_column: str = "Distination"
    action_id_column: str | None = "ActionId"
    action_lookup_table_name: str | None = "WF_Action"
    action_lookup_id_column: str | None = "ActionId"
    action_lookup_desc_column: str | None = "Fdesc"
    operation_lookup_table_name: str | None = "WF_OperationTypes"
    operation_lookup_id_column: str | None = "OperationId"
    operation_lookup_desc_column: str | None = "Name"
    card_lookup_table_name: str | None = "Cards"
    card_lookup_id_column: str | None = "Card_No"
    card_lookup_desc_column: str | None = "DefaultTitle"
    card_lookup_action_id_column: str | None = "WF_ActionID"
    employee_table_name: str | None = "Employee"
    employee_emp_no_column: str | None = "Emp_No"
    employee_sec_no_column: str | None = "Sec_No"
    section_table_name: str | None = "Sections"
    section_sec_no_column: str | None = "Sec_No"
    section_manager_emp_no_column: str | None = "ManagerEmp_No"
    section_parent_column: str | None = "TFather"
    wf_reviews_table_name: str | None = "WF_Reviews"
    wf_attachment_table_name: str | None = "WF_Attachment"
    wf_moveup_table_name: str | None = "WF_MoveUp"
    wf_parallel_approval_table_name: str | None = "WF_RequestParallelApproval"
    wf_reviews_request_id_column: str | None = "RequestId"
    wf_reviews_reviewed_emp_no_column: str | None = "ReviewedEmp_No"
    wf_reviews_description_column: str | None = "Description"
    wf_reviews_type_column: str | None = "ReviewType"
    wf_reviews_date_column: str | None = "ReviewDate"
    wf_reviews_show_to_personal_column: str | None = "ShowToPersonal"
    wf_reviews_approved_type_value: int | None = 4
    wf_reviews_rejected_type_value: int | None = 3
    branch_code_column: str | None = "BranchCode"
    branch_code_value: int | None = None
    application_id_value: int = 4
    # نام جدول/ستون‌های کاراوب (کلید «گروه.نقش») - هر بخش فقط اگر نگاشت شده باشد فعال است
    kara_schema: dict[str, str] = {}

    @field_validator("kara_schema", mode="before")
    @classmethod
    def _kara_schema(cls, value):
        """کلیدهای kara_schema ورودی را با فهرست مجاز LEAVE_SCHEMA_DEFAULTS اعتبارسنجی می‌کند."""
        return validate_schema(value, LEAVE_SCHEMA_DEFAULTS)


class LeaveRequestMappingOut(LeaveRequestMappingIn):
    """خروجی GET/PUT /sites/{site_id}/mapping - همان فیلدهای ورودی به‌علاوه شناسه‌ها."""

    id: int
    site_id: int

    @field_validator("kara_schema", mode="before")
    @classmethod
    def _kara_schema(cls, value):
        """در خروجی، مقدار ذخیره‌شده بدون اعتبارسنجی مجدد برگردانده می‌شود (None به دیکشنری خالی)."""
        return dict(value or {})

    model_config = ConfigDict(from_attributes=True)


# ---------- تنظیمات ادمین: نوع‌های درخواست ----------


class LeaveRequestTypeIn(BaseModel):
    """ورودی POST /sites/{site_id}/types - ساخت یک نوع درخواست جدید."""

    title: str
    is_mission: bool = False
    is_hourly: bool = False
    action_id: int | None = None
    operation_id: int | None = None
    card_no: int | None = None
    is_forgotten_punch: bool = False


class LeaveRequestTypeUpdateIn(BaseModel):
    """ورودی PUT /types/{type_id} - ویرایش جزئی؛ فقط فیلدهای غیر None اعمال می‌شوند."""

    title: str | None = None
    is_mission: bool | None = None
    is_hourly: bool | None = None
    is_active: bool | None = None
    action_id: int | None = None
    operation_id: int | None = None
    card_no: int | None = None
    is_forgotten_punch: bool | None = None


class LeaveRequestTypeOut(BaseModel):
    """خروجی نوع درخواست - در فهرست نوع‌های ادمین و فهرست نوع‌های فعال فرم پرسنل."""

    id: int
    site_id: int
    title: str
    is_mission: bool
    is_hourly: bool
    is_active: bool
    action_id: int | None
    operation_id: int | None
    card_no: int | None
    is_forgotten_punch: bool = False

    model_config = ConfigDict(from_attributes=True)


# ---------- جدول‌های مرجع کاراوب (فقط‌خواندنی) ----------


class ActionLookupItemOut(BaseModel):
    """یک ردیف WF_Action - خروجی GET /sites/{site_id}/action-lookup."""

    action_id: int
    title: str


class OperationLookupItemOut(BaseModel):
    """یک ردیف WF_OperationTypes - خروجی GET /sites/{site_id}/operation-lookup."""

    operation_id: int
    title: str


class CardLookupItemOut(BaseModel):
    """یک کارت کاراوب - خروجی GET /sites/{site_id}/card-lookup."""

    card_no: int
    title: str
    action_id: int | None = None  # ActionId متصل به کارت؛ برای پرکردن خودکار action_id نوع


# ---------- تنظیمات ادمین: تأییدکننده هر واحد ----------


class SetApproverIn(BaseModel):
    """ورودی PUT /departments/{department_id}/approver."""

    approver_employee_id: int


class LeaveRequestApproverOut(BaseModel):
    """خروجی تأییدکننده یک واحد - در فهرست تأییدکننده‌های سایت و پاسخ set_approver."""

    id: int
    department_id: int
    approver_employee: EmployeeBrief

    model_config = ConfigDict(from_attributes=True)


# ---------- تنظیمات ادمین: مسئول نیروی انسانی سایت ----------


class SetHrOfficerIn(BaseModel):
    """ورودی PUT /sites/{site_id}/hr-officer."""

    employee_id: int


class LeaveRequestModuleStatusOut(BaseModel):
    """خروجی GET/PUT /sites/{site_id}/module-status - نگاشت دارد؟ از پنل غیرفعال شده؟"""

    has_mapping: bool
    is_disabled: bool


class SetModuleDisabledIn(BaseModel):
    """ورودی PUT /sites/{site_id}/module-status."""

    is_disabled: bool


class LeaveRequestHrOfficerOut(BaseModel):
    """خروجی GET/PUT /sites/{site_id}/hr-officer."""

    id: int
    site_id: int
    employee: EmployeeBrief

    model_config = ConfigDict(from_attributes=True)


# ---------- ثبت درخواست (پرسنل) ----------


class ForgottenPunchIn(BaseModel):
    """یک تردد فراموش‌شده داخل SubmitLeaveRequestIn - ورود و خروج هر کدام تاریخ خودشان را دارند (شیفت شب)."""

    kind: str | None = None  # in | out | None (فرم پرتال یک تردد بدون تعیین ورود/خروج می‌فرستد)
    punch_date: date
    time: int  # فرمت فشرده HHMM - مثلاً 700


class SubmitLeaveRequestIn(BaseModel):
    """ورودی POST /submit - ثبت درخواست توسط پرسنل."""

    leave_type_id: int
    start_date: date
    end_date: date | None = None  # فقط برای نوع روزانه
    start_hour: int | None = None  # فرمت فشرده HHMM مثل گزارش تردد - مثلاً 1236؛ فقط نوع ساعتی
    end_hour: int | None = None
    description: str = ""
    source: str | None = None  # مبدأ/مقصد فقط برای مأموریت
    destination: str | None = None
    # فقط برای نوع «تردد فراموش‌شده» (یک یا دو تردد)
    punches: list[ForgottenPunchIn] | None = None


class SubmitLeaveRequestOut(BaseModel):
    """خروجی POST /submit - شناسه ردیف(های) ساخته‌شده در WF_Requests."""

    request_id: int
    request_ids: list[int] = []  # تردد فراموش‌شده با دو تردد، دو ردیف می‌سازد


# ---------- نمایش یک درخواست (نرمالایز‌شده) ----------


class LeaveRequestOut(BaseModel):
    """یک درخواست نرمالایزشده از WF_Requests - خروجی فهرست‌های پرسنل، تأییدکننده و گزارش مدیریتی."""

    request_id: int
    emp_no: int | None
    submitted_at: datetime | None
    start_date: datetime | None
    end_date: datetime | None
    start_hour: int | None
    end_hour: int | None
    duration: str | None
    status: str  # pending | approved | rejected
    approved_by_emp_no: int | None
    approved_at: datetime | None
    is_mission: bool
    description: str | None
    current_approver_emp_no: int | None
    manager_idea: str | None
    source: str | None
    destination: str | None
    type_id: int | None = None  # نوع پورتال که از روی ActionId/OperationsID/Card_No تشخیص داده شده
    type_title: str | None = None
    requester_name: str | None = None  # از جدول پرسنل پورتال بر اساس کد پرسنلی
    requester_department: str | None = None
    is_forgotten_punch: bool = False
    # تردد فراموش‌شده‌ای که سرپرست تأیید کرده و منتظر مسئول نیروی انسانی است
    awaiting_hr: bool = False


class DecidedLeaveRequestsPage(BaseModel):
    """یک صفحه از سوابق تصمیم‌گیری - خروجی GET /decided-by-me."""

    items: list[LeaveRequestOut]
    total: int  # تعداد کل برای صفحه‌بندی


# ---------- تصمیم‌گیری (تأییدکننده) ----------


class DecideRequestIn(BaseModel):
    """ورودی POST /{request_id}/decide - تأیید یا رد توسط تأییدکننده."""

    approved: bool
    manager_idea: str = ""  # نظر تأییدکننده؛ در WF_Reviews ذخیره می‌شود


# ---------- ویرایش مدیریتی (منابع انسانی) ----------


class AdminUpdateRequestIn(BaseModel):
    """
    ورودی PUT /sites/{site_id}/requests/{request_id} - ویرایش مدیریتی.
    فقط فیلدهای ارسال‌شده اعمال می‌شوند (exclude_unset)؛ None عمدی معنادار است
    (مثلاً is_final_approved=None یعنی برگرداندن به «در حال بررسی»).
    """

    is_final_approved: bool | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    start_hour: int | None = None
    end_hour: int | None = None
    leave_type_id: int | None = None
    manager_idea: str | None = None
    description: str | None = None
