"""
مدل‌های LoginAttempt و MessageRateLimit: شمارنده‌های Rate Limiting ذخیره‌شده در پایگاه‌داده.
چون سرویس با چند worker اجرا می‌شود، این شمارنده‌ها در دیتابیس نگه داشته می‌شوند تا بین همه‌ی workerها
مشترک باشند و تلاش‌های ناموفق ورود بین workerها پخش نشود (در غیر این صورت قفل موقت دورزدنی می‌شد).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LoginAttempt(Base):
    """شمارنده‌ی تلاش‌های ناموفق و زمان قفل موقت برای هر شناسه‌ی ورود (یا کلید مبتنی بر IP)."""
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    # یوزرنیم یا کد پرسنلی (یا کلیدی مثل reset-password:<ip>)، همیشه lower/strip شده ذخیره می‌شود
    identifier: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # تعداد تلاش‌های ناموفق پیاپی
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # تا این زمان قفل است؛ None = قفل نیست
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MessageRateLimit(Base):
    """زمان آخرین پیام ارسالی هر کاربر، برای محدود کردن فاصله‌ی ارسال پیام."""
    __tablename__ = "message_rate_limits"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    last_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
