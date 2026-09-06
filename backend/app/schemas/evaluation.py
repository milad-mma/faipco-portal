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


class AddSiteManagerIn(BaseModel):
    employee_id: int


class SiteManagerOut(BaseModel):
    id: int
    site_id: int
    employee: EmployeeBrief

    model_config = ConfigDict(from_attributes=True)


class AddOtherManagerIn(BaseModel):
    employee_id: int


class OtherManagerOut(BaseModel):
    id: int
    site_id: int
    employee: EmployeeBrief

    model_config = ConfigDict(from_attributes=True)


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
    site_managers: list[SiteManagerOut]
    other_managers: list[OtherManagerOut]
    departments: list[DepartmentStructureOut]
