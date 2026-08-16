"""
مدل‌های LoginAttempt و MessageRateLimit — نسخه پایگاه‌داده‌ای شمارنده‌های
Rate Limiting که قبلاً فقط در حافظه پایتون بودند. چون سرویس با چند Worker
اجرا می‌شود، این شمارنده‌ها باید بین همه Worker ها مشترک باشند — یک تست
نفوذ زنده نشان داد بدون این، Lockout ورود عملاً قابل‌دورزدن است (تلاش‌های
ناموفق بین Worker ها پخش می‌شدند و هیچ‌کدام به آستانه قفل نمی‌رسیدند).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    # یوزرنیم یا کد پرسنلی، همیشه lower/strip شده ذخیره می‌شود
    identifier: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MessageRateLimit(Base):
    __tablename__ = "message_rate_limits"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    last_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
