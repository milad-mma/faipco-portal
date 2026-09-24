"""
Schema های Pydantic برای «جریان انجام ارزیابی»: تولید انتساب‌ها، فهرست ارزیابی‌های من،
ذخیره پاسخ‌ها، نمایش ارزیابی/نتیجه و خلاصه داشبورد. ورودی/خروجی endpointهای evaluation_process.py.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GenerateAssignmentsIn(BaseModel):
    """بدنه درخواست تولید انتساب‌های یک دوره با یک فرم."""
    form_id: int


class GenerateAssignmentsOut(BaseModel):
    """نتیجه تولید انتساب‌ها: تعداد جدیدها و کل انتساب‌های دوره."""
    created_count: int
    total_assignments: int


class EmployeeBriefOut(BaseModel):
    """خلاصه پرسنل ارزیابی‌شونده؛ درون MyEvaluationItemOut."""
    id: int
    personnel_code: str
    first_name: str
    last_name: str

    model_config = ConfigDict(from_attributes=True)


class MyEvaluationItemOut(BaseModel):
    """یک ردیف در فهرست «ارزیابی‌هایی که من باید انجام دهم»."""
    assignment_id: int
    target: EmployeeBriefOut
    period_title: str
    form_title: str
    evaluation_id: int | None  # None یعنی ارزیابی هنوز شروع نشده
    status: str  # not_started | draft | submitted
    was_edited: bool = False
    total_score: float | None = None


class AnswerIn(BaseModel):
    """پاسخ یک سوال درون SaveAnswersIn؛ بسته به نوع سوال فقط یکی از فیلدهای مقدار پر می‌شود."""
    question_id: int
    selected_option_ids: list[int] | None = None
    text_value: str | None = None
    number_value: float | None = None
    date_value: datetime | None = None
    comment: str | None = None


class SaveAnswersIn(BaseModel):
    """بدنه ذخیره پیش‌نویس/ثبت پاسخ‌های یک ارزیابی."""
    answers: list[AnswerIn] = Field(default_factory=list)


class AnswerOptionOut(BaseModel):
    """یک گزینه ممکن برای سوال همراه با انتخاب‌شدن یا نشدنش، تا همه گزینه‌های موجود نمایش داده شوند."""

    id: int
    label: str
    score: float
    is_selected: bool


class AnswerOut(BaseModel):
    """پاسخ کامل یک سوال (شامل نظر ارزیاب)؛ برای ارزیاب و گزارش‌های مدیریتی."""
    id: int
    question_id: int | None
    question_text_snapshot: str
    question_type_snapshot: str
    selected_option_ids: list[int] | None
    selected_option_labels: list[str] = []
    available_options: list[AnswerOptionOut] = []
    text_value: str | None
    number_value: float | None
    date_value: datetime | None
    score: float | None
    comment: str | None

    model_config = ConfigDict(from_attributes=True)


class MyAnswerOut(BaseModel):
    """
    پاسخ یک سوال برای نمایش به خودِ پرسنل ارزیابی‌شده؛ فیلد comment (نظر خصوصی ارزیاب)
    را ندارد. جدا از AnswerOut تعریف شده تا فیلدهای جدید AnswerOut به پرسنل نشت نکنند.
    """

    id: int
    question_text_snapshot: str
    question_type_snapshot: str
    selected_option_ids: list[int] | None
    selected_option_labels: list[str] = []
    available_options: list[AnswerOptionOut] = []
    text_value: str | None
    number_value: float | None
    date_value: datetime | None
    score: float | None

    model_config = ConfigDict(from_attributes=True)


class EvaluationOut(BaseModel):
    """ارزیابی کامل همراه پاسخ‌ها؛ خروجی شروع/ذخیره/ثبت و بازکردن ارزیابی توسط ارزیاب."""
    id: int
    assignment_id: int
    form_id: int
    status: str
    total_score: float | None
    comment: str | None
    submitted_at: datetime | None
    was_edited: bool
    evaluator_name_snapshot: str
    target_name_snapshot: str
    site_name_snapshot: str
    department_name_snapshot: str | None
    form_title_snapshot: str
    period_title_snapshot: str
    answers: list[AnswerOut]

    model_config = ConfigDict(from_attributes=True)


class EvaluationResultOut(BaseModel):
    """یک ردیف «نتایج ارزیابی من»؛ همان Evaluation بدون فهرست پاسخ‌ها."""

    id: int
    total_score: float | None
    submitted_at: datetime | None
    evaluator_name_snapshot: str
    form_title_snapshot: str
    period_title_snapshot: str
    site_name_snapshot: str
    department_name_snapshot: str | None
    comment: str | None
    was_edited: bool

    model_config = ConfigDict(from_attributes=True)


class DashboardSummaryOut(BaseModel):
    """خلاصه ارزیابی کاربر برای داشبورد: میانگین، آخرین امتیاز و تعداد موارد در انتظار."""
    average_score: float | None
    latest_score: float | None
    results_count: int
    pending_to_evaluate_count: int


class YearlyAverageOut(BaseModel):
    """میانگین امتیاز کاربر در یک سال شمسی (نمودار سالانه)."""
    jalali_year: int
    average_score: float | None
    count: int


class ShiftLeadEvaluationOut(BaseModel):
    """ارزیابی‌های ثبت‌شده توسط سرشیفت‌های واحد، برای مشاهده/ویرایش توسط سرپرست."""

    evaluation_id: int
    assignment_id: int
    shift_lead_name: str
    target_name: str
    period_title: str
    form_title: str
    total_score: float | None
    was_edited: bool
    submitted_at: datetime | None
