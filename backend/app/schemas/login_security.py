"""Schemaهای امنیت ورود: تنظیمات قابل ویرایش از پنل، وضعیت قفل‌ها، رویدادها و کپچا."""
from __future__ import annotations

import ipaddress
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class LoginSecuritySettings(BaseModel):
    """تنظیمات امنیت ورود (ذخیره در system_settings با کلید login_security). پیش‌فرض‌ها = رفتار قبلی سیستم."""

    # قفل پلکانی هر شناسه (نام کاربری / کد پرسنلی)
    attempts_per_tier: int = Field(default=3, ge=1, le=20, description="هر چند تلاش ناموفق یک پله‌ی قفل")
    lock_minutes: list[int] = Field(default_factory=lambda: [1, 5, 60], min_length=1, max_length=6)

    # محدودیت IP (تلاش ناموفق روی شناسه‌های مختلف از یک IP)
    ip_limit_enabled: bool = True
    ip_max_failures: int = Field(default=20, ge=3, le=1000)
    ip_window_minutes: int = Field(default=10, ge=1, le=1440)
    ip_block_minutes: int = Field(default=15, ge=1, le=1440)
    exempt_ips: list[str] = Field(default_factory=list, max_length=100)  # CIDR یا IP تکی؛ محدودیت IP و کپچای IP ندارند

    # کپچای داخلی
    captcha_enabled: bool = True
    captcha_after_failures: int = Field(default=2, ge=0, le=20)  # ۰ = همیشه
    captcha_on_forgot_password: bool = True

    # هشدار حجم غیرعادی تلاش ناموفق
    alert_enabled: bool = True
    alert_threshold: int = Field(default=50, ge=5, le=100000)
    alert_window_minutes: int = Field(default=10, ge=1, le=1440)

    retention_days: int = Field(default=90, ge=7, le=730)  # نگهداری گزارش رویدادها

    @field_validator("lock_minutes")
    @classmethod
    def _check_lock_minutes(cls, v: list[int]) -> list[int]:
        """هر پله بین ۱ دقیقه و ۷ روز."""
        for m in v:
            if not 1 <= int(m) <= 10080:
                raise ValueError("مدت هر پله‌ی قفل باید بین ۱ تا ۱۰۰۸۰ دقیقه باشد")
        return [int(m) for m in v]

    @field_validator("exempt_ips")
    @classmethod
    def _check_exempt_ips(cls, v: list[str]) -> list[str]:
        """هر مقدار باید IP یا CIDR معتبر باشد؛ فاصله‌ها حذف و تکراری‌ها یکی می‌شوند."""
        out: list[str] = []
        for raw in v:
            text = str(raw).strip()
            if not text:
                continue
            try:
                network = ipaddress.ip_network(text, strict=False)
            except ValueError:
                raise ValueError(f"«{text}» آدرس IP یا رنج CIDR معتبر نیست")
            if str(network) not in out:
                out.append(str(network))
        return out


class LockOut(BaseModel):
    """یک قفل فعال: شناسه، IP یا کلید بازیابی رمز."""
    key: str
    kind: str  # identifier | ip | reset
    value: str
    fail_count: int
    locked_until: datetime


class LoginSecurityEventOut(BaseModel):
    """یک ردیف گزارش رویداد."""
    id: int
    created_at: datetime
    kind: str
    identifier: str | None
    ip: str
    user_agent: str | None

    model_config = {"from_attributes": True}


class UnlockRequest(BaseModel):
    """بدنه‌ی POST /login-security/unlock؛ key همان کلید برگشتی از GET /login-security/locks است."""
    key: str = Field(min_length=1, max_length=255)
