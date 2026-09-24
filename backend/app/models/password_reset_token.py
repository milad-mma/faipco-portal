"""
مدل توکن‌های بازنشانی رمز عبور (یک‌بارمصرف و کوتاه‌عمر).
ساخت، اعتبارسنجی و مصرف توکن در app/services/password_reset_service.py انجام می‌شود.
ستون token هم برای ایمیل (رشته‌ی تصادفی طولانی در لینک) و هم برای پیامک (کد ۶ رقمی) استفاده می‌شود
و هر دو به یک شکل اعتبارسنجی می‌شوند؛ channel فقط برای نمایش/گزارش نگه داشته می‌شود.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PasswordResetChannel(str, enum.Enum):
    """کانال ارسال توکن بازنشانی: ایمیل یا پیامک."""
    email = "email"
    sms = "sms"


class PasswordResetToken(Base):
    """یک توکن بازنشانی رمز برای یک کاربر (جدول password_reset_tokens)."""
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)  # رشته‌ی لینک ایمیل یا کد ۶ رقمی پیامک
    channel: Mapped[PasswordResetChannel] = mapped_column(
        Enum(PasswordResetChannel, name="password_reset_channel"), default=PasswordResetChannel.email, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # زمان مصرف؛ None یعنی هنوز استفاده نشده
