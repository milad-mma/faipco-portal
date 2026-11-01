"""
Endpoint های پشتیبان‌گیری و بازیابی (همه با مجوز system.backup).

/backup/export          (GET)   دانلود یک بکاپ کامل (Schema + Data) به صورت ZIP
/backup/restore         (POST)  بازیابی یک بکاپ روی همین سرور (در پس‌زمینه)
/backup/restore-status  (GET)   وضعیت زنده آخرین بازیابی
/backup/settings        (GET/PUT) تنظیمات زمان‌بندی و مقصدهای راه‌دور
/backup/test-smb        (POST)  تست اتصال SMB
/backup/test-ftp        (POST)  تست اتصال FTP
/backup/run-now         (POST)  اجرای فوری بکاپ و ارسال به مقصدهای فعال

بازیابی فقط برای همین سرور طراحی شده (نه Clone به سرور دیگر). چون بازیابی واقعی نیاز به متوقف‌کردن خودِ سرویس دارد (وگرنه
Connection Pool زنده‌ی سرویس روی همان جدول‌هایی که pg_restore می‌خواهد
بازسازی کند قفل می‌گیرد و pg_restore برای همیشه منتظر می‌ماند)، و چون این
درخواست HTTP از داخل همان سرویسی می‌آید که قرار است متوقف شود، خودِ کار
واقعی (توقف → pg_restore → migrate → روشن‌کردن دوباره) به یک اسکریپت
کاملاً مستقل واگذار می‌شود؛ این Endpoint فقط اعتبارسنجی می‌کند و آن
اسکریپت را راه می‌اندازد، بدون این‌که منتظر اتمامش بماند.
"""
import asyncio
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.backup_rules import has_backup_permission
from app.core.deps import get_current_user
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.core.security import decrypt_secret
from app.db.session import get_db
from app.schemas.backup import BackupSettingsIn, BackupSettingsOut, FtpTestConnectionIn, SmbTestConnectionIn
from app.services.backup_service import (
    RESTORE_CONFIRMATION_PHRASE,
    BackupError,
    get_restore_status,
)
from app.services.backup_settings_service import BackupSettingsService
from app.services.remote_backup_service import RemoteBackupError, test_ftp_connection, test_smb_connection

logger = logging.getLogger("faipco.backup")
router = APIRouter()


def require_backup(code: str):
    """
    مجوزهای تفکیک‌شده‌ی بکاپ (Migration 132). system.backup (منسوخ) تا یک نسخه معادل همه به‌جز backup.key_manage است؛
    ادمین کل همه را دارد.
    """

    async def checker(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> User:
        if current_user.is_superuser:
            return current_user
        codes = set(await UserRepository(db).get_all_permission_codes(current_user.id))
        if not has_backup_permission(codes, code):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="شما مجوز لازم را ندارید")
        return current_user

    return checker


@router.get("/export")
async def export_backup(
    current_user: User = Depends(require_backup("backup.download")),
):
    """
    یک ZIP بکاپ کامل (دیتابیس + فایل‌های آپلودی، با رمز فایل بکاپ اگر تعیین شده) می‌سازد و دانلود می‌شود؛ فایل موقت
    روی سرور بعد از تحویل پاک می‌شود. مجوز backup.download.
    """
    from fastapi.responses import FileResponse
    from starlette.background import BackgroundTask

    from app.core.scheduler import _BACKUP_LOCK_KEY, _advisory_unlock, _try_advisory_lock
    from app.db.session import AsyncSessionLocal
    from app.services.backup_archive import backup_dir
    from app.services.backup_settings_service import run_scheduled_backup

    async with AsyncSessionLocal() as db:
        if not await _try_advisory_lock(db, _BACKUP_LOCK_KEY):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="بکاپ دیگری در حال اجراست؛ کمی بعد دوباره امتحان کنید.")
        try:
            run = await run_scheduled_backup(
                db, trigger="download", user_id=current_user.id, send_to_destinations=False, keep_file=True
            )
        finally:
            await _advisory_unlock(db, _BACKUP_LOCK_KEY)
    if run.status == "failed" or not run.filename:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=run.message or "ساخت بکاپ ناموفق بود")
    path = backup_dir() / run.filename
    return FileResponse(
        path, filename=run.filename, media_type="application/zip",
        background=BackgroundTask(lambda: path.unlink(missing_ok=True)),
    )


