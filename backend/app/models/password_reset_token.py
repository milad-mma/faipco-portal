"""
مدل توکن‌های «بازنشانی رمز عبور» - یک‌بارمصرف و کوتاه‌عمر. منطق واقعی
(ساخت/اعتبارسنجی/مصرف) در app/services/password_reset_service.py است.

⚠️ همان ستون token هم برای ایمیل (رشته طولانی و امن، در querystring یک
لینک) و هم برای پیامک (کد عددی ۶ رقمی، تایپ‌شده دستی توسط کاربر) استفاده
می‌شود - channel فقط برای نمایش/گزارش نگه داشته می‌شود، نه برای تفاوت
منطقی در اعتبارسنجی (هر دو یکسان چک می‌شوند).
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PasswordResetChannel(str, enum.Enum):
    email = "email"
    sms = "sms"


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    channel: Mapped[PasswordResetChannel] = mapped_column(
        Enum(PasswordResetChannel, name="password_reset_channel"), default=PasswordResetChannel.email, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
