"""Schema های Pydantic برای «گزارش‌های مدیریتی ارزیابی عملکرد»."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr


class EmployeeScoreOut(BaseModel):
    first_name: str
    last_name: str
    personnel_code: str
    score: float | None


class DepartmentReportEntryOut(BaseModel):
    department_id: int
    department_name: str
    average_score: float | None
    count: int
    min_score: float | None
    max_score: float | None
    employees: list[EmployeeScoreOut]


class SitePeriodReportOut(BaseModel):
    site_id: int
    site_name: str
    period_id: int
    period_title: str
    overall_average_score: float | None
    overall_count: int
    departments: list[DepartmentReportEntryOut]


class PeriodComparisonEntryOut(BaseModel):
    department_id: int
    department_name: str
    period_a_average: float | None
    period_a_count: int
    period_b_average: float | None
    period_b_count: int


class PeriodInfoOut(BaseModel):
    id: int
    title: str
    average_score: float | None


class PeriodComparisonOut(BaseModel):
    site_id: int
    site_name: str
    period_a: PeriodInfoOut
    period_b: PeriodInfoOut
    departments: list[PeriodComparisonEntryOut]


class EmailReportIn(BaseModel):
    email: EmailStr
