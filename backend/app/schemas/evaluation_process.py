"""Schema های Pydantic برای «جریان انجام ارزیابی»."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GenerateAssignmentsIn(BaseModel):
    form_id: int


class GenerateAssignmentsOut(BaseModel):
    created_count: int
    total_assignments: int


class EmployeeBriefOut(BaseModel):
    id: int
    personnel_code: str
    first_name: str
    last_name: str

    model_config = ConfigDict(from_attributes=True)


class MyEvaluationItemOut(BaseModel):
    assignment_id: int
    target: EmployeeBriefOut
    period_title: str
    form_title: str
    evaluation_id: int | None
    status: str  # not_started | draft | submitted


class AnswerIn(BaseModel):
    question_id: int
    selected_option_ids: list[int] | None = None
    text_value: str | None = None
    number_value: float | None = None
    date_value: datetime | None = None
    comment: str | None = None


class SaveAnswersIn(BaseModel):
    answers: list[AnswerIn] = Field(default_factory=list)


class AnswerOut(BaseModel):
    id: int
    question_id: int | None
    question_text_snapshot: str
    question_type_snapshot: str
    selected_option_ids: list[int] | None
    text_value: str | None
    number_value: float | None
    date_value: datetime | None
    score: float | None
    comment: str | None

    model_config = ConfigDict(from_attributes=True)


class EvaluationOut(BaseModel):
    id: int
    assignment_id: int
    form_id: int
    status: str
    total_score: float | None
    comment: str | None
    submitted_at: datetime | None
    evaluator_name_snapshot: str
    target_name_snapshot: str
    site_name_snapshot: str
    department_name_snapshot: str | None
    form_title_snapshot: str
    answers: list[AnswerOut]

    model_config = ConfigDict(from_attributes=True)


class EvaluationResultOut(BaseModel):
    """برای «نتایج ارزیابی من» - همان Evaluation، بدون فهرست کامل پاسخ‌ها."""

    id: int
    total_score: float | None
    submitted_at: datetime | None
    evaluator_name_snapshot: str
    form_title_snapshot: str
    site_name_snapshot: str
    department_name_snapshot: str | None
    comment: str | None

    model_config = ConfigDict(from_attributes=True)


class DashboardSummaryOut(BaseModel):
    average_score: float | None
    latest_score: float | None
    results_count: int
    pending_to_evaluate_count: int
