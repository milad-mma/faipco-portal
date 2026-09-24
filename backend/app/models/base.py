"""
Mixin های مشترک برای مدل‌های ORM؛ شامل TimestampMixin که ستون‌های زمان ایجاد
و آخرین ویرایش را به مدل اضافه می‌کند.
"""
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """created_at و updated_at به‌صورت خودکار توسط دیتابیس مقداردهی می‌شوند."""

    # زمان ایجاد رکورد (پیش‌فرض سمت دیتابیس)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # زمان آخرین ویرایش؛ با onupdate در هر UPDATE از طریق ORM تازه می‌شود
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
