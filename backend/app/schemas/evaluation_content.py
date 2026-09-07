"""Schema های Pydantic برای «محتوای ارزیابی عملکرد» - دوره‌ها و فرم‌ها."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------- دوره‌های ارزیابی ----------


class EvaluationPeriodIn(BaseModel):
    site_id: int | None = None
    title: str
    description: str | None = None
    start_date: datetime
    end_date: datetime

    @model_validator(mode="after")
    def _validate_dates(self) -> "EvaluationPeriodIn":
        if self.end_date <= self.start_date:
            raise ValueError("تاریخ پایان باید بعد از تاریخ شروع باشد")
        return self


class EvaluationPeriodOut(EvaluationPeriodIn):
    id: int
    status: str
    created_by_user_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class EvaluationPeriodStatusUpdate(BaseModel):
    status: str


class TitleUpdateIn(BaseModel):
    title: str


# ---------- گزینه‌های سوال ----------


class EvaluationQuestionOptionIn(BaseModel):
    label: str
    score: float
    sort_order: int = 0


class EvaluationQuestionOptionOut(EvaluationQuestionOptionIn):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ---------- سوالات ----------

_OPTION_REQUIRED_TYPES = {"single_choice", "multiple_choice", "rating", "yes_no"}


class EvaluationQuestionIn(BaseModel):
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
        if self.question_type in _OPTION_REQUIRED_TYPES and len(self.options) < 2:
            raise ValueError(f"سوال‌های نوع «{self.question_type}» باید حداقل دو گزینه پاسخ داشته باشند")
        return self


class EvaluationQuestionOut(BaseModel):
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
    title: str
    weight: float = Field(default=0, ge=0, le=100)
    sort_order: int = 0
    is_active: bool = True


class EvaluationCategoryOut(EvaluationCategoryIn):
    id: int
    form_id: int
    questions: list[EvaluationQuestionOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ---------- فرم‌ها ----------


class EvaluationFormIn(BaseModel):
    site_id: int | None = None
    title: str
    description: str | None = None


class EvaluationFormOut(EvaluationFormIn):
    id: int
    version: int
    parent_form_id: int | None = None
    status: str
    created_by_user_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class EvaluationFormFullOut(EvaluationFormOut):
    """نسخه کامل فرم - همراه دسته‌بندی‌ها و سوالات، برای فرم‌ساز (یک درخواست، همه‌چیز)."""

    categories: list[EvaluationCategoryOut] = Field(default_factory=list)
