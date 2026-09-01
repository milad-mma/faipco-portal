"""
/backup/export    (GET)   دانلود یک بکاپ کامل (Schema + Data) — فقط Admin کامل.
/backup/restore   (POST)  بازیابی یک بکاپ از همین پنل، روی همین سرور — فقط Admin کامل.

⚠️ این قابلیت فقط برای بازیابی روی همین سرور طراحی شده (نه Clone به سرور
دیگر). چون بازیابی واقعی نیاز به متوقف‌کردن خودِ سرویس دارد (وگرنه
Connection Pool زنده‌ی سرویس روی همان جدول‌هایی که pg_restore می‌خواهد
بازسازی کند قفل می‌گیرد و pg_restore برای همیشه منتظر می‌ماند)، و چون این
درخواست HTTP از داخل همان سرویسی می‌آید که قرار است متوقف شود، خودِ کار
واقعی (توقف → pg_restore → migrate → روشن‌کردن دوباره) به یک اسکریپت
کاملاً مستقل واگذار می‌شود؛ این Endpoint فقط اعتبارسنجی می‌کند و آن
اسکریپت را راه می‌اندازد، بدون این‌که منتظر اتمامش بماند.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.core.security import decrypt_secret
from app.db.session import get_db
from app.schemas.backup import BackupSettingsIn, BackupSettingsOut, FtpTestConnectionIn, SmbTestConnectionIn
from app.services.backup_service import (
    RESTORE_CONFIRMATION_PHRASE,
    BackupError,
    create_backup_archive,
    get_restore_status,
    schedule_restore,
    validate_and_stage_archive,
)
from app.services.backup_settings_service import BackupSettingsService, run_scheduled_backup
from app.services.remote_backup_service import RemoteBackupError, test_ftp_connection, test_smb_connection

logger = logging.getLogger("faipco.backup")
router = APIRouter()


@router.get("/export")
async def export_backup(
    _user=Depends(require_permission("system.backup")),
):
    try:
        archive_bytes = await create_backup_archive()
    except BackupError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception:
        logger.exception("ساخت بکاپ با خطای پیش‌بینی‌نشده مواجه شد")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ساخت بکاپ با خطای پیش‌بینی‌نشده مواجه شد — جزئیات کامل در لاگ سرور ثبت شد.",
        )

    filename = f"faipco-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.zip"
    return Response(
        content=archive_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/restore")
async def restore_backup(
    confirm: str = Form(..., description=f'برای تأیید باید دقیقاً "{RESTORE_CONFIRMATION_PHRASE}" ارسال شود'),
    file: UploadFile = File(..., description="فایلی که از همین صفحه «پشتیبان‌گیری» دانلود شده"),
    _user=Depends(require_permission("system.backup")),
):
    """
    داده و ساختار فعلی دیتابیس همین سرور را کاملاً با محتوای فایل بکاپ
    جایگزین می‌کند — برگشت‌ناپذیر است.

    این Endpoint فقط اعتبارسنجی سریع انجام می‌دهد و برمی‌گردد — خودِ Restore
    واقعی (که سرویس را چند لحظه متوقف می‌کند) در پس‌زمینه ادامه پیدا می‌کند.
    یعنی این پاسخ به معنای «بازیابی موفق شد» نیست، فقط یعنی «شروع شد» —
    برای دیدن نتیجه واقعی، بعد از ۳۰-۶۰ ثانیه صفحه را Refresh کنید.
    """
    file_bytes = await file.read()
    try:
        dump_path = validate_and_stage_archive(file_bytes, confirm_phrase=confirm)
    except BackupError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logger.exception("اعتبارسنجی فایل بکاپ با خطای پیش‌بینی‌نشده مواجه شد")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="بررسی فایل بکاپ با خطای پیش‌بینی‌نشده مواجه شد — جزئیات کامل در لاگ سرور ثبت شد.",
        )

    try:
        schedule_restore(dump_path)
    except BackupError as e:
        logger.error("راه‌اندازی فرآیند بازیابی ناموفق بود: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception:
        logger.exception("راه‌اندازی فرآیند بازیابی با خطای کاملاً پیش‌بینی‌نشده مواجه شد")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="راه‌اندازی فرآیند بازیابی با خطای پیش‌بینی‌نشده مواجه شد — جزئیات کامل در لاگ سرور ثبت شد.",
        )

    return {
        "success": True,
        "message": "بازیابی شروع شد. سرویس چند لحظه (معمولاً کمتر از یک دقیقه) در دسترس نخواهد بود، "
        "سپس خودکار دوباره بالا می‌آید — نیازی به ورود دوباره نیست. لطفاً ۳۰ تا ۶۰ ثانیه صبر کنید و "
        "بعد صفحه را Refresh کنید تا نتیجه واقعی را ببینید.",
    }


@router.get("/restore-status")
async def restore_status(
    _user=Depends(require_permission("system.backup")),
):
    """
    وضعیت زنده آخرین Restore — پنل هر چند ثانیه یک‌بار این را می‌پرسد تا
    مراحل واقعی (نه یک شمارش‌معکوس کور) نشان بدهد. طبیعی است که خودِ همین
    Endpoint هم برای چند ثانیه (دقیقاً همان لحظه‌ای که سرویس Stop/Start
    می‌شود) در دسترس نباشد — فرانت‌اند باید آن گپ را با Retry پر کند.
    """
    return get_restore_status()


def _to_settings_out(settings) -> BackupSettingsOut:
    return BackupSettingsOut(
        schedule_enabled=settings.schedule_enabled,
        schedule_type=settings.schedule_type,
        schedule_hour=settings.schedule_hour,
        schedule_minute=settings.schedule_minute,
        schedule_weekday=settings.schedule_weekday,
        schedule_interval_hours=settings.schedule_interval_hours,
        smb_enabled=settings.smb_enabled,
        smb_host=settings.smb_host,
        smb_share=settings.smb_share,
        smb_path=settings.smb_path,
        smb_username=settings.smb_username,
        smb_has_password=bool(settings.smb_password_encrypted),
        smb_domain=settings.smb_domain,
        ftp_enabled=settings.ftp_enabled,
        ftp_host=settings.ftp_host,
        ftp_port=settings.ftp_port,
        ftp_username=settings.ftp_username,
        ftp_has_password=bool(settings.ftp_password_encrypted),
        ftp_path=settings.ftp_path,
        ftp_use_tls=settings.ftp_use_tls,
        retention_mode=settings.retention_mode,
        retention_count=settings.retention_count,
        retention_days=settings.retention_days,
        last_run_at=settings.last_run_at,
        last_run_success=settings.last_run_success,
        last_run_message=settings.last_run_message,
    )


@router.get("/settings", response_model=BackupSettingsOut)
async def get_backup_settings(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.backup")),
):
    """رمزهای عبور هرگز در پاسخ برنمی‌گردند — فقط smb_has_password/ftp_has_password (بولی)."""
    settings = await BackupSettingsService(db).get_settings()
    return _to_settings_out(settings)


@router.put("/settings", response_model=BackupSettingsOut)
async def update_backup_settings(
    payload: BackupSettingsIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.backup")),
):
    """
    برای رمزهای SMB/FTP: اگر خالی فرستاده شود، رمز قبلاً ذخیره‌شده دست‌نخورده
    می‌ماند (نیازی به وارد‌کردن دوباره در هر ویرایش نیست).
    """
    settings = await BackupSettingsService(db).update_settings(payload)
    return _to_settings_out(settings)


@router.post("/test-smb")
async def test_smb(
    payload: SmbTestConnectionIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.backup")),
):
    password = payload.password
    if not password:
        settings = await BackupSettingsService(db).get_settings()
        if not settings.smb_password_encrypted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="رمز عبور وارد نشده و رمز ذخیره‌شده قبلی هم وجود ندارد.",
            )
        password = decrypt_secret(settings.smb_password_encrypted)

    try:
        test_smb_connection(
            host=payload.host,
            share=payload.share,
            path=payload.path,
            username=payload.username,
            password=password,
            domain=payload.domain,
        )
    except RemoteBackupError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"success": True, "message": "اتصال به SMB با موفقیت برقرار شد."}


@router.post("/test-ftp")
async def test_ftp(
    payload: FtpTestConnectionIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.backup")),
):
    password = payload.password
    if not password:
        settings = await BackupSettingsService(db).get_settings()
        if not settings.ftp_password_encrypted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="رمز عبور وارد نشده و رمز ذخیره‌شده قبلی هم وجود ندارد.",
            )
        password = decrypt_secret(settings.ftp_password_encrypted)

    try:
        test_ftp_connection(
            host=payload.host,
            port=payload.port,
            username=payload.username,
            password=password,
            path=payload.path,
            use_tls=payload.use_tls,
        )
    except RemoteBackupError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"success": True, "message": "اتصال به FTP با موفقیت برقرار شد."}


@router.post("/run-now")
async def run_backup_now(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.backup")),
):
    """
    بلافاصله (نه در پس‌زمینه) یک بکاپ می‌گیرد و به هدف‌های راه‌دور فعال
    می‌فرستد - برخلاف Restore، این عملیات سرویس را متوقف نمی‌کند، پس
    نیازی به الگوی «شروع کن و برگرد» نیست؛ همین‌جا منتظر اتمام می‌مانیم.
    """
    await run_scheduled_backup(db)
    settings = await BackupSettingsService(db).get_settings()
    if settings.last_run_success is False:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=settings.last_run_message)
    return {"success": True, "message": settings.last_run_message}
