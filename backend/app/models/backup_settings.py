"""
مدل تنظیمات «زمان‌بندی و پشتیبان‌گیری راه‌دور» - یک ردیف واحد (Singleton،
id همیشه ۱)، چون این یک تنظیم سراسری سرور است، نه چیزی که بین چند سایت
تکرار شود.

رمزهای عبور SMB/FTP هرگز خام ذخیره نمی‌شوند - فقط رمزنگاری‌شده، با همان
app.core.security.encrypt_secret/decrypt_secret که برای SiteConnection.password_encrypted
استفاده می‌شود.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class BackupScheduleType(str, enum.Enum):
    """نوع زمان‌بندی اجرای خودکار بکاپ."""
    daily = "daily"  # هر روز، ساعت مشخص
    weekly = "weekly"  # هر هفته، یک روز/ساعت مشخص
    interval = "interval"  # هر N ساعت یک‌بار


class BackupRetentionMode(str, enum.Enum):
    """روش پاک‌سازی بکاپ‌های قدیمی روی مقصد راه‌دور."""
    count = "count"  # فقط N بکاپ آخر نگه داشته شود
    days = "days"  # فقط بکاپ‌های N روز اخیر نگه داشته شود


class BackupSettings(Base):
    """ردیف یکتای تنظیمات زمان‌بندی، مقصدها (پوشه محلی/SMB/FTP/SFTP/S3/ایمیل)، Retention و وضعیت آخرین اجرا."""
    __tablename__ = "backup_settings"

    id: Mapped[int] = mapped_column(primary_key=True)  # همیشه ۱ (Singleton)

    # --- زمان‌بندی ---
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    schedule_type: Mapped[BackupScheduleType] = mapped_column(
        Enum(BackupScheduleType, name="backup_schedule_type"), default=BackupScheduleType.daily, nullable=False
    )
    schedule_hour: Mapped[int] = mapped_column(Integer, default=3, nullable=False)  # ۰ تا ۲۳، برای daily/weekly
    schedule_minute: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # ۰ تا ۵۹
    # ۰=دوشنبه ... ۶=یکشنبه (قرارداد APScheduler cron: day_of_week) - فقط برای weekly
    schedule_weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule_interval_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)  # فقط برای interval

    # --- هدف SMB ---
    smb_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    smb_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smb_share: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smb_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # زیرپوشه اختیاری داخل share
    smb_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smb_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)  # رمزنگاری‌شده با encrypt_secret
    smb_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)  # اختیاری، برای Auth دامنه‌ای

    # --- هدف FTP ---
    ftp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ftp_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ftp_port: Mapped[int] = mapped_column(Integer, default=21, nullable=False)
    ftp_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ftp_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)  # رمزنگاری‌شده با encrypt_secret
    ftp_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ftp_use_tls: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # FTPS - پیش‌فرض امن‌تر

    # --- نگهداری (Retention) روی هدف راه‌دور ---
    retention_mode: Mapped[BackupRetentionMode] = mapped_column(
        Enum(BackupRetentionMode, name="backup_retention_mode"), default=BackupRetentionMode.count, nullable=False
    )
    retention_count: Mapped[int] = mapped_column(Integer, default=30, nullable=False)  # برای حالت count
    retention_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)  # برای حالت days

    # --- هدف ایمیل (از طریق تنظیمات SMTP سراسری - app/models/smtp_settings.py) ---
    # ایمیل برخلاف SMB/FTP پاک‌سازی (Retention) ندارد، چون آرشیو در صندوق ورودی
    # گیرنده می‌ماند و پرتال به آن دسترسی حذف ندارد.
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # چند آدرس، هرکدام در یک خط - برای پشتیبانی از چند گیرنده هم‌زمان
    email_recipients: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- پوشه یا دیسک متصل به همین سرور (Migration 135) ---
    local_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    local_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # مسیر مطلق، مثلاً /mnt/backup/faipco

    # --- هدف SFTP (Migration 135) ---
    sftp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sftp_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sftp_port: Mapped[int] = mapped_column(Integer, default=22, nullable=False)
    sftp_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sftp_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    sftp_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # کلید عمومی سرور («نوع base64») که با «تست اتصال» تأیید و ذخیره شد؛ اتصال با کلید دیگر رد می‌شود
    sftp_host_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- هدف S3 و سرویس‌های سازگار (Migration 135) ---
    s3_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    s3_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)  # مثلاً https://s3.ir-thr-at1.arvanstorage.ir
    s3_region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    s3_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    s3_prefix: Mapped[str | None] = mapped_column(String(500), nullable=True)  # پوشه داخل Bucket
    s3_access_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    s3_secret_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    s3_path_style: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # بررسی کامل سالم رسیدن (SMB/FTP/SFTP): فایل دوباره خوانده و هش آن مقایسه می‌شود؛ خاموش = فقط مقایسه‌ی حجم
    verify_full: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- رمز فایل ZIP بکاپ (AES-256، Migration 133) — رمزنگاری‌شده با encrypt_secret؛ خالی = بدون رمز ---
    archive_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- آخرین اجرا (برای نمایش وضعیت در پنل) ---
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_run_message: Mapped[str | None] = mapped_column(Text, nullable=True)