@router.post("/restore", status_code=status.HTTP_202_ACCEPTED)
async def restore_backup(
    confirm: str = Form(..., description=f'برای تأیید باید دقیقاً "{RESTORE_CONFIRMATION_PHRASE}" ارسال شود'),
    password: str | None = Form(None, description="رمز فایل بکاپ (اگر فایل رمز دارد)"),
    file: UploadFile = File(..., description="فایل ZIP بکاپ که از همین صفحه دانلود شده"),
    _user=Depends(require_backup("backup.restore")),
):
    """
    داده و فایل‌های آپلودی فعلی را با محتوای فایل بکاپ جایگزین می‌کند (برگشت‌ناپذیر). فایل جریانی روی دیسک ذخیره و در
    پس‌زمینه باز و بررسی می‌شود (رمز، هش همه‌ی فایل‌ها)؛ فقط اگر سالم بود سرویس متوقف و جایگزینی انجام می‌شود و در شکست،
    داده و فایل‌های قبلی برمی‌گردند. وضعیت: GET /backup/restore-status. مجوز backup.restore.
    """
    from app.services.backup_jobs import read_stage_state, save_upload, start_restore_upload

    if confirm != RESTORE_CONFIRMATION_PHRASE:
        raise HTTPException(status_code=400, detail=f'برای تأیید، باید دقیقاً عبارت «{RESTORE_CONFIRMATION_PHRASE}» ارسال شود.')
    stage = read_stage_state() or {}
    if stage.get("phase") == "staging" or (await asyncio.to_thread(get_restore_status))["is_running"]:
        raise HTTPException(status_code=409, detail="یک بازیابی دیگر در حال اجراست.")
    try:
        path = await save_upload(file)
    except BackupError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    start_restore_upload(path, password or None)
    return {
        "success": True,
        "message": "فایل دریافت شد و در حال بررسی است؛ اگر سالم باشد بازیابی خودکار ادامه پیدا می‌کند و سرویس چند لحظه "
        "در دسترس نخواهد بود.",
    }


@router.get("/restore-status")
async def restore_status(
    _user=Depends(require_backup("backup.restore")),
):
    """
    وضعیت زنده آخرین Restore + مرحله‌ی آماده‌سازی (رمزگشایی/استخراج/بررسی هش) بازیابی از نسخه‌ی روی سرور. طبیعی است که
    همین Endpoint چند ثانیه (هنگام Stop/Start سرویس) در دسترس نباشد — فرانت‌اند با Retry مدیریت می‌کند.
    """
    from app.services.backup_jobs import read_stage_state

    result = await asyncio.to_thread(get_restore_status)
    result["stage"] = read_stage_state()
    return result


def _to_settings_out(settings) -> BackupSettingsOut:
    """ورودی: رکورد BackupSettings. خروجی: BackupSettingsOut بدون رمزها (فقط has_password)."""
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
        email_enabled=settings.email_enabled,
        email_recipients=settings.email_recipients,
        has_archive_password=bool(settings.archive_password_encrypted),
        last_run_at=settings.last_run_at,
        last_run_success=settings.last_run_success,
        last_run_message=settings.last_run_message,
    )


@router.get("/settings", response_model=BackupSettingsOut)
async def get_backup_settings(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_backup("backup.destinations")),
):
    """
    تنظیمات فعلی بکاپ را برمی‌گرداند. مجوز system.backup.
    رمزهای عبور هرگز در پاسخ برنمی‌گردند — فقط smb_has_password/ftp_has_password (بولی).
    """
    settings = await BackupSettingsService(db).get_settings()
    return _to_settings_out(settings)


@router.put("/settings", response_model=BackupSettingsOut)
async def update_backup_settings(
    payload: BackupSettingsIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_backup("backup.destinations")),
):
    """
    تنظیمات بکاپ را ذخیره و زمان‌بندی را به‌روز می‌کند. مجوز system.backup؛ 422 برای ورودی ناقص.
    برای رمزهای SMB/FTP: اگر خالی فرستاده شود، رمز ذخیره‌شده دست‌نخورده
    می‌ماند (نیازی به وارد‌کردن دوباره در هر ویرایش نیست).
    """
    try:
        settings = await BackupSettingsService(db).update_settings(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    return _to_settings_out(settings)


@router.post("/test-smb")
async def test_smb(
    payload: SmbTestConnectionIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_backup("backup.destinations")),
):
    """
    اتصال به SMB را با اطلاعات ارسالی تست می‌کند. مجوز system.backup.
    خطا: 400 اگر رمزی در دسترس نباشد یا اتصال ناموفق باشد.
    """
    # رمز خالی یعنی استفاده از رمز ذخیره‌شده
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
        # اتصال شبکه‌ای همگام (smbclient) در Thread جدا تا حلقه‌ی async معطل نشود
        await asyncio.to_thread(
            test_smb_connection,
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
    _user=Depends(require_backup("backup.destinations")),
):
    """
    اتصال به FTP/FTPS را با اطلاعات ارسالی تست می‌کند. مجوز system.backup.
    خطا: 400 اگر رمزی در دسترس نباشد یا اتصال ناموفق باشد.
    """
    # رمز خالی یعنی استفاده از رمز ذخیره‌شده
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
        # اتصال شبکه‌ای همگام (ftplib) در Thread جدا تا حلقه‌ی async معطل نشود
        await asyncio.to_thread(
            test_ftp_connection,
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


@router.post("/run-now", status_code=status.HTTP_202_ACCEPTED)
async def run_backup_now(
    send_to_destinations: bool = True,
    current_user: User = Depends(require_backup("backup.run_view")),
):
    """
    ساخت بکاپ همین الان در پس‌زمینه (و در صورت send_to_destinations ارسال به مقصدهای فعال). نتیجه در تاریخچه‌ی اجرا
    (GET /backup/overview). مجوز backup.run_view.
    """
    from app.services.backup_jobs import start_manual_backup

    start_manual_backup(current_user.id, send_to_destinations)
    return {"started": True, "message": "ساخت بکاپ در پس‌زمینه شروع شد؛ نتیجه در «تاریخچه‌ی بکاپ» نمایش داده می‌شود."}


# ---------- بکاپ v4: نمای کلی، نسخه‌های روی سرور، کلیدها، بازیابی از سرور ----------
