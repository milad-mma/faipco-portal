"""
مدل جابه‌جایی پرسنل بین سایت‌ها.

وقتی چند سایت یک دیتابیس منبع مشترک دارند و واحد یک نفر در منبع از شاخه‌ی
یک سایت به شاخه‌ی سایت دیگر می‌رود، Sync رکورد پرسنل (با همه‌ی سوابق و حساب
کاربری) را به سایت جدید منتقل می‌کند و یک ردیف اینجا ثبت می‌کند. نقش‌های
سایتی و سرپرستی واحدهای سایت قبلی خودکار حذف نمی‌شوند؛ این ردیف تا وقتی
reviewed_at خالی است در صفحه‌ی «مدیریت دسترسی» برای بازبینی نشان داده می‌شود.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class SiteTransfer(Base, TimestampMixin):
    """یک جابه‌جایی پرسنل از سایتی به سایت دیگر، با وضعیت بازبینی نقش‌ها."""

    __tablename__ = "site_transfers"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    personnel_code: Mapped[str] = mapped_column(String(64), nullable=False)  # برای نمایش حتی اگر پرسنل بعداً تغییر کند
    from_site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), nullable=True)
    to_site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), nullable=True)
    # حساب کاربری متصل به این پرسنل در لحظه‌ی جابه‌جایی (اگر داشت)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    transferred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # زمان و کاربری که نقش‌های باقی‌مانده را بازبینی و این مورد را «بررسی‌شده» علامت زد
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    employee: Mapped["Employee"] = relationship()  # noqa: F821
