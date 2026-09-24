"""
Schema های Pydantic برای «گزارش‌های مدیریتی ارزیابی عملکرد»: گزارش سایت/دوره،
مقایسه دو دوره، روند فردی و ارسال گزارش با ایمیل. خروجی endpointهای evaluation_reports.py.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr


class EmployeeScoreOut(BaseModel):
    """امتیاز یک پرسنل در گزارش دوره؛ درون DepartmentReportEntryOut."""
    first_name: str
    last_name: str
    personnel_code: str
    score: float | None
    evaluation_id: int | None = None  # برای Drill-down جزئیات سوال‌به‌سوال


class DepartmentReportEntryOut(BaseModel):
    """آمار یک واحد در گزارش دوره (میانگین، کمینه، بیشینه و فهرست پرسنل)."""
    department_id: int
    department_name: str
    average_score: float | None
    count: int
    min_score: float | None
    max_score: float | None
    employees: list[EmployeeScoreOut]


class SitePeriodReportOut(BaseModel):
    """گزارش کامل یک دوره برای یک سایت، تفکیک‌شده بر اساس واحد."""
    site_id: int
    site_name: str
    period_id: int
    period_title: str
    overall_average_score: float | None
    overall_count: int
    departments: list[DepartmentReportEntryOut]


class EmployeeComparisonOut(BaseModel):
    """امتیاز یک پرسنل در هر دو دوره؛ زیر هر واحد در «مقایسه دوره‌ها»."""

    first_name: str
    last_name: str
    personnel_code: str
    period_a_score: float | None
    period_a_evaluation_id: int | None = None
    period_b_score: float | None
    period_b_evaluation_id: int | None = None


class PeriodComparisonEntryOut(BaseModel):
    """مقایسه میانگین و تعداد یک واحد در دو دوره؛ درون PeriodComparisonOut."""
    department_id: int
    department_name: str
    period_a_average: float | None
    period_a_count: int
    period_b_average: float | None
    period_b_count: int
    employees: list[EmployeeComparisonOut] = []


class PeriodInfoOut(BaseModel):
    """شناسه، عنوان و میانگین کل یک دوره در گزارش مقایسه."""
    id: int
    title: str
    average_score: float | None


class PeriodComparisonOut(BaseModel):
    """گزارش مقایسه دو دوره برای یک سایت."""
    site_id: int
    site_name: str
    period_a: PeriodInfoOut
    period_b: PeriodInfoOut
    departments: list[PeriodComparisonEntryOut]


class EmailReportIn(BaseModel):
    """بدنه درخواست ارسال گزارش Excel به یک ایمیل."""
    email: EmailStr


class EmployeeTrendPointOut(BaseModel):
    """امتیاز یک نفر در یک دوره؛ یک نقطه از نمودار روند فردی."""

    period_id: int
    period_title: str
    score: float | None
    evaluation_id: int | None = None
    submitted_at: datetime | None = None


class EmployeeTrendOut(BaseModel):
    """گزارش روند فردی: سیر امتیاز یک نفر در همه دوره‌ها همراه میانگین، بهترین و بدترین امتیاز."""

    first_name: str
    last_name: str
    personnel_code: str
    points: list[EmployeeTrendPointOut] = []
    average_score: float | None = None
    best_score: float | None = None
    worst_score: float | None = None
