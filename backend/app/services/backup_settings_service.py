"""
سرویس تنظیمات «زمان‌بندی بکاپ + هدف راه‌دور» - شامل CRUD تنظیمات، و منطق
اصلی «یک بکاپ بگیر و به همه هدف‌های فعال بفرست + Retention اعمال کن» که
هم توسط Scheduler (زمان‌بندی خودکار) و هم Endpoint «الان اجرا کن» صدا
زده می‌شود.
"""
from __future__ import annotations

import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_secret, encrypt_secret
from app.models.backup_settings import BackupSettings
from app.schemas.backup import BackupSettingsIn
from app.services.backup_service import create_backup_archive
from app.services.email_service import EmailError, EmailNotConfiguredError, send_email
from app.services.remote_backup_service import (
    RemoteBackupError,
    apply_ftp_retention,
    apply_smb_retention,
    upload_to_ftp,
    upload_to_smb,
)

logger = logging.getLogger("faipco.backup_scheduler")

_SETTINGS_ID = 1  # شناسه ردیف یکتای backup_settings


class BackupSettingsService:
    """خواندن و به‌روزرسانی ردیف یکتای تنظیمات بکاپ."""

    def __init__(self, db: AsyncSession):
        """ورودی: Session دیتابیس."""
        self.db = db

    async def get_settings(self) -> BackupSettings:
        """ردیف تنظیمات را برمی‌گرداند و اگر وجود نداشت آن را با مقادیر پیش‌فرض می‌سازد."""
        settings = await self.db.get(BackupSettings, _SETTINGS_ID)
        if settings is None:
            # ردیف اولیه در Migration 043 ساخته می‌شود؛ این شاخه فقط برای اطمینان است
            settings = BackupSettings(id=_SETTINGS_ID)
            self.db.add(settings)
            await self.db.commit()
            await self.db.refresh(settings)
        return settings

    async def update_settings(self, payload: BackupSettingsIn) -> BackupSettings:
        """
        همه فیلدها را از payload ذخیره می‌کند و رکورد به‌روزشده را برمی‌گرداند.
        رمزهای SMB/FTP فقط اگر مقدار داشته باشند رمزنگاری و جایگزین می‌شوند.
        """
        settings = await self.get_settings()

        # زمان‌بندی
        settings.schedule_enabled = payload.schedule_enabled
        settings.schedule_type = payload.schedule_type
        settings.schedule_hour = payload.schedule_hour
        settings.schedule_minute = payload.schedule_minute
        settings.schedule_weekday = payload.schedule_weekday
        settings.schedule_interval_hours = payload.schedule_interval_hours

        # مقصد SMB؛ رمز خالی یعنی حفظ رمز قبلی
        settings.smb_enabled = payload.smb_enabled
        settings.smb_host = payload.smb_host
        settings.smb_share = payload.smb_share
        settings.smb_path = payload.smb_path
        settings.smb_username = payload.smb_username
        if payload.smb_password:
            settings.smb_password_encrypted = encrypt_secret(payload.smb_password)
        settings.smb_domain = payload.smb_domain

        # مقصد FTP؛ رمز خالی یعنی حفظ رمز قبلی
        settings.ftp_enabled = payload.ftp_enabled
        settings.ftp_host = payload.ftp_host
        settings.ftp_port = payload.ftp_port
        settings.ftp_username = payload.ftp_username
        if payload.ftp_password:
            settings.ftp_password_encrypted = encrypt_secret(payload.ftp_password)
        settings.ftp_path = payload.ftp_path
        settings.ftp_use_tls = payload.ftp_use_tls

        # سیاست نگهداری و مقصد ایمیل
        settings.retention_mode = payload.retention_mode
        settings.retention_count = payload.retention_count
        settings.retention_days = payload.retention_days

        settings.email_enabled = payload.email_enabled
        settings.email_recipients = payload.email_recipients

        await self.db.commit()
        await self.db.refresh(settings)
        return settings


def _decrypt_or_empty(encrypted: str | None) -> str:
    """رمز رمزنگاری‌شده را باز می‌کند؛ برای مقدار خالی رشته خالی برمی‌گرداند."""
    return decrypt_secret(encrypted) if encrypted else ""


