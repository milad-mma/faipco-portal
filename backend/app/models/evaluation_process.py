"""
مدل‌های «جریان انجام ارزیابی» - سومین لایه سیستم ارزیابی عملکرد، روی دو
لایه قبلی سوار می‌شود:
    app/models/evaluation.py         -> چه کسی مجاز به ارزیابی چه کسی است
    app/models/evaluation_content.py -> چه چیزی پرسیده می‌شود، در چه دوره‌ای
    app/models/evaluation_process.py -> همین فایل: خودِ عمل ارزیابی‌کردن

سه مدل:
    EvaluationAssignment: «X باید Y را برای دوره P با فرم F ارزیابی کند»
        - تولید می‌شود از get_evaluation_targets (مرحله اول) + دوره فعال
    Evaluation: خودِ فرم پرشده - با Historical Snapshot کامل (طبق اصل
        غیرقابل‌مذاکره این پروژه: تغییرات بعدی پرسنل/واحد/فرم نباید
        ارزیابی‌های قبلی را خراب کند)
    EvaluationAnswer: پاسخ هر سوال - با Snapshot متن/نوع سوال (طبق همان اصل)
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class EvaluationAssignmentStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"


class EvaluationAssignment(Base, TimestampMixin):
    """
    «فلان کارمند باید فلان کارمند دیگر را برای این دوره، با این فرم،
    ارزیابی کند» - تولید خودکار از get_evaluation_targets (مرحله اول)
    برای دوره‌ای که Admin مشخص کرده (POST .../generate-assignments).

    ⚠️ جلوگیری از Duplicate: طبق اصل صریح پروژه (بخش ۲۸ طرح اولیه)، یک
    ارزیاب نباید یک فرد را در یک ترکیب دوره+فرم بیش از یک‌بار ارزیابی
    کند - با UniqueConstraint تضمین می‌شود.
    """

    __tablename__ = "evaluation_assignments"
    __table_args__ = (
        UniqueConstraint(
            "period_id", "form_id", "evaluator_employee_id", "target_employee_id", name="uq_evaluation_assignment"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("evaluation_periods.id", ondelete="CASCADE"), nullable=False)
    form_id: Mapped[int] = mapped_column(ForeignKey("evaluation_forms.id", ondelete="CASCADE"), nullable=False)
    evaluator_employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    target_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[EvaluationAssignmentStatus] = mapped_column(
        Enum(EvaluationAssignmentStatus, name="evaluation_assignment_status"),
        default=EvaluationAssignmentStatus.pending,
        nullable=False,
    )

    period: Mapped["EvaluationPeriod"] = relationship()  # noqa: F821
    form: Mapped["EvaluationForm"] = relationship()  # noqa: F821
    evaluator_employee: Mapped["Employee"] = relationship(foreign_keys=[evaluator_employee_id])  # noqa: F821
    target_employee: Mapped["Employee"] = relationship(foreign_keys=[target_employee_id])  # noqa: F821


class EvaluationStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"


class Evaluation(Base, TimestampMixin):
    """
    خودِ فرم پرشده برای یک Assignment مشخص - حداکثر یکی به‌ازای هر
    Assignment (assignment_id یکتا).

    ⚠️ Historical Snapshot (اصل غیرقابل‌مذاکره این پروژه): چون Employee
    توسط Sync Engine مرتب تغییر می‌کند (واحد/سمت/حتی نام)، اطلاعات لحظه
    Submit همیشه جداگانه نگه داشته می‌شوند - گزارش یک ارزیابی قدیمی هرگز
    نباید بر اثر تغییرات بعدی سازمانی خراب شود.
    """

    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_assignments.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[EvaluationStatus] = mapped_column(
        Enum(EvaluationStatus, name="evaluation_status"), default=EvaluationStatus.draft, nullable=False
    )
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text(), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    was_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- Historical Snapshot - در لحظه شروع/Submit پر می‌شود، بعداً تغییر نمی‌کند ---
    evaluator_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    evaluator_personnel_code_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    target_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    target_personnel_code_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    site_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    department_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    form_title_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    period_title_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)

    assignment: Mapped["EvaluationAssignment"] = relationship()
    answers: Mapped[list["EvaluationAnswer"]] = relationship(
        back_populates="evaluation", cascade="all, delete-orphan"
    )

    @property
    def form_id(self) -> int:
        """
        ⚠️ برای اینکه Frontend بعد از start_evaluation بداند کدام فرم
        (با چه دسته‌بندی/سوال/گزینه‌هایی) را باید رندر کند - بدون این،
        مجبور بود جداگانه Assignment را هم Query کند. این یک ستون
        دیتابیسی جدید نیست - فقط یک میان‌بر پایتونی به assignment.form_id
        (که باید از قبل selectinload شده باشد، وگرنه همان خطای
        MissingGreenlet را می‌دهد).
        """
        return self.assignment.form_id


class EvaluationAnswer(Base, TimestampMixin):
    """
    پاسخ یک سوال مشخص درون یک Evaluation.

    ⚠️ Question Versioning ساده (طبق تصمیم قبلی پروژه - بخش ۴۶ طرح
    اولیه): به‌جای یک سیستم Versioning جداگانه برای سوالات، متن/نوع سوال
    در لحظه پاسخ‌دادن Snapshot می‌شود - اگر بعداً متن سوال تغییر کند،
    این ارزیابی قبلی همچنان متن قدیمی را نشان می‌دهد.
    """

    __tablename__ = "evaluation_answers"
    __table_args__ = (UniqueConstraint("evaluation_id", "question_id", name="uq_evaluation_answer_question"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_questions.id", ondelete="SET NULL"), nullable=True
    )

    question_text_snapshot: Mapped[str] = mapped_column(Text(), nullable=False)
    question_type_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)

    # فقط یکی از فیلدهای زیر، بسته به نوع سوال، مقدار می‌گیرد
    selected_option_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)
    text_value: Mapped[str | None] = mapped_column(Text(), nullable=True)
    number_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    date_value: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    score: Mapped[float | None] = mapped_column(Float, nullable=True)  # امتیاز محاسبه‌شده (۰ تا ۱۰۰)
    comment: Mapped[str | None] = mapped_column(Text(), nullable=True)

    evaluation: Mapped["Evaluation"] = relationship(back_populates="answers")
