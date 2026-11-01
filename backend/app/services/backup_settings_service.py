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

from app.core.backup_dest_rules import KINDS, LABELS, sha256_file
from app.core.security import decrypt_secret, encrypt_secret
from app.models.backup_settings import BackupSettings
from app.schemas.backup import BackupSettingsIn
from app.services.email_service import EmailError, EmailNotConfiguredError, send_email
from app.services.remote_backup_service import (
    RemoteBackupError,
    apply_ftp_retention,
    apply_smb_retention,
    upload_to_ftp,
    upload_to_smb,
    verify_ftp_file,
    verify_smb_file,
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

        # پوشه یا دیسک محلی
        settings.local_enabled = payload.local_enabled
        settings.local_path = payload.local_path

        # مقصد SFTP؛ رمز خالی = حفظ رمز قبلی. کلید سرور فقط اگر فرم کلید (تأییدشده با تست) فرستاده باشد عوض می‌شود؛
        # تغییر سرور/پورت بدون کلید تازه، کلید قبلی را پاک می‌کند تا دوباره تست و تأیید شود.
        if (payload.sftp_host or "") != (settings.sftp_host or "") or payload.sftp_port != settings.sftp_port:
            settings.sftp_host_key = None
        settings.sftp_enabled = payload.sftp_enabled
        settings.sftp_host = (payload.sftp_host or "").strip() or None
        settings.sftp_port = payload.sftp_port
        settings.sftp_username = payload.sftp_username
        if payload.sftp_password:
            settings.sftp_password_encrypted = encrypt_secret(payload.sftp_password)
        settings.sftp_path = payload.sftp_path
        if payload.sftp_host_key:
            settings.sftp_host_key = payload.sftp_host_key.strip()

        # مقصد S3؛ Secret Key خالی = حفظ کلید قبلی
        settings.s3_enabled = payload.s3_enabled
        settings.s3_endpoint = (payload.s3_endpoint or "").strip() or None
        settings.s3_region = (payload.s3_region or "").strip() or None
        settings.s3_bucket = payload.s3_bucket
        settings.s3_prefix = (payload.s3_prefix or "").strip().strip("/") or None
        settings.s3_access_key = (payload.s3_access_key or "").strip() or None
        if payload.s3_secret_key:
            settings.s3_secret_key_encrypted = encrypt_secret(payload.s3_secret_key)
        settings.s3_path_style = payload.s3_path_style

        settings.verify_full = payload.verify_full

        # سیاست نگهداری و مقصد ایمیل
        settings.retention_mode = payload.retention_mode
        settings.retention_count = payload.retention_count
        settings.retention_days = payload.retention_days

        settings.email_enabled = payload.email_enabled
        settings.email_recipients = payload.email_recipients

        # رمز فایل بکاپ: خالی = حفظ رمز قبلی؛ clear = برداشتن رمز. تغییر یا برداشتن رمزِ موجود فقط با رمز فعلی.
        if settings.archive_password_encrypted and (payload.archive_password_clear or payload.archive_password):
            current = _decrypt_or_empty(settings.archive_password_encrypted)
            import hmac

            if not payload.archive_password_current or not hmac.compare_digest(
                payload.archive_password_current.encode(), current.encode()
            ):
                raise ValueError("برای تغییر یا برداشتن رمز فایل بکاپ، رمز فعلی را درست وارد کنید")
        if payload.archive_password_clear:
            settings.archive_password_encrypted = None
        elif payload.archive_password:
            if len(payload.archive_password) < 8:
                raise ValueError("رمز فایل بکاپ باید حداقل ۸ نویسه باشد")
            settings.archive_password_encrypted = encrypt_secret(payload.archive_password)

        await self.db.commit()
        await self.db.refresh(settings)
        return settings


def _decrypt_or_empty(encrypted: str | None) -> str:
    """رمز رمزنگاری‌شده را باز می‌کند؛ برای مقدار خالی رشته خالی برمی‌گرداند."""
    return decrypt_secret(encrypted) if encrypted else ""


EMAIL_MAX_BYTES = 20 * 1024 * 1024


def archive_password(settings: BackupSettings) -> str | None:
    """رمز فایل بکاپ (اگر تعیین شده)."""
    return _decrypt_or_empty(settings.archive_password_encrypted) or None


def enabled_kinds(settings: BackupSettings) -> list[str]:
    """مقصدهای فعال به ترتیب ثابت."""
    flags = {
        "local": settings.local_enabled, "smb": settings.smb_enabled, "ftp": settings.ftp_enabled,
        "sftp": settings.sftp_enabled, "s3": settings.s3_enabled, "email": settings.email_enabled,
    }
    return [k for k in KINDS if flags[k]]


def _retention(settings: BackupSettings) -> dict:
    return {"mode": settings.retention_mode.value, "retention_count": settings.retention_count,
            "retention_days": settings.retention_days}


def _sftp_conn(settings: BackupSettings) -> dict:
    return {"host": settings.sftp_host, "port": settings.sftp_port, "username": settings.sftp_username,
            "password": _decrypt_or_empty(settings.sftp_password_encrypted), "path": settings.sftp_path,
            "host_key": settings.sftp_host_key}


def _s3_conn(settings: BackupSettings) -> dict:
    return {"endpoint": settings.s3_endpoint, "region": settings.s3_region, "bucket": settings.s3_bucket,
            "prefix": settings.s3_prefix, "access_key": settings.s3_access_key,
            "secret_key": _decrypt_or_empty(settings.s3_secret_key_encrypted), "path_style": settings.s3_path_style}


def _smb_conn(settings: BackupSettings) -> dict:
    return {"host": settings.smb_host, "share": settings.smb_share, "path": settings.smb_path,
            "username": settings.smb_username, "password": _decrypt_or_empty(settings.smb_password_encrypted),
            "domain": settings.smb_domain}


def _ftp_conn(settings: BackupSettings) -> dict:
    return {"host": settings.ftp_host, "port": settings.ftp_port, "username": settings.ftp_username,
            "password": _decrypt_or_empty(settings.ftp_password_encrypted), "path": settings.ftp_path,
            "use_tls": settings.ftp_use_tls}


def _deliver_sync(settings: BackupSettings, kind: str, path: Path, filename: str, sha256: str) -> str:
    """ارسال + بررسی سالم رسیدن + Retention برای یک مقصد غیر ایمیل (همگام). خروجی: پیام. خطا: RemoteBackupError."""
    from app.services import backup_destinations as D

    size = path.stat().st_size
    full = sha256 if settings.verify_full else None
    ret = _retention(settings)
    if kind == "local":
        D.upload_local(path, filename, sha256, path=settings.local_path)
        deleted = D.retention_local(path=settings.local_path, **ret)
        check = "هش بررسی شد"
    elif kind == "smb":
        conn = _smb_conn(settings)
        upload_to_smb(path, filename, **conn)
        verify_smb_file(filename, size, full, **conn)
        deleted = apply_smb_retention(**conn, **ret)
        check = "هش بررسی شد" if full else "حجم بررسی شد"
    elif kind == "ftp":
        conn = _ftp_conn(settings)
        upload_to_ftp(path, filename, **conn)
        verify_ftp_file(filename, size, full, **conn)
        deleted = apply_ftp_retention(**conn, **ret)
        check = "هش بررسی شد" if full else "حجم بررسی شد"
    elif kind == "sftp":
        conn = _sftp_conn(settings)
        D.upload_sftp(path, filename, sha256, verify_full=settings.verify_full, **conn)
        deleted = D.retention_sftp(**conn, **ret)
        check = "هش بررسی شد" if settings.verify_full else "حجم بررسی شد"
    elif kind == "s3":
        conn = _s3_conn(settings)
        D.upload_s3(path, filename, sha256, **conn)
        deleted = D.retention_s3(**conn, **ret)
        check = "هش توسط S3 بررسی شد"
    else:
        raise RemoteBackupError(f"مقصد ناشناخته: {kind}")
    return f"رسید و سالم است ({check}؛ {deleted} بکاپ قدیمی طبق سیاست نگهداری حذف شد)"


async def deliver_to(db: AsyncSession, settings: BackupSettings, kind: str, path: Path, filename: str,
                     sha256: str) -> str:
    """ارسال یک فایل بکاپ به یک مقصد. خروجی: پیام موفقیت. خطا: RemoteBackupError/EmailError (پیام قابل نمایش)."""
    if kind != "email":
        return await asyncio.to_thread(_deliver_sync, settings, kind, path, filename, sha256)
    size = path.stat().st_size
    if size > EMAIL_MAX_BYTES:
        # تلاش دوباره فایده ندارد؛ پیام خطا ولی بدون صف (فراخواننده با PermanentError تشخیص می‌دهد)
        raise PermanentDeliveryError(
            f"حجم بکاپ ({size / 2**20:.1f} مگابایت) بیش از حد مجاز پیوست ایمیل (۲۰ مگابایت) است — ارسال نشد"
        )
    data = path.read_bytes()
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
    if failures:
        raise RemoteBackupError(f"{ok} موفق، ناموفق‌ها: {'; '.join(failures)}"[:500])
    return f"با موفقیت به {ok} گیرنده ارسال شد"


class PermanentDeliveryError(RemoteBackupError):
    """خطایی که تلاش دوباره درستش نمی‌کند (مثل حجم زیاد برای ایمیل) — به صف نمی‌رود."""


async def run_scheduled_backup(db: AsyncSession, trigger: str = "scheduled", user_id: int | None = None,
                               send_to_destinations: bool = True, keep_file: bool = False) -> dict:
    """
    یک ZIP بکاپ (دیتابیس + فایل‌های آپلودی اتوماسیون، با رمز فایل بکاپ اگر تعیین شده) می‌سازد و به مقصدهای فعال جدا جدا
    می‌فرستد؛ هر مقصد سالم رسیدن فایل را بررسی و Retention خودش را اعمال می‌کند. خرابی یک مقصد مانع بقیه نمی‌شود و
    مقصدهای ناموفق با همان فایل به صف تلاش دوباره می‌روند (services/backup_retry_queue.py). نتیجه در last_run_*.
    فراخواننده Advisory Lock بکاپ را گرفته است. keep_file=True (دانلود) فایل را برای تحویل نگه می‌دارد.
    خروجی: {"ok": bool، "filename": نام فایل یا None، "message": متن نتیجه}.
    """
    from app.services import backup_retry_queue as queue
    from app.services.backup_archive import (
        ArchiveError,
        backup_dir,
        build_archive,
        remove_old_local,
    )

    service = BackupSettingsService(db)
    settings = await service.get_settings()
    kinds = enabled_kinds(settings) if send_to_destinations else []
    if trigger == "scheduled" and not kinds:
        logger.info("بکاپ زمان‌بندی‌شده اجرا شد ولی هیچ مقصدی فعال نیست - رد شد")
        return {"ok": True, "filename": None, "message": "هیچ مقصدی فعال نیست"}

    try:
        built = await build_archive(password=archive_password(settings))
    except Exception as e:
        logger.exception("ساخت بکاپ ناموفق بود")
        msg = (str(e) if isinstance(e, ArchiveError) else f"ساخت بکاپ ناموفق بود: {e}")[:2000]
        if trigger != "download":
            settings.last_run_at, settings.last_run_success, settings.last_run_message = datetime.now(timezone.utc), False, msg
            await db.commit()
        return {"ok": False, "filename": None, "message": msg}

    file_count = built["manifest"]["files"]["count"]
    local_path: Path = built["path"]
    filename = built["filename"]
    created_at = datetime.now(timezone.utc)
    sha256 = await asyncio.to_thread(sha256_file, local_path) if kinds else ""
    results: dict[str, dict] = {}
    failures: dict[str, str] = {}

    for kind in kinds:
        try:
            msg = await deliver_to(db, settings, kind, local_path, filename, sha256)
            results[kind] = {"ok": True, "message": msg}
            queue.note_success(kind, created_at)
        except PermanentDeliveryError as e:
            results[kind] = {"ok": False, "message": str(e)[:500]}
        except Exception as e:  # noqa: BLE001 — خطای هر مقصد جدا ثبت و به صف سپرده می‌شود
            text = str(e)[:500] or e.__class__.__name__
            results[kind] = {"ok": False, "message": text + " — در صف تلاش دوباره"}
            failures[kind] = text
            logger.error("ارسال بکاپ به %s ناموفق بود: %s", kind, text)

    # فایل یا به صف تلاش دوباره می‌رود، یا (دانلود) برای تحویل می‌ماند، یا پاک می‌شود
    if failures and not keep_file:
        try:
            await asyncio.to_thread(queue.enqueue, local_path, filename, sha256, created_at, failures)
        except OSError:
            logger.exception("انتقال بکاپ به صف تلاش دوباره ناموفق بود")
    await asyncio.to_thread(remove_old_local, {filename} if keep_file else set())
    if not keep_file:
        (backup_dir() / filename).unlink(missing_ok=True)

    parts = [f"{LABELS[k]}: {v['message']}" for k, v in results.items()]
    if not parts:
        parts = [f"بکاپ ساخته شد ({file_count} فایل آپلودی، {built['size'] / 2**20:.1f} مگابایت)"]
    any_failure = any(not v["ok"] for v in results.values())
    message = " | ".join(parts)[:2000]
    if trigger != "download":
        settings.last_run_at, settings.last_run_success, settings.last_run_message = (
            datetime.now(timezone.utc), not any_failure, message
        )
        await db.commit()
    return {"ok": not any_failure, "filename": filename, "message": message}
