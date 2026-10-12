"""
مدل کد تأیید یک‌بارمصرف (OTP) برای عملیات حساس داخل پروفایل کاربر واردشده:
- purpose="password": تغییر رمز عبور (کد به موبایل یا ایمیل خود کاربر)
- purpose="mobile": تغییر شماره موبایل (کد به شماره‌ی جدید)
ساخت، ارسال و بررسی در app/services/otp_service.py انجام می‌شود. فقط هش SHA-256 کد ذخیره می‌شود.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class VerificationCode(Base):
    """یک کد تأیید برای یک کاربر و یک هدف (جدول verification_codes، Migration 112)."""
    __tablename__ = "verification_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)  # password | mobile
    channel: Mapped[str] = mapped_column(String(10), nullable=False)  # sms | email
    destination: Mapped[str] = mapped_column(String(255), nullable=False)  # شماره/ایمیلی که کد به آن رفت
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
