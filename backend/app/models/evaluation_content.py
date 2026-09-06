"""
مدل‌های «محتوای ارزیابی عملکرد» - دوره‌های ارزیابی و فرم‌ها (با
دسته‌بندی/سوال/گزینه‌های آن‌ها). این‌ها فقط «چه چیزی پرسیده می‌شود و در
چه بازه زمانی» را مشخص می‌کنند - نه «چه کسی چه کسی را ارزیابی می‌کند»
(آن در app/models/evaluation.py است) و نه خودِ فرایند پرسش‌وپاسخ واقعی
(Draft/Submit، که یک مرحله بعدی است).

⚠️ Historical Integrity: بعد از این‌که حداقل یک ارزیابی واقعی از یک
فرم/سوال استفاده کرد، آن فرم/سوال دیگر Hard-Delete نمی‌شود - فقط
غیرفعال (is_active=False / status=archived) می‌شود؛ این‌طوری تاریخچه
ارزیابی‌های قبلی همیشه سالم می‌ماند. این قانون در Service Layer اعمال
می‌شود (app/services/evaluation_form_service.py)، نه در سطح دیتابیس.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class EvaluationPeriodStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    active = "active"
    closed = "closed"
    archived = "archived"


class EvaluationPeriod(Base, TimestampMixin):
    """
    یک دوره ارزیابی - مثلاً «ارزیابی عملکرد نیمه اول ۱۴۰۵». site_id
    اختیاری است: اگر None باشد، این دوره برای همه سایت‌ها اعمال می‌شود؛
    اگر مقدار داشته باشد، فقط مخصوص همان سایت است.
    """

    __tablename__ = "evaluation_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[EvaluationPeriodStatus] = mapped_column(
        Enum(EvaluationPeriodStatus, name="evaluation_period_status"),
        default=EvaluationPeriodStatus.draft,
        nullable=False,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    site: Mapped["Site"] = relationship()  # noqa: F821


class EvaluationFormStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    inactive = "inactive"
    archived = "archived"


class EvaluationForm(Base, TimestampMixin):
    """
    یک فرم ارزیابی - مثلاً «فرم ارزیابی عملکرد پرسنل». هر فرم چند
    دسته‌بندی دارد، هر دسته‌بندی چند سوال.

    ⚠️ Form Versioning ساده: اگر فرمی که قبلاً استفاده شده نیاز به تغییر
    محتوایی دارد، به‌جای ویرایش مستقیم، یک نسخه جدید (version افزایش‌یافته،
    parent_form_id به فرم قبلی) ساخته می‌شود - فرم‌های قدیمی همچنان
    archived می‌مانند، نه حذف.
    """

    __tablename__ = "evaluation_forms"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_form_id: Mapped[int | None] = mapped_column(
        ForeignKey("evaluation_forms.id", ondelete="SET NULL"), nullable=True
    )
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
    یک دسته‌بندی سوالات درون یک فرم - مثلاً «انضباط کاری». weight درصد
    این دسته از امتیاز کل فرم است (اعتبارسنجی مجموع ۱۰۰٪ در Service
    Layer، نه در دیتابیس - چون فقط هنگام فعال‌کردن فرم لازم است، نه در
    حالت Draft که هنوز ناقص است).
    """

    __tablename__ = "evaluation_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    form_id: Mapped[int] = mapped_column(ForeignKey("evaluation_forms.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    form: Mapped["EvaluationForm"] = relationship(back_populates="categories")
    questions: Mapped[list["EvaluationQuestion"]] = relationship(
        back_populates="category", order_by="EvaluationQuestion.sort_order", cascade="all, delete-orphan"
    )


class EvaluationQuestionType(str, enum.Enum):
    single_choice = "single_choice"
    multiple_choice = "multiple_choice"
    rating = "rating"
    yes_no = "yes_no"
    text = "text"
    number = "number"
    date = "date"


class EvaluationQuestion(Base, TimestampMixin):
    """
    یک سوال درون یک دسته‌بندی. برای انواع single_choice/multiple_choice/
    rating/yes_no، پاسخ‌های ممکن در EvaluationQuestionOption تعریف
    می‌شوند (حتی yes_no - با دو گزینه «بله»/«خیر» با امتیاز دلخواه، تا
    منطق امتیازدهی یکسانی برای همه این انواع استفاده شود). انواع
    text/number/date گزینه ندارند - فقط برای ثبت توضیح/عدد/تاریخ آزاد.
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
    weight: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    category: Mapped["EvaluationCategory"] = relationship(back_populates="questions")
    options: Mapped[list["EvaluationQuestionOption"]] = relationship(
        back_populates="question", order_by="EvaluationQuestionOption.sort_order", cascade="all, delete-orphan"
    )


class EvaluationQuestionOption(Base, TimestampMixin):
    """یک گزینه پاسخ ممکن برای یک سوال - با یک امتیاز عددی دلخواه (Dynamic)."""

    __tablename__ = "evaluation_question_options"
    __table_args__ = (UniqueConstraint("question_id", "sort_order", name="uq_evaluation_option_sort_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_questions.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    question: Mapped["EvaluationQuestion"] = relationship(back_populates="options")
