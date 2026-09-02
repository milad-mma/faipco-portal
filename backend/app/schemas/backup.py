"""
Schema های «زمان‌بندی بکاپ + هدف راه‌دور (SMB/FTP)».

⚠️ همان الگوی امنیتی SiteConnectionIn/Out (app/schemas/site.py): رمز عبور
هرگز در پاسخ (Out) برگردانده نمی‌شود؛ در ورودی (In) اختیاری است - اگر خالی
باشد، رمز قبلی دست‌نخورده می‌ماند (برای ویرایش بدون نیاز به وارد‌کردن دوباره).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.backup_settings import BackupRetentionMode, BackupScheduleType


class BackupSettingsIn(BaseModel):
    schedule_enabled: bool = False
    schedule_type: BackupScheduleType = BackupScheduleType.daily
    schedule_hour: int = Field(default=3, ge=0, le=23)
    schedule_minute: int = Field(default=0, ge=0, le=59)
    schedule_weekday: int | None = Field(default=None, ge=0, le=6)  # فقط برای weekly
    schedule_interval_hours: int | None = Field(default=None, ge=1, le=168)  # فقط برای interval

    smb_enabled: bool = False
    smb_host: str | None = None
    smb_share: str | None = None
    smb_path: str | None = None
    smb_username: str | None = None
    smb_password: str | None = Field(default=None, description="در ویرایش، خالی بگذارید تا رمز قبلی حفظ شود")
    smb_domain: str | None = None

    ftp_enabled: bool = False
    ftp_host: str | None = None
    ftp_port: int = Field(default=21, ge=1, le=65535)
    ftp_username: str | None = None
    ftp_password: str | None = Field(default=None, description="در ویرایش، خالی بگذارید تا رمز قبلی حفظ شود")
    ftp_path: str | None = None
    ftp_use_tls: bool = True

    retention_mode: BackupRetentionMode = BackupRetentionMode.count
    retention_count: int = Field(default=30, ge=1, le=1000)
    retention_days: int = Field(default=30, ge=1, le=3650)

    email_enabled: bool = False
    email_recipients: str | None = Field(default=None, description="هر آدرس ایمیل در یک خط")

    @model_validator(mode="after")
    def _validate_schedule_fields(self) -> "BackupSettingsIn":
        if self.schedule_enabled:
            if self.schedule_type == BackupScheduleType.weekly and self.schedule_weekday is None:
                raise ValueError("برای زمان‌بندی هفتگی، روز هفته باید مشخص شود")
            if self.schedule_type == BackupScheduleType.interval and not self.schedule_interval_hours:
                raise ValueError("برای زمان‌بندی چندساعتی، فاصله زمانی (ساعت) باید مشخص شود")
        if self.smb_enabled and not (self.smb_host and self.smb_share and self.smb_username):
            raise ValueError("برای فعال‌کردن هدف SMB، نام سرور، Share و نام کاربری الزامی‌اند")
        if self.ftp_enabled and not (self.ftp_host and self.ftp_username):
            raise ValueError("برای فعال‌کردن هدف FTP، نام سرور و نام کاربری الزامی‌اند")
        if self.email_enabled and not self.email_recipients:
            raise ValueError("برای فعال‌کردن ارسال به ایمیل، حداقل یک گیرنده لازم است")
        return self


class BackupSettingsOut(BaseModel):
    schedule_enabled: bool
    schedule_type: BackupScheduleType
    schedule_hour: int
    schedule_minute: int
    schedule_weekday: int | None
    schedule_interval_hours: int | None

    smb_enabled: bool
    smb_host: str | None
    smb_share: str | None
    smb_path: str | None
    smb_username: str | None
    smb_has_password: bool
    smb_domain: str | None

    ftp_enabled: bool
    ftp_host: str | None
    ftp_port: int
    ftp_username: str | None
    ftp_has_password: bool
    ftp_path: str | None
    ftp_use_tls: bool

    retention_mode: BackupRetentionMode
    retention_count: int
    retention_days: int

    email_enabled: bool
    email_recipients: str | None

    last_run_at: datetime | None
    last_run_success: bool | None
    last_run_message: str | None


class SmbTestConnectionIn(BaseModel):
    host: str
    share: str
    path: str | None = None
    username: str
    password: str | None = Field(default=None, description="خالی یعنی از رمز ذخیره‌شده فعلی استفاده شود")
    domain: str | None = None


class FtpTestConnectionIn(BaseModel):
    host: str
    port: int = 21
    username: str
    password: str | None = Field(default=None, description="خالی یعنی از رمز ذخیره‌شده فعلی استفاده شود")
    path: str | None = None
    use_tls: bool = True
