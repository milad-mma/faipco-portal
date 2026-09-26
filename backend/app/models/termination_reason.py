"""
دسته‌بندی علت ترک کار برای «گزارش جذب و ترک کار».

علت ترک کار در منبع (کاراوب: Employee.Cut_Reason) متن آزاد است و یک علت با چند
املای مختلف ثبت می‌شود. هر متن پس از نرمال‌سازی (turnover_report_service.normalize_reason)
یک ردیف TerminationReasonAlias دارد که به یک دسته وصل می‌شود؛ متن‌های تازه با
category_id خالی («دسته‌بندی نشده») خودکار اضافه می‌شوند تا در پنل دسته‌بندی شوند.
این جدول‌ها اطلاعات شخصی ندارند و بین همه‌ی سایت‌ها مشترک‌اند.
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin

# گروه آماری هر دسته (طبقه‌بندی استاندارد خروج کارکنان)
REASON_GROUPS = ("voluntary", "involuntary", "probation", "other", "excluded")


class TerminationReasonCategory(Base, TimestampMixin):
    """یک دسته‌ی علت ترک کار (مثل «استعفا») با گروه آماری و مبنای قانونی."""

    __tablename__ = "termination_reason_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)  # دسته‌های پیش‌فرض Migration 089
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    group: Mapped[str] = mapped_column(String(20), nullable=False)  # یکی از REASON_GROUPS
    legal_basis: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TerminationReasonAlias(Base, TimestampMixin):
    """یک متن نرمال‌شده‌ی علت ترک کار و دسته‌ی آن (NULL = دسته‌بندی نشده)."""

    __tablename__ = "termination_reason_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    normalized_text: Mapped[str] = mapped_column(String(400), unique=True, nullable=False)
    sample_text: Mapped[str] = mapped_column(String(400), nullable=False)  # یکی از متن‌های خام اصلی برای نمایش
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("termination_reason_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
