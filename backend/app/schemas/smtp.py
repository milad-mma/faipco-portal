"""
Schema های تنظیمات SMTP - همان الگوی امنیتی BackupSettingsIn/Out
(app/schemas/backup.py): رمز عبور هرگز در پاسخ برنمی‌گردد؛ در ورودی
اختیاری است - خالی یعنی رمز قبلی حفظ شود.
"""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.smtp_settings import SmtpEncryptionMode


class SmtpSettingsIn(BaseModel):
    enabled: bool = False
    host: str | None = None
    port: int = Field(default=587, ge=1, le=65535)
    username: str | None = None
    password: str | None = Field(default=None, description="در ویرایش، خالی بگذارید تا رمز قبلی حفظ شود")
    from_address: EmailStr | None = None
    from_name: str | None = None
    encryption_mode: SmtpEncryptionMode = SmtpEncryptionMode.starttls

    @model_validator(mode="after")
    def _validate_required_when_enabled(self) -> "SmtpSettingsIn":
        if self.enabled and not (self.host and self.from_address):
            raise ValueError("برای فعال‌کردن SMTP، آدرس سرور و آدرس ایمیل فرستنده الزامی‌اند")
        return self


class SmtpSettingsOut(BaseModel):
    enabled: bool
    host: str | None
    port: int
    username: str | None
    has_password: bool
    from_address: str | None
    from_name: str | None
    encryption_mode: SmtpEncryptionMode


class SmtpTestEmailIn(BaseModel):
    to_address: EmailStr
