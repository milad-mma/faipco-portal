"""
Schema های Pydantic برای «محتوای ارزیابی عملکرد»: دوره‌ها و فرم‌ها
(دسته‌بندی، سوال، گزینه). ورودی/خروجی endpointهای evaluation_periods.py و evaluation_forms.py.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------- دوره‌های ارزیابی ----------


class EvaluationPeriodIn(BaseModel):
    """بدنه ایجاد/ویرایش دوره ارزیابی."""
    site_id: int | None = None
    title: str
    description: str | None = None
    start_date: datetime
    end_date: datetime

    @model_validator(mode="after")
    def _validate_dates(self) -> "EvaluationPeriodIn":
        """بررسی می‌کند تاریخ پایان بعد از تاریخ شروع باشد؛ در غیر این صورت ValueError."""
        if self.end_date <= self.start_date:
            raise ValueError("تاریخ پایان باید بعد از تاریخ شروع باشد")
        return self


class EvaluationPeriodOut(EvaluationPeriodIn):
    """خروجی دوره ارزیابی در فهرست و جزئیات دوره‌ها."""
    id: int
    status: str
    created_by_user_id: int | None = None
    is_disabled: bool = False
    # تعداد ارزیابی‌های منتشرشده (انتساب‌ها) و انجام‌شده؛ فقط در فهرست دوره‌ها پر می‌شود
    assignments_total: int = 0
    assignments_completed: int = 0

    model_config = ConfigDict(from_attributes=True)


class EvaluationPeriodStatusUpdate(BaseModel):
    """بدنه تغییر وضعیت دوره یا فرم."""
    status: str


class EvaluationPeriodDisabledUpdate(BaseModel):
    """بدنه فعال/غیرفعال‌کردن یک دوره."""
    is_disabled: bool


class EvaluationPeriodDeleteIn(BaseModel):
    """بدنه حذف دوره."""
    # برای دوره‌ای که ارزیابی منتشرشده دارد: عنوان دقیق دوره به‌عنوان تأیید
    confirm_title: str | None = None


class PublishedEvaluationOut(BaseModel):
    """یک ارزیابی منتشرشده در فهرست ارزیابی‌های یک دوره (صفحه دوره‌ها)."""
    assignment_id: int
    evaluator_name: str
    evaluator_personnel_code: str | None = None
    target_name: str
    target_personnel_code: str | None = None
    form_title: str | None = None
    status: str  # not_started | draft | submitted
    total_score: float | None = None
    submitted_at: datetime | None = None


class TitleUpdateIn(BaseModel):
    """بدنه تغییر عنوان (دوره یا فرم)."""
    title: str


# ---------- گزینه‌های سوال ----------


class EvaluationQuestionOptionIn(BaseModel):
    """یک گزینه پاسخ درون بدنه ایجاد/ویرایش سوال."""
    label: str
    score: float
    sort_order: int = 0


class EvaluationQuestionOptionOut(EvaluationQuestionOptionIn):
    """خروجی گزینه پاسخ درون EvaluationQuestionOut."""
    id: int

    model_config = ConfigDict(from_attributes=True)


# ---------- سوالات ----------

# انواع سوالی که حداقل دو گزینه پاسخ لازم دارند
_OPTION_REQUIRED_TYPES = {"single_choice", "multiple_choice", "rating", "yes_no"}


class EvaluationQuestionIn(BaseModel):
    """بدنه ایجاد/ویرایش سوال در فرم‌ساز."""
    text: str
    description: str | None = None
    question_type: str
    weight: float = Field(default=0, ge=0, le=100)
    required: bool = True
    sort_order: int = 0
    is_active: bool = True
    options: list[EvaluationQuestionOptionIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_options(self) -> "EvaluationQuestionIn":
        """برای سوال‌های گزینه‌دار حداقل دو گزینه الزامی است؛ در غیر این صورت ValueError."""
        if self.question_type in _OPTION_REQUIRED_TYPES and len(self.options) < 2:
            raise ValueError(f"سوال‌های نوع «{self.question_type}» باید حداقل دو گزینه پاسخ داشته باشند")
        return self


class EvaluationQuestionOut(BaseModel):
    """خروجی سوال همراه گزینه‌ها؛ در فرم‌ساز و فرم کامل."""
    id: int
    category_id: int
    text: str
    description: str | None = None
    question_type: str
    weight: float
    required: bool
    sort_order: int
    is_active: bool
    options: list[EvaluationQuestionOptionOut]

    model_config = ConfigDict(from_attributes=True)


# ---------- دسته‌بندی‌ها ----------


class EvaluationCategoryIn(BaseModel):
    """بدنه ایجاد/ویرایش دسته‌بندی سوالات."""
    title: str
    weight: float = Field(default=0, ge=0, le=100)
    sort_order: int = 0
    is_active: bool = True


class EvaluationCategoryOut(EvaluationCategoryIn):
    """خروجی دسته‌بندی همراه سوالاتش؛ در فرم‌ساز و فرم کامل."""
    id: int
    form_id: int
    questions: list[EvaluationQuestionOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ---------- فرم‌ها ----------


class EvaluationFormIn(BaseModel):
    """بدنه ایجاد/ویرایش فرم ارزیابی."""
    site_id: int | None = None
    title: str
    description: str | None = None


class EvaluationFormOut(EvaluationFormIn):
    """خروجی خلاصه فرم در فهرست فرم‌ها."""
    id: int
    version: int
    parent_form_id: int | None = None
    status: str
    created_by_user_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class EvaluationFormFullOut(EvaluationFormOut):
    """فرم کامل همراه دسته‌بندی‌ها و سوالات؛ برای فرم‌ساز و رندر فرم ارزیابی در یک درخواست."""

    categories: list[EvaluationCategoryOut] = Field(default_factory=list)
