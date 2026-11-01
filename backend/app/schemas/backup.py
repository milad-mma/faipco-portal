"""
Schema های «زمان‌بندی بکاپ + هدف راه‌دور (SMB/FTP)».

همان الگوی امنیتی SiteConnectionIn/Out (app/schemas/site.py): رمز عبور
هرگز در پاسخ (Out) برگردانده نمی‌شود؛ در ورودی (In) اختیاری است - اگر خالی
باشد، رمز قبلی دست‌نخورده می‌ماند (برای ویرایش بدون نیاز به وارد‌کردن دوباره).
"""
from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.backup_dest_rules import check_local_path
from app.models.backup_settings import BackupRetentionMode, BackupScheduleType

_S3_BUCKET_RE = re.compile(r"[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]")

# کاراکترهایی که در نام سرور/Share/مسیر SMB مجاز نیستند — این مقادیر در فرمان smbclient (-c "cd ...; put ...")
# قرار می‌گیرند و با این کاراکترها می‌شد از گیومه خارج شد یا فرمان دیگری تزریق کرد
_SMB_FORBIDDEN_CHARS = ('"', ";", "\n", "\r", "`", "$(")
_SMB_FIELD_TITLES = {
    "smb_host": "نام سرور SMB",
    "smb_share": "نام Share",
    "smb_path": "مسیر SMB",
    "host": "نام سرور SMB",
    "share": "نام Share",
    "path": "مسیر SMB",
}


