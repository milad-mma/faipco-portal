"""Schema های Pydantic برای «ساختار ارزیابی عملکرد»."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class EmployeeBrief(BaseModel):
    """نمایش خلاصه یک پرسنل - برای فهرست‌های سرپرست/مدیر/سرشیفت."""

    id: int
    personnel_code: str
    first_name: str
    last_name: str
    department_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class SetDepartmentSupervisorIn(BaseModel):
    employee_id: int


class DepartmentSupervisorOut(BaseModel):
    department_id: int
    employee: EmployeeBrief

    model_config = ConfigDict(from_attributes=True)


class AddManagerIn(BaseModel):
    employee_id: int
    title: str | None = None


class UpdateManagerTitleIn(BaseModel):
    title: str | None = None


class AddManagerTargetIn(BaseModel):
    target_employee_id: int


class ManagerAssignmentOut(BaseModel):
    id: int
    target_employee: EmployeeBrief

    model_config = ConfigDict(from_attributes=True)


class ManagerOut(BaseModel):
    """
    یک «مدیر» به همراه فهرست کامل کسانی که صریحاً به او تخصیص داده
    شده‌اند - جایگزین مدل قبلی که «مدیر سایت» را از «سایر مدیران» جدا
    نگه می‌داشت؛ حالا همه‌چیز زیر یک مدیر، با اهدافش، یک‌جا نمایش داده
    می‌شود.
    """

    id: int
    site_id: int
    title: str | None
    employee: EmployeeBrief
    assignments: list[ManagerAssignmentOut]

    model_config = ConfigDict(from_attributes=True)


class ManagerCandidateOut(BaseModel):
    """
    برای انتخابگر «افزودن به فهرست یک مدیر» - علاوه بر اطلاعات پایه،
    مشخص می‌کند آیا این فرد سرپرست یک واحد است (برای بخش «سرپرستان بدون
    مدیر»)، آیا از قبل تحت ارزیابی مدیر دیگری است (برای غیرفعال‌کردن/
    برچسب‌گذاری در جست‌وجو - نه پنهان‌کردن کامل)، و آیا خودش هم یک مدیر
    ثبت‌شده است (تا در میان‌بر «سرپرستان بدون مدیر» پیشنهاد نشود - کسی
    که خودش در سطح مدیر است، سرپرست ساده‌ی آماده‌واگذاری محسوب نمی‌شود).
    """

    id: int
    personnel_code: str
    first_name: str
    last_name: str
    department_id: int | None
    supervisor_department_name: str | None
    evaluated_by_name: str | None
    is_manager: bool


class AddShiftLeadIn(BaseModel):
    employee_id: int


class ShiftLeadOut(BaseModel):
    id: int
    department_id: int
    employee: EmployeeBrief

    model_config = ConfigDict(from_attributes=True)


class SetShiftAssignmentIn(BaseModel):
    employee_id: int
    shift_lead_id: int


class ShiftAssignmentOut(BaseModel):
    id: int
    shift_lead_id: int
    employee: EmployeeBrief

    model_config = ConfigDict(from_attributes=True)


class DepartmentStructureOut(BaseModel):
    """ساختار کامل ارزیابی یک واحد - برای نمایش یک‌جا در UI."""

    id: int
    name: str
    code: str
    supervisor: EmployeeBrief | None
    shift_leads: list[ShiftLeadOut]
    shift_assignments: list[ShiftAssignmentOut]


class SiteStructureOut(BaseModel):
    """ساختار کامل ارزیابی یک سایت - یک درخواست، همه‌چیز برای رندر UI."""

    site_id: int
    site_name: str
    managers: list[ManagerOut]
    departments: list[DepartmentStructureOut]
