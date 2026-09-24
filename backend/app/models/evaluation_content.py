"""
مدل‌های «محتوای ارزیابی عملکرد»: دوره‌های ارزیابی و فرم‌ها (با دسته‌بندی، سوال و گزینه).
این مدل‌ها مشخص می‌کنند چه چیزی و در چه بازه‌ای پرسیده می‌شود؛ «چه کسی چه کسی را
ارزیابی می‌کند» در app/models/evaluation.py و خود فرایند پاسخ‌دهی در
app/models/evaluation_process.py است.

فرم/سوالی که در حداقل یک ارزیابی استفاده شده Hard-Delete نمی‌شود و فقط غیرفعال
(is_active=False / status=archived) می‌شود تا تاریخچه سالم بماند. این قانون در
app/services/evaluation_form_service.py اعمال می‌شود، نه در دیتابیس.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class EvaluationPeriodStatus(str, enum.Enum):
    """وضعیت‌های چرخه عمر یک دوره ارزیابی."""
    draft = "draft"
    scheduled = "scheduled"
    active = "active"
    closed = "closed"
    archived = "archived"


class EvaluationPeriod(Base, TimestampMixin):
    """
    یک دوره ارزیابی (مثلاً «ارزیابی عملکرد نیمه اول ۱۴۰۵»).
    site_id=None یعنی دوره برای همه سایت‌هاست؛ در غیر این صورت فقط مخصوص همان سایت.
    """

    __tablename__ = "evaluation_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=True)  # None = همه سایت‌ها
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[EvaluationPeriodStatus] = mapped_column(
        Enum(EvaluationPeriodStatus, name="evaluation_period_status"),
        default=EvaluationPeriodStatus.draft,
        nullable=False,
    )
    # غیرفعال: ارزیابی‌های این دوره برای ارزیاب‌ها و پرسنل پنهان است (فهرست، انجام،
    # نتیجه و اجبار)؛ فقط ادمین در صفحه دوره‌ها و گزارش‌ها می‌بیند. برگشت‌پذیر است.
    is_disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    site: Mapped["Site"] = relationship()  # noqa: F821


class EvaluationFormStatus(str, enum.Enum):
    """وضعیت‌های یک فرم ارزیابی."""
    draft = "draft"
    active = "active"
    inactive = "inactive"
    archived = "archived"


class EvaluationForm(Base, TimestampMixin):
    """
    یک فرم ارزیابی؛ هر فرم چند دسته‌بندی و هر دسته‌بندی چند سوال دارد.
    برای تغییر محتوای فرمِ استفاده‌شده، نسخه جدید (version+1 با parent_form_id به فرم قبلی)
    ساخته می‌شود و فرم قبلی archived می‌ماند.
    """

    __tablename__ = "evaluation_forms"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=True)  # None = همه سایت‌ها
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # شماره نسخه فرم
    parent_form_id: Mapped[int | None] = mapped_column(
        ForeignKey("evaluation_forms.id", ondelete="SET NULL"), nullable=True
    )  # فرم نسخه قبلی که این نسخه از آن ساخته شده
    status: Mapped[EvaluationFormStatus] = mapped_column(
        Enum(EvaluationFormStatus, name="evaluation_form_status"),
        default=EvaluationFormStatus.draft,
        nullable=False,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    site: Mapped["Site"] = relationship()  # noqa: F821
    categories: Mapped[list["EvaluationCategory"]] = relationship(
        back_populates="form", order_by="EvaluationCategory.sort_order", cascade="all, delete-orphan"
    )


class EvaluationCategory(Base, TimestampMixin):
    """
    یک دسته‌بندی سوالات درون فرم (مثلاً «انضباط کاری»).
    weight درصد سهم دسته از امتیاز کل است؛ مجموع ۱۰۰٪ فقط هنگام فعال‌سازی فرم در Service Layer بررسی می‌شود.
    """

    __tablename__ = "evaluation_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    form_id: Mapped[int] = mapped_column(ForeignKey("evaluation_forms.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)  # درصد از امتیاز کل فرم
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    form: Mapped["EvaluationForm"] = relationship(back_populates="categories")
    questions: Mapped[list["EvaluationQuestion"]] = relationship(
        back_populates="category", order_by="EvaluationQuestion.sort_order", cascade="all, delete-orphan"
    )


class EvaluationQuestionType(str, enum.Enum):
    """انواع سوال؛ چهار نوع اول گزینه‌دار و امتیازی‌اند، سه نوع آخر پاسخ آزاد دارند."""
    single_choice = "single_choice"
    multiple_choice = "multiple_choice"
    rating = "rating"
    yes_no = "yes_no"
    text = "text"
    number = "number"
    date = "date"


class EvaluationQuestion(Base, TimestampMixin):
    """
    یک سوال درون دسته‌بندی. برای single_choice/multiple_choice/rating/yes_no پاسخ‌ها در
    EvaluationQuestionOption تعریف می‌شوند (yes_no هم دو گزینه با امتیاز دلخواه دارد تا منطق
    امتیازدهی یکسان باشد). text/number/date گزینه ندارند و فقط مقدار آزاد ثبت می‌کنند.
    """

    __tablename__ = "evaluation_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_categories.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text(), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    question_type: Mapped[EvaluationQuestionType] = mapped_column(
        Enum(EvaluationQuestionType, name="evaluation_question_type"), nullable=False
    )
    weight: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)  # وزن سوال درون دسته‌بندی
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    category: Mapped["EvaluationCategory"] = relationship(back_populates="questions")
    options: Mapped[list["EvaluationQuestionOption"]] = relationship(
        back_populates="question", order_by="EvaluationQuestionOption.sort_order", cascade="all, delete-orphan"
    )


class EvaluationQuestionOption(Base, TimestampMixin):
    """یک گزینه پاسخ برای یک سوال، با امتیاز عددی دلخواه."""

    __tablename__ = "evaluation_question_options"
    __table_args__ = (UniqueConstraint("question_id", "sort_order", name="uq_evaluation_option_sort_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_questions.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)  # امتیاز خام این گزینه
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    question: Mapped["EvaluationQuestion"] = relationship(back_populates="options")
