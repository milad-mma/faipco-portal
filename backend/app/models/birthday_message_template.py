"""
مدل BirthdayMessageTemplate: مجموعه متن‌های آماده تبریک تولد.

این متن‌ها را مدیر منابع انسانی و ادمین مدیریت می‌کنند. هر روز در ساعت
تنظیم‌شده، یک متن تصادفی از این مجموعه برای هر پرسنلی که امروز تولدش است
فرستاده می‌شود.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class BirthdayMessageTemplate(Base):
    """یک متن آماده تبریک تولد در جدول birthday_message_templates."""
    __tablename__ = "birthday_message_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
