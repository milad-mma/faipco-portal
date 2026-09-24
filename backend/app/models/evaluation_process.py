"""
مدل‌های «جریان انجام ارزیابی»؛ لایه سوم سیستم ارزیابی عملکرد:
    app/models/evaluation.py         -> چه کسی مجاز به ارزیابی چه کسی است
    app/models/evaluation_content.py -> چه چیزی پرسیده می‌شود، در چه دوره‌ای
    app/models/evaluation_process.py -> همین فایل: خودِ عمل ارزیابی‌کردن

سه مدل:
    EvaluationAssignment: «X باید Y را برای دوره P با فرم F ارزیابی کند»؛
        از روی get_evaluation_targets و دوره انتخاب‌شده تولید می‌شود.
    Evaluation: فرم پرشده، همراه با Snapshot اطلاعات لحظه ثبت تا تغییرات بعدی
        پرسنل/واحد/فرم روی ارزیابی‌های قبلی اثر نگذارد.
    EvaluationAnswer: پاسخ هر سوال، همراه با Snapshot متن و نوع سوال.
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
    """وضعیت یک انتساب ارزیابی: در انتظار یا انجام‌شده."""
    pending = "pending"
    completed = "completed"


class EvaluationAssignment(Base, TimestampMixin):
    """
    «ارزیاب X باید پرسنل Y را برای این دوره با این فرم ارزیابی کند»؛ به‌صورت خودکار از
    get_evaluation_targets برای دوره انتخابی تولید می‌شود (POST .../generate-assignments).
    UniqueConstraint مانع ارزیابی تکراری یک فرد در یک ترکیب دوره+فرم توسط یک ارزیاب می‌شود.
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
    )  # ارزیاب
    target_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)  # ارزیابی‌شونده
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
    """وضعیت فرم پرشده: پیش‌نویس یا ثبت نهایی."""
    draft = "draft"
    submitted = "submitted"


class Evaluation(Base, TimestampMixin):
    """
    فرم پرشده برای یک Assignment؛ حداکثر یکی به‌ازای هر Assignment (assignment_id یکتا).
    چون Employee توسط Sync Engine تغییر می‌کند، نام‌ها/کدها/عناوین در ستون‌های *_snapshot
    نگه داشته می‌شوند تا گزارش ارزیابی‌های قدیمی ثابت بماند.
    """

    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_assignments.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[EvaluationStatus] = mapped_column(
        Enum(EvaluationStatus, name="evaluation_status"), default=EvaluationStatus.draft, nullable=False
    )
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # امتیاز نهایی وزن‌دار (۰ تا ۱۰۰)
    comment: Mapped[str | None] = mapped_column(Text(), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    was_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # پس از ثبت نهایی ویرایش شده است

    # --- Historical Snapshot: در لحظه شروع/Submit پر می‌شود و بعداً تغییر نمی‌کند ---
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
        شناسه فرم این ارزیابی را برمی‌گرداند (میان‌بر به assignment.form_id، ستون دیتابیسی نیست)
        تا Frontend بداند کدام فرم را رندر کند. assignment باید از قبل selectinload شده باشد،
        وگرنه در حالت async خطای MissingGreenlet رخ می‌دهد.
        """
        return self.assignment.form_id


class EvaluationAnswer(Base, TimestampMixin):
    """
    پاسخ یک سوال درون یک Evaluation.
    متن و نوع سوال در لحظه پاسخ Snapshot می‌شود تا تغییر بعدی سوال، ارزیابی‌های قبلی را تغییر ندهد.
    """

    __tablename__ = "evaluation_answers"
    __table_args__ = (UniqueConstraint("evaluation_id", "question_id", name="uq_evaluation_answer_question"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_questions.id", ondelete="SET NULL"), nullable=True
    )  # با حذف سوال NULL می‌شود؛ snapshot باقی می‌ماند

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
