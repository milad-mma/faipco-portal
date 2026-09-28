"""
مدل‌های امنیت ورود:
- LoginSecurityEvent: رویدادهای ناموفق ورود/بازیابی رمز (گزارش امنیتی، محدودیت IP و هشدار حجم غیرعادی).
- CaptchaChallenge: چالش کپچای تصویری داخلی (یک‌بارمصرف، با انقضای کوتاه).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LoginSecurityEvent(Base):
    """یک رویداد امنیتی ورود (جدول login_security_events)."""
    __tablename__ = "login_security_events"
    __table_args__ = (Index("ix_login_security_events_ip_created", "ip", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # login_failed | login_locked | ip_blocked | captcha_failed | reset_code_failed | forgot_password
    kind: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)  # شناسه‌ی یکسان‌شده (نه رمز)
    ip: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # False بعد از «آزادسازی IP» توسط مدیر: دیگر در شمارش محدودیت IP حساب نمی‌شود (در گزارش می‌ماند)
    counted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CaptchaChallenge(Base):
    """چالش کپچا؛ فقط هش پاسخ ذخیره می‌شود و با اولین بررسی (درست یا غلط) حذف می‌شود."""
    __tablename__ = "captcha_challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    answer_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