def _clean_smb_field(value, field_name: str):
    """مقدار SMB را trim می‌کند و اگر شامل کاراکتر ممنوع باشد ValueError با نام فارسی فیلد می‌دهد؛ خالی → None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if any(ch in text for ch in _SMB_FORBIDDEN_CHARS):
        title = _SMB_FIELD_TITLES.get(field_name, field_name)
        raise ValueError(f"«{title}» نمی‌تواند شامل گیومه («\"»)، نقطه‌ویرگول، بک‌تیک، «$(» یا خط جدید باشد")
    return text


class BackupSettingsIn(BaseModel):
    """بدنه PUT /backup/settings و ورودی BackupSettingsService.update_settings."""

    schedule_enabled: bool = False
    schedule_type: BackupScheduleType = BackupScheduleType.daily
    schedule_hour: int = Field(default=3, ge=0, le=23)
    schedule_minute: int = Field(default=0, ge=0, le=59)
    schedule_weekday: int | None = Field(default=None, ge=0, le=6)  # فقط برای weekly
    schedule_interval_hours: int | None = Field(default=None, ge=1, le=168)  # فقط برای interval

    # رمز فایل ZIP بکاپ (AES-256)؛ خالی = رمز قبلی حفظ شود؛ archive_password_clear=True یعنی برداشتن رمز
    archive_password: str | None = Field(default=None, max_length=200)
    archive_password_clear: bool = False
    # برای تغییر یا برداشتن رمزِ موجود، رمز فعلی لازم است
    archive_password_current: str | None = Field(default=None, max_length=200)

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

    local_enabled: bool = False
    local_path: str | None = Field(default=None, max_length=500)

    sftp_enabled: bool = False
    sftp_host: str | None = Field(default=None, max_length=255)
    sftp_port: int = Field(default=22, ge=1, le=65535)
    sftp_username: str | None = Field(default=None, max_length=255)
    sftp_password: str | None = Field(default=None, description="در ویرایش، خالی بگذارید تا رمز قبلی حفظ شود")
    sftp_path: str | None = Field(default=None, max_length=500)
    # کلید سرور که «تست اتصال SFTP» برگرداند؛ None = کلید ذخیره‌شده دست نخورد
    sftp_host_key: str | None = Field(default=None, max_length=4000)

    s3_enabled: bool = False
    s3_endpoint: str | None = Field(default=None, max_length=500)
    s3_region: str | None = Field(default=None, max_length=100)
    s3_bucket: str | None = Field(default=None, max_length=255)
    s3_prefix: str | None = Field(default=None, max_length=500)
    s3_access_key: str | None = Field(default=None, max_length=255)
    s3_secret_key: str | None = Field(default=None, description="در ویرایش، خالی بگذارید تا کلید قبلی حفظ شود")
    s3_path_style: bool = True

    verify_full: bool = False

    retention_mode: BackupRetentionMode = BackupRetentionMode.count
    retention_count: int = Field(default=30, ge=1, le=1000)
    retention_days: int = Field(default=30, ge=1, le=3650)

    email_enabled: bool = False
    email_recipients: str | None = Field(default=None, description="هر آدرس ایمیل در یک خط")

    @field_validator("smb_host", "smb_share", "smb_path", mode="before")
    @classmethod
    def _validate_smb_fields(cls, value, info):
        """نام سرور/Share/مسیر SMB را از کاراکترهای ممنوع (گیومه، ;، بک‌تیک، خط جدید) پاک نگه می‌دارد."""
        return _clean_smb_field(value, info.field_name)

    @model_validator(mode="after")
    def _validate_schedule_fields(self) -> "BackupSettingsIn":
        """فیلدهای وابسته به هم را بررسی می‌کند؛ در صورت نقص ValueError (پاسخ 422) می‌دهد."""
        # فیلدهای لازم برای هر نوع زمان‌بندی
        if self.schedule_enabled:
            if self.schedule_type == BackupScheduleType.weekly and self.schedule_weekday is None:
                raise ValueError("برای زمان‌بندی هفتگی، روز هفته باید مشخص شود")
            if self.schedule_type == BackupScheduleType.interval and not self.schedule_interval_hours:
                raise ValueError("برای زمان‌بندی چندساعتی، فاصله زمانی (ساعت) باید مشخص شود")
        # هر مقصد فعال باید اطلاعات اتصال حداقلی داشته باشد
        if self.smb_enabled and not (self.smb_host and self.smb_share and self.smb_username):
            raise ValueError("برای فعال‌کردن هدف SMB، نام سرور، Share و نام کاربری الزامی‌اند")
        if self.ftp_enabled and not (self.ftp_host and self.ftp_username):
            raise ValueError("برای فعال‌کردن هدف FTP، نام سرور و نام کاربری الزامی‌اند")
        if self.email_enabled and not self.email_recipients:
            raise ValueError("برای فعال‌کردن ارسال به ایمیل، حداقل یک گیرنده لازم است")
        if self.local_enabled:
            self.local_path = check_local_path(self.local_path)
        if self.sftp_enabled and not (self.sftp_host and self.sftp_username):
            raise ValueError("برای فعال‌کردن SFTP، نام سرور و نام کاربری الزامی‌اند")
        if self.sftp_path and ".." in self.sftp_path.replace("\\", "/").split("/"):
            raise ValueError("مسیر SFTP نباید «..» داشته باشد")
        if self.s3_enabled:
            if not (self.s3_endpoint and self.s3_bucket and self.s3_access_key):
                raise ValueError("برای فعال‌کردن S3، آدرس سرویس، نام Bucket و Access Key الزامی‌اند")
            if not _S3_BUCKET_RE.fullmatch(self.s3_bucket.strip()):
                raise ValueError("نام Bucket فقط حروف کوچک انگلیسی، عدد، نقطه و خط تیره (۳ تا ۶۳ نویسه) است")
            self.s3_bucket = self.s3_bucket.strip()
        if self.s3_prefix and ".." in self.s3_prefix.split("/"):
            raise ValueError("پوشه‌ی داخل Bucket نباید «..» داشته باشد")
        return self


class BackupSettingsOut(BaseModel):
    """پاسخ GET/PUT /backup/settings؛ به‌جای رمزها فقط has_password برمی‌گردد."""

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
    smb_has_password: bool  # آیا رمز SMB ذخیره شده است
    smb_domain: str | None

    ftp_enabled: bool
    ftp_host: str | None
    ftp_port: int
    ftp_username: str | None
    ftp_has_password: bool  # آیا رمز FTP ذخیره شده است
    ftp_path: str | None
    ftp_use_tls: bool

    local_enabled: bool = False
    local_path: str | None = None

    sftp_enabled: bool = False
    sftp_host: str | None = None
    sftp_port: int = 22
    sftp_username: str | None = None
    sftp_has_password: bool = False
    sftp_path: str | None = None
    sftp_host_key: str | None = None
    sftp_fingerprint: str | None = None  # اثر انگشت کلید ذخیره‌شده‌ی سرور

    s3_enabled: bool = False
    s3_endpoint: str | None = None
    s3_region: str | None = None
    s3_bucket: str | None = None
    s3_prefix: str | None = None
    s3_access_key: str | None = None
    s3_has_secret: bool = False
    s3_path_style: bool = True

    verify_full: bool = False

    retention_mode: BackupRetentionMode
    retention_count: int
    retention_days: int

    email_enabled: bool
    email_recipients: str | None

    has_archive_password: bool = False  # آیا فایل بکاپ رمز دارد

    last_run_at: datetime | None
    last_run_success: bool | None
    last_run_message: str | None


class SmbTestConnectionIn(BaseModel):
    """بدنه POST تست اتصال SMB در backup.py."""

    host: str
    share: str
    path: str | None = None
    username: str
    password: str | None = Field(default=None, description="خالی یعنی از رمز ذخیره‌شده فعلی استفاده شود")
    domain: str | None = None


class FtpTestConnectionIn(BaseModel):
    """بدنه POST تست اتصال FTP در backup.py."""

    host: str
    port: int = 21
    username: str
    password: str | None = Field(default=None, description="خالی یعنی از رمز ذخیره‌شده فعلی استفاده شود")
    path: str | None = None
    use_tls: bool = True


class DestinationTestIn(BaseModel):
    """بدنه POST /backup/test-destination/{kind} برای local، sftp و s3 — مقادیر فعلی فرم (رمز خالی = رمز ذخیره‌شده)."""

    local_path: str | None = None

    sftp_host: str | None = None
    sftp_port: int = Field(default=22, ge=1, le=65535)
    sftp_username: str | None = None
    sftp_password: str | None = None
    sftp_path: str | None = None
    sftp_host_key: str | None = None  # کلیدی که فرم فعلاً دارد (ذخیره‌شده یا تازه تأییدشده)
    sftp_accept_new_key: bool = False  # کاربر پذیرفته که کلید سرور عوض شده است

    s3_endpoint: str | None = None
    s3_region: str | None = None
    s3_bucket: str | None = None
    s3_prefix: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_path_style: bool = True
