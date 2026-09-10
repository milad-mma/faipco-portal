"""Schema های Pydantic برای «درخواست مرخصی/ماموریت»."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class EmployeeBrief(BaseModel):
    id: int
    personnel_code: str
    first_name: str
    last_name: str

    model_config = ConfigDict(from_attributes=True)


# ---------- تنظیمات ادمین: Mapping ----------


class LeaveRequestMappingIn(BaseModel):
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
    branch_code_column: str | None = "BranchCode"
    branch_code_value: int | None = None
    application_id_value: int = 4


class LeaveRequestMappingOut(LeaveRequestMappingIn):
    id: int
    site_id: int

    model_config = ConfigDict(from_attributes=True)


# ---------- تنظیمات ادمین: نوع‌های درخواست ----------


class LeaveRequestTypeIn(BaseModel):
    title: str
    is_mission: bool = False
    is_hourly: bool = False
    action_id: int | None = None


class LeaveRequestTypeUpdateIn(BaseModel):
    title: str | None = None
    is_mission: bool | None = None
    is_hourly: bool | None = None
    is_active: bool | None = None
    action_id: int | None = None


class LeaveRequestTypeOut(BaseModel):
    id: int
    site_id: int
    title: str
    is_mission: bool
    is_hourly: bool
    is_active: bool
    action_id: int | None

    model_config = ConfigDict(from_attributes=True)


# ---------- تنظیمات ادمین: تأییدکننده هر واحد ----------


class SetApproverIn(BaseModel):
    approver_employee_id: int


class LeaveRequestApproverOut(BaseModel):
    id: int
    department_id: int
    approver_employee: EmployeeBrief

    model_config = ConfigDict(from_attributes=True)


# ---------- ثبت درخواست (پرسنل) ----------


class SubmitLeaveRequestIn(BaseModel):
    leave_type_id: int
    start_date: date
    end_date: date | None = None
    start_hour: int | None = None  # فرمت فشرده مثل گزارش تردد - مثلاً 1236
    end_hour: int | None = None
    description: str = ""
    source: str | None = None
    destination: str | None = None


class SubmitLeaveRequestOut(BaseModel):
    request_id: int


# ---------- نمایش یک درخواست (نرمالایز‌شده) ----------


class LeaveRequestOut(BaseModel):
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


# ---------- تصمیم‌گیری (تأییدکننده) ----------


class DecideRequestIn(BaseModel):
    approved: bool
    manager_idea: str = ""


# ---------- ویرایش مدیریتی (منابع انسانی) ----------


class AdminUpdateRequestIn(BaseModel):
    is_final_approved: bool | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    start_hour: int | None = None
    end_hour: int | None = None
    manager_idea: str | None = None
    description: str | None = None
