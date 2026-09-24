"""
Schema های Pydantic برای «ساختار ارزیابی عملکرد»:
ورودی/خروجی endpointهای app/api/v1/endpoints/evaluation_structure.py
(سرپرست ارزیابی واحد، مدیران و اهدافشان، سرشیفت‌ها و زیرمجموعه‌ها، ساختار کامل سایت).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class EmployeeBrief(BaseModel):
    """خلاصه یک پرسنل؛ درون خروجی‌های سرپرست/مدیر/سرشیفت استفاده می‌شود."""

    id: int
    personnel_code: str
    first_name: str
    last_name: str
    department_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class SetDepartmentSupervisorIn(BaseModel):
    """بدنه درخواست تعیین سرپرست ارزیابی یک واحد."""
    employee_id: int


class DepartmentSupervisorOut(BaseModel):
    """خروجی تعیین سرپرست ارزیابی واحد."""
    department_id: int
    employee: EmployeeBrief

    model_config = ConfigDict(from_attributes=True)


class AddManagerIn(BaseModel):
    """بدنه درخواست افزودن مدیر ارزیابی به یک سایت."""
    employee_id: int
    title: str | None = None


class UpdateManagerTitleIn(BaseModel):
    """بدنه درخواست تغییر عنوان نمایشی یک مدیر."""
    title: str | None = None


class AddManagerTargetIn(BaseModel):
    """بدنه درخواست افزودن یک پرسنل به فهرست ارزیابی‌شوندگان یک مدیر."""
    target_employee_id: int


class ManagerAssignmentOut(BaseModel):
    """یک هدف ارزیابی مدیر؛ درون ManagerOut."""
    id: int
    target_employee: EmployeeBrief

    model_config = ConfigDict(from_attributes=True)


class ManagerOut(BaseModel):
    """یک مدیر همراه با فهرست کامل پرسنلی که صریحاً به او اختصاص داده شده‌اند؛ در ساختار سایت و endpointهای مدیر."""

    id: int
    site_id: int
    title: str | None
    employee: EmployeeBrief
    assignments: list[ManagerAssignmentOut]

    model_config = ConfigDict(from_attributes=True)


class ManagerCandidateOut(BaseModel):
    """
    گزینه‌های انتخابگر «افزودن به فهرست یک مدیر». علاوه بر اطلاعات پایه مشخص می‌کند:
    سرپرست کدام واحد است، الان توسط کدام مدیر ارزیابی می‌شود (برای برچسب‌گذاری، نه پنهان‌کردن)
    و آیا خودش مدیر ثبت‌شده است (تا در میان‌بر «سرپرستان بدون مدیر» پیشنهاد نشود).
    """

    id: int
    personnel_code: str
    first_name: str
    last_name: str
    department_id: int | None
    supervisor_department_name: str | None  # نام واحدی که این فرد سرپرست ارزیابی آن است
    evaluated_by_name: str | None  # نام مدیری که از قبل این فرد را ارزیابی می‌کند
    is_manager: bool


class AddShiftLeadIn(BaseModel):
    """بدنه درخواست افزودن سرشیفت به یک واحد."""
    employee_id: int


class ShiftLeadOut(BaseModel):
    """خروجی یک سرشیفت واحد."""
    id: int
    department_id: int
    employee: EmployeeBrief

    model_config = ConfigDict(from_attributes=True)


class SetShiftAssignmentIn(BaseModel):
    """بدنه درخواست قراردادن یک پرسنل زیر یک سرشیفت."""
    employee_id: int
    shift_lead_id: int


class ShiftAssignmentOut(BaseModel):
    """خروجی تخصیص یک پرسنل به سرشیفت."""
    id: int
    shift_lead_id: int
    employee: EmployeeBrief

    model_config = ConfigDict(from_attributes=True)


class DepartmentStructureOut(BaseModel):
    """ساختار کامل ارزیابی یک واحد؛ درون SiteStructureOut."""

    id: int
    name: str
    code: str
    supervisor: EmployeeBrief | None
    shift_leads: list[ShiftLeadOut]
    shift_assignments: list[ShiftAssignmentOut]


class SiteStructureOut(BaseModel):
    """ساختار کامل ارزیابی یک سایت (مدیران و واحدها) در یک پاسخ، برای رندر صفحه ساختار."""

    site_id: int
    site_name: str
    managers: list[ManagerOut]
    departments: list[DepartmentStructureOut]
