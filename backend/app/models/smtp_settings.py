"""
مدل تنظیمات SMTP (ارسال ایمیل) - یک ردیف واحد (Singleton، id همیشه ۱)،
چون این یک تنظیم سراسری سرور است، دقیقاً مثل BackupSettings.

کاربرد: «فراموشی رمز عبور» (ارسال لینک بازنشانی) و «ارسال بکاپ به ایمیل».
رمز عبور SMTP هرگز خام ذخیره نمی‌شود - فقط رمزنگاری‌شده، با همان
app.core.security.encrypt_secret/decrypt_secret.
"""
from __future__ import annotations

import enum

from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SmtpEncryptionMode(str, enum.Enum):
    none = "none"  # بدون رمزنگاری (فقط برای سرورهای داخلی/محلی توصیه می‌شود)
    starttls = "starttls"  # رایج‌ترین حالت - معمولاً پورت ۵۸۷
    ssl = "ssl"  # اتصال مستقیم رمزنگاری‌شده - معمولاً پورت ۴۶۵


class SmtpSettings(Base):
    __tablename__ = "smtp_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    port: Mapped[int] = mapped_column(Integer, default=587, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_encrypted: Mapped[str | None] = mapped_column(String(500), nullable=True)
    from_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    from_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    encryption_mode: Mapped[SmtpEncryptionMode] = mapped_column(
        Enum(SmtpEncryptionMode, name="smtp_encryption_mode"), default=SmtpEncryptionMode.starttls, nullable=False
    )