async def run_scheduled_backup(db: AsyncSession) -> None:
    """
    یک بکاپ می‌گیرد و به همه هدف‌های راه‌دور فعال (SMB و/یا FTP - هر دو اگر
    هر دو فعال باشند) می‌فرستد، سپس روی هرکدام Retention اعمال می‌کند.
    نتیجه (موفق/ناموفق + پیام) در خودِ رکورد تنظیمات ذخیره می‌شود تا در
    پنل قابل‌مشاهده باشد. ورودی: Session دیتابیس. خروجی: ندارد.
    """
    service = BackupSettingsService(db)
    settings = await service.get_settings()

    # اگر هیچ مقصدی فعال نیست، بکاپی ساخته نمی‌شود
    if not (settings.smb_enabled or settings.ftp_enabled or settings.email_enabled):
        logger.info("بکاپ زمان‌بندی‌شده اجرا شد ولی هیچ هدف راه‌دوری فعال نیست - رد شد")
        return

    # ساخت آرشیو؛ خطا در last_run_* ثبت و اجرا متوقف می‌شود
    try:
        archive_bytes = await create_backup_archive()
    except Exception as e:  # noqa: BLE001 - هر خطای غیرمنتظره باید در وضعیت آخرین اجرا ثبت شود، نه کل Job را بترکاند
        logger.exception("ساخت آرشیو بکاپ زمان‌بندی‌شده ناموفق بود")
        settings.last_run_at = datetime.now(timezone.utc)
        settings.last_run_success = False
        settings.last_run_message = f"ساخت بکاپ ناموفق بود: {e}"
        await db.commit()
        return

    filename = f"faipco-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.zip"
    messages: list[str] = []
    any_failure = False

    # آرشیو در یک فایل موقت نوشته می‌شود تا آپلودکننده‌ها از مسیر فایل استفاده کنند
    with tempfile.TemporaryDirectory() as tmp_dir:
        local_path = Path(tmp_dir) / filename
        local_path.write_bytes(archive_bytes)

        # آپلود به SMB و سپس حذف بکاپ‌های قدیمی طبق Retention
        if settings.smb_enabled:
            try:
                upload_to_smb(
                    local_path,
                    filename,
                    host=settings.smb_host,
                    share=settings.smb_share,
                    path=settings.smb_path,
                    username=settings.smb_username,
                    password=_decrypt_or_empty(settings.smb_password_encrypted),
                    domain=settings.smb_domain,
                )
                deleted = apply_smb_retention(
                    host=settings.smb_host,
                    share=settings.smb_share,
                    path=settings.smb_path,
                    username=settings.smb_username,
                    password=_decrypt_or_empty(settings.smb_password_encrypted),
                    domain=settings.smb_domain,
                    mode=settings.retention_mode.value,
                    retention_count=settings.retention_count,
                    retention_days=settings.retention_days,
                )
                messages.append(f"SMB: آپلود موفق ({deleted} بکاپ قدیمی طبق سیاست نگهداری حذف شد)")
            except RemoteBackupError as e:
                any_failure = True
                messages.append(f"SMB: {e}")
                logger.error("آپلود بکاپ زمان‌بندی‌شده به SMB ناموفق بود: %s", e)

        # آپلود به FTP و سپس حذف بکاپ‌های قدیمی طبق Retention
        if settings.ftp_enabled:
            try:
                upload_to_ftp(
                    local_path,
                    filename,
                    host=settings.ftp_host,
                    port=settings.ftp_port,
                    username=settings.ftp_username,
                    password=_decrypt_or_empty(settings.ftp_password_encrypted),
                    path=settings.ftp_path,
                    use_tls=settings.ftp_use_tls,
                )
                deleted = apply_ftp_retention(
                    host=settings.ftp_host,
                    port=settings.ftp_port,
                    username=settings.ftp_username,
                    password=_decrypt_or_empty(settings.ftp_password_encrypted),
                    path=settings.ftp_path,
                    use_tls=settings.ftp_use_tls,
                    mode=settings.retention_mode.value,
                    retention_count=settings.retention_count,
                    retention_days=settings.retention_days,
                )
                messages.append(f"FTP: آپلود موفق ({deleted} بکاپ قدیمی طبق سیاست نگهداری حذف شد)")
            except RemoteBackupError as e:
                any_failure = True
                messages.append(f"FTP: {e}")
                logger.error("آپلود بکاپ زمان‌بندی‌شده به FTP ناموفق بود: %s", e)

        # ارسال به ایمیل به صورت پیوست
        if settings.email_enabled:
            # محدودیت اندازه پیوست: اکثر سرورهای SMTP رایج (Gmail، Outlook، ...)
            # پیوست بزرگ‌تر از ۲۰-۲۵ مگابایت را رد می‌کنند؛ این‌جا با پیام روشن رد می‌شود.
            max_email_size_bytes = 20 * 1024 * 1024
            if len(archive_bytes) > max_email_size_bytes:
                any_failure = True
                size_mb = len(archive_bytes) / (1024 * 1024)
                messages.append(
                    f"ایمیل: حجم بکاپ ({size_mb:.1f} مگابایت) بیش از حد مجاز پیوست ایمیل (۲۰ مگابایت) است — ارسال نشد"
                )
            else:
                # هر خط email_recipients یک گیرنده؛ ارسال جداگانه به هر گیرنده
                recipients = [r.strip() for r in (settings.email_recipients or "").splitlines() if r.strip()]
                email_failures = []
                email_successes = 0
                for recipient in recipients:
                    try:
                        await send_email(
                            db,
                            to_address=recipient,
                            subject=f"بکاپ خودکار پرتال سازمانی — {filename}",
                            body_text="بکاپ زمان‌بندی‌شده به‌صورت خودکار تهیه و به این ایمیل پیوست شده است.",
                            attachment=(filename, archive_bytes),
                        )
                        email_successes += 1
                    except (EmailNotConfiguredError, EmailError) as e:
                        email_failures.append(f"{recipient}: {e}")
                        logger.error("ارسال بکاپ زمان‌بندی‌شده به ایمیل %s ناموفق بود: %s", recipient, e)

                if email_failures:
                    any_failure = True
                    messages.append(f"ایمیل: {email_successes} موفق، ناموفق‌ها: {'; '.join(email_failures)}")
                else:
                    messages.append(f"ایمیل: با موفقیت به {email_successes} گیرنده ارسال شد")

    # ثبت نتیجه نهایی اجرا برای نمایش در پنل
    settings.last_run_at = datetime.now(timezone.utc)
    settings.last_run_success = not any_failure
    settings.last_run_message = " | ".join(messages) if messages else "هیچ هدفی فعال نبود"
    await db.commit()
