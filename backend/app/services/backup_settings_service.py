"""
سرویس تنظیمات «زمان‌بندی بکاپ + هدف راه‌دور» - شامل CRUD تنظیمات، و منطق
اصلی «یک بکاپ بگیر و به همه هدف‌های فعال بفرست + Retention اعمال کن» که
هم توسط Scheduler (زمان‌بندی خودکار) و هم Endpoint «الان اجرا کن» صدا
زده می‌شود.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_secret, encrypt_secret
from app.models.backup_settings import BackupSettings
from app.models.backup_v4 import BackupRun
from app.schemas.backup import BackupSettingsIn
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


LOCAL_KEEP = 2  # تعداد نسخه‌ی محلی نگه‌داشته‌شده در /var/lib/faipco/backups (برای دانلود و بازیابی از پنل)
EMAIL_MAX_BYTES = 20 * 1024 * 1024


async def run_scheduled_backup(db: AsyncSession, trigger: str = "scheduled", user_id: int | None = None,
                               send_to_destinations: bool = True) -> BackupRun:
    """
    یک مجموعه‌ی بکاپ v4 می‌سازد (backup_archive.build_archive: دیتابیس + فایل‌های اتوماسیون، جریانی، در صورت وجود کلید
    رمزنگاری‌شده)، به همه‌ی مقصدهای فعال (SMB، FTP، ایمیل) جدا جدا می‌فرستد و Retention هر مقصد را اعمال می‌کند؛ خرابی یک
    مقصد مانع بقیه نمی‌شود. یک نسخه‌ی محلی (LOCAL_KEEP آخر) برای دانلود/بازیابی از پنل می‌ماند. نتیجه در backup_runs و
    last_run_* ثبت می‌شود. فراخواننده Advisory Lock بکاپ را گرفته است. خروجی: ردیف BackupRun.
    """
    import uuid

    from app.services.backup_archive import ArchiveError, build_archive, prune_local

    service = BackupSettingsService(db)
    settings = await service.get_settings()
    run = BackupRun(set_id=uuid.uuid4().hex, trigger=trigger, status="running", started_by=user_id)
    db.add(run)
    await db.commit()
    await db.refresh(run)

    if trigger == "scheduled" and not (settings.smb_enabled or settings.ftp_enabled or settings.email_enabled):
        logger.info("بکاپ زمان‌بندی‌شده: هیچ مقصد راه‌دوری فعال نیست؛ فقط نسخه‌ی محلی ساخته می‌شود")

    try:
        built = await build_archive(trigger=trigger, user_id=user_id)
    except Exception as e:  # noqa: BLE001 - هر خطا باید در وضعیت ثبت شود، نه Job را بترکاند
        logger.exception("ساخت بکاپ ناموفق بود")
        msg = str(e) if isinstance(e, ArchiveError) else f"ساخت بکاپ ناموفق بود: {e}"
        run.status, run.message, run.finished_at = "failed", msg[:2000], datetime.now(timezone.utc)
        settings.last_run_at, settings.last_run_success, settings.last_run_message = run.finished_at, False, msg[:2000]
        await db.commit()
        return run

    run.set_id = built["set_id"]
    run.filename, run.size, run.key_id = built["filename"], built["size"], built["key_id"]
    run.file_count = built["manifest"]["files"]["count"]
    run.files_bytes = built["manifest"]["files"]["bytes"]
    run.manifest_sha256 = built["manifest_sha256"]
    run.consistency_method = built["manifest"]["consistency_method"]
    local_path: Path = built["path"]
    filename = built["filename"]
    results: dict[str, dict] = {}

    if send_to_destinations and settings.smb_enabled:
        try:
            await asyncio.to_thread(
                upload_to_smb, local_path, filename, host=settings.smb_host, share=settings.smb_share,
                path=settings.smb_path, username=settings.smb_username,
                password=_decrypt_or_empty(settings.smb_password_encrypted), domain=settings.smb_domain,
            )
            deleted = await asyncio.to_thread(
                apply_smb_retention, host=settings.smb_host, share=settings.smb_share, path=settings.smb_path,
                username=settings.smb_username, password=_decrypt_or_empty(settings.smb_password_encrypted),
                domain=settings.smb_domain, mode=settings.retention_mode.value,
                retention_count=settings.retention_count, retention_days=settings.retention_days,
            )
            results["smb"] = {"ok": True, "message": f"آپلود موفق ({deleted} بکاپ قدیمی حذف شد)"}
        except RemoteBackupError as e:
            results["smb"] = {"ok": False, "message": str(e)[:500]}
            logger.error("ارسال بکاپ به SMB ناموفق بود: %s", e)

    if send_to_destinations and settings.ftp_enabled:
        try:
            await asyncio.to_thread(
                upload_to_ftp, local_path, filename, host=settings.ftp_host, port=settings.ftp_port,
                username=settings.ftp_username, password=_decrypt_or_empty(settings.ftp_password_encrypted),
                path=settings.ftp_path, use_tls=settings.ftp_use_tls,
            )
            deleted = await asyncio.to_thread(
                apply_ftp_retention, host=settings.ftp_host, port=settings.ftp_port, username=settings.ftp_username,
                password=_decrypt_or_empty(settings.ftp_password_encrypted), path=settings.ftp_path,
                use_tls=settings.ftp_use_tls, mode=settings.retention_mode.value,
                retention_count=settings.retention_count, retention_days=settings.retention_days,
            )
            results["ftp"] = {"ok": True, "message": f"آپلود موفق ({deleted} بکاپ قدیمی حذف شد)"}
        except RemoteBackupError as e:
            results["ftp"] = {"ok": False, "message": str(e)[:500]}
            logger.error("ارسال بکاپ به FTP ناموفق بود: %s", e)

    if send_to_destinations and settings.email_enabled:
        size = local_path.stat().st_size
        if size > EMAIL_MAX_BYTES:
            results["email"] = {
                "ok": False,
                "message": f"حجم بکاپ ({size / 2**20:.1f} مگابایت) بیش از حد مجاز پیوست ایمیل (۲۰ مگابایت) است — ارسال نشد",
            }
        else:
            data = local_path.read_bytes()
            recipients = [r.strip() for r in (settings.email_recipients or "").splitlines() if r.strip()]
            failures, ok = [], 0
            for recipient in recipients:
                try:
                    await send_email(
                        db, to_address=recipient, subject=f"بکاپ خودکار پرتال سازمانی — {filename}",
                        body_text="بکاپ زمان‌بندی‌شده به‌صورت خودکار تهیه و به این ایمیل پیوست شده است.",
                        attachment=(filename, data),
                    )
                    ok += 1
                except (EmailNotConfiguredError, EmailError) as e:
                    failures.append(f"{recipient}: {e}")
            results["email"] = (
                {"ok": False, "message": f"{ok} موفق، ناموفق‌ها: {'; '.join(failures)}"[:500]}
                if failures else {"ok": True, "message": f"به {ok} گیرنده ارسال شد"}
            )

    await asyncio.to_thread(prune_local, LOCAL_KEEP)
    labels = {"smb": "SMB", "ftp": "FTP", "email": "ایمیل"}
    parts = [f"ساخت موفق ({run.file_count} فایل اتوماسیون، {run.size / 2**20:.1f} مگابایت"
             + ("، رمزنگاری‌شده" if run.key_id else "، بدون رمزنگاری") + ")"]
    parts += [f"{labels[k]}: {v['message']}" for k, v in results.items()]
    any_failure = any(not v["ok"] for v in results.values())
    run.destinations = results
    run.status = "partial" if any_failure else "success"
    run.message = " | ".join(parts)[:2000]
    run.finished_at = datetime.now(timezone.utc)
    settings.last_run_at, settings.last_run_success, settings.last_run_message = run.finished_at, not any_failure, run.message
    await db.commit()
    return run
