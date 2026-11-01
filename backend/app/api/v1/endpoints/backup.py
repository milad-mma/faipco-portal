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
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
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
    schedule_restore,
    validate_and_stage_archive,
)
from app.services.backup_settings_service import BackupSettingsService, run_scheduled_backup
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
    (سازگاری با نسخه‌ی قبل) یک بکاپ v4 همین الان می‌سازد و فایلش را جریانی تحویل می‌دهد. برای بکاپ بزرگ از
    «ساخت بکاپ» + دانلود از فهرست نسخه‌های روی سرور استفاده کنید. مجوز backup.download.
    """
    from fastapi.responses import FileResponse

    from app.core.scheduler import _BACKUP_LOCK_KEY, _advisory_unlock, _try_advisory_lock
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as lock_db:
        if not await _try_advisory_lock(lock_db, _BACKUP_LOCK_KEY):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="بکاپ دیگری در حال اجراست؛ کمی بعد دوباره امتحان کنید.")
        try:
            run = await run_scheduled_backup(lock_db, trigger="download", user_id=current_user.id, send_to_destinations=False)
        finally:
            await _advisory_unlock(lock_db, _BACKUP_LOCK_KEY)
    if run.status == "failed" or not run.filename:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=run.message or "ساخت بکاپ ناموفق بود")
    from app.services.backup_archive import local_path

    path = local_path(run.filename)
    return FileResponse(path, filename=run.filename, media_type="application/octet-stream")


@router.post("/restore")
async def restore_backup(
    confirm: str = Form(..., description=f'برای تأیید باید دقیقاً "{RESTORE_CONFIRMATION_PHRASE}" ارسال شود'),
    file: UploadFile = File(..., description="فایلی که از همین صفحه «پشتیبان‌گیری» دانلود شده"),
    _user=Depends(require_backup("backup.restore")),
):
    """
    داده و ساختار فعلی دیتابیس همین سرور را کاملاً با محتوای فایل بکاپ
    جایگزین می‌کند — برگشت‌ناپذیر است.

    این Endpoint فقط اعتبارسنجی سریع انجام می‌دهد و برمی‌گردد — خودِ Restore
    واقعی (که سرویس را چند لحظه متوقف می‌کند) در پس‌زمینه ادامه پیدا می‌کند.
    یعنی این پاسخ به معنای «بازیابی موفق شد» نیست، فقط یعنی «شروع شد» —
    برای دیدن نتیجه واقعی، بعد از ۳۰-۶۰ ثانیه صفحه را Refresh کنید.
    مجوز system.backup. خطا: 400 برای عبارت تأیید/فایل نامعتبر، 500 برای خطای راه‌اندازی.
    """
    # مرحله ۱: اعتبارسنجی فایل و عبارت تأیید، و آماده‌سازی فایل dump روی دیسک
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

    # مرحله ۲: اجرای اسکریپت مستقل بازیابی بدون انتظار برای اتمام
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
    settings = await BackupSettingsService(db).update_settings(payload)
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


@router.get("/overview")
async def backup_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_backup("backup.run_view")),
):
    """تاریخچه‌ی اجرا، نسخه‌های روی سرور، کلید فعال، فضای دیسک، هشدارها و وضعیت آخرین اجرا."""
    import shutil

    from sqlalchemy import select

    from app.models.backup_v4 import BackupRun
    from app.services import backup_keys
    from app.services.backup_archive import backup_dir, list_local

    runs = (await db.execute(select(BackupRun).order_by(BackupRun.id.desc()).limit(30))).scalars().all()
    key = await backup_keys.active_key(db)
    settings = await BackupSettingsService(db).get_settings()
    try:
        disk = shutil.disk_usage(backup_dir())
        disk_info = {"free": disk.free, "total": disk.total}
    except OSError:
        disk_info = None
    ok_runs = [r for r in runs if r.status in ("success", "partial") and r.finished_at]
    last_ok = ok_runs[0].finished_at if ok_runs else None
    warnings = []
    if key is None:
        warnings.append("بکاپ‌ها رمزنگاری نمی‌شوند؛ یک کلید رمزنگاری بسازید.")
    if not (settings.smb_enabled or settings.ftp_enabled):
        warnings.append("هیچ مقصد مستقل خودکاری (SMB یا FTP) فعال نیست؛ دانلود دستی مقصد مستقل محسوب نمی‌شود.")
    recent = [r.status for r in runs[:3] if r.trigger != "download"]
    if len(recent) == 3 and all(st == "failed" for st in recent):
        warnings.append("سه بکاپ آخر ناموفق بوده‌اند.")
    if last_ok and (datetime.now(timezone.utc) - last_ok).days >= 2:
        warnings.append(f"آخرین بکاپ سالم {(datetime.now(timezone.utc) - last_ok).days} روز پیش ساخته شده است.")
    if disk_info and disk_info["free"] < 2 * 1024**3:
        warnings.append("فضای آزاد دیسک کمتر از ۲ گیگابایت است.")
    return {
        "runs": [
            {
                "id": r.id, "set_id": r.set_id, "trigger": r.trigger, "status": r.status, "filename": r.filename,
                "key_id": r.key_id, "size": r.size, "file_count": r.file_count, "files_bytes": r.files_bytes,
                "consistency_method": r.consistency_method, "destinations": r.destinations, "message": r.message,
                "started_at": r.started_at, "finished_at": r.finished_at,
            }
            for r in runs
        ],
        "local": list_local(),
        "active_key": backup_keys.key_out(key, key.id) if key else None,
        "age_available": backup_keys.age_available(),
        "disk": disk_info,
        "last_success_at": last_ok,
        "warnings": warnings,
    }


@router.get("/local/{filename}/download")
async def download_local(
    filename: str,
    _user=Depends(require_backup("backup.download")),
):
    """دانلود جریانی یک نسخه‌ی روی سرور. مجوز backup.download."""
    from fastapi.responses import FileResponse

    from app.services.backup_archive import ArchiveError, local_path

    try:
        path = local_path(filename)
    except ArchiveError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None
    return FileResponse(path, filename=filename, media_type="application/octet-stream")


class RestoreLocalIn(BaseModel):
    filename: str
    confirm: str
    private_key: str | None = None  # کلید خصوصی age برای بکاپ رمزنگاری‌شده با کلید بیرون از سرور


@router.post("/restore-local", status_code=status.HTTP_202_ACCEPTED)
async def restore_local(
    payload: RestoreLocalIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_backup("backup.restore")),
):
    """
    بازیابی هماهنگ (دیتابیس + فایل‌های اتوماسیون) از یک نسخه‌ی روی سرور: رمزگشایی، استخراج و تطبیق همه‌ی هش‌ها در پس‌زمینه؛
    فقط اگر سالم بود سرویس متوقف و جایگزینی انجام می‌شود (در شکست هر دو برمی‌گردند). وضعیت: GET /backup/restore-status.
    """
    from sqlalchemy import select

    from app.models.backup_v4 import BackupKey, BackupRun
    from app.services import backup_keys
    from app.services.backup_archive import ArchiveError, local_path
    from app.services.backup_jobs import read_stage_state, start_restore_local

    if payload.confirm != RESTORE_CONFIRMATION_PHRASE:
        raise HTTPException(status_code=400, detail=f'برای تأیید، باید دقیقاً عبارت «{RESTORE_CONFIRMATION_PHRASE}» ارسال شود.')
    try:
        local_path(payload.filename)
    except ArchiveError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    if payload.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="بکاپ قالب قدیمی (zip) را از بخش «بازیابی از فایل» بارگذاری کنید.")
    stage = read_stage_state() or {}
    if stage.get("phase") == "staging" or (await asyncio.to_thread(get_restore_status))["is_running"]:
        raise HTTPException(status_code=409, detail="یک بازیابی دیگر در حال اجراست.")
    from datetime import timedelta

    recent = datetime.now(timezone.utc) - timedelta(hours=6)  # ردیف running قدیمی‌تر = فرآیند قطع‌شده، مانع نیست
    running = (await db.execute(
        select(BackupRun.id).where(BackupRun.status == "running", BackupRun.started_at > recent).limit(1)
    )).first()
    if running:
        raise HTTPException(status_code=409, detail="یک بکاپ در حال ساخت است؛ بعد از پایان آن بازیابی کنید.")
    identities = []
    if payload.private_key:
        try:
            backup_keys.public_key_of(payload.private_key)
        except backup_keys.BackupKeyError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None
        identities.append(payload.private_key.strip())
    for row in (await db.execute(select(BackupKey).where(BackupKey.encrypted_private_key.isnot(None)))).scalars():
        ident = backup_keys.stored_identity(row)
        if ident:
            identities.append(ident)
    start_restore_local(payload.filename, identities)
    return {"started": True, "message": "بررسی فایل بکاپ شروع شد؛ اگر سالم باشد بازیابی خودکار ادامه پیدا می‌کند."}


@router.get("/keys")
async def list_backup_keys(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_backup("backup.run_view")),
):
    """کلیدهای رمزنگاری (فقط کلید عمومی و اثرانگشت؛ هرگز کلید خصوصی)."""
    from app.services import backup_keys

    active = await backup_keys.active_key(db)
    return {
        "keys": [backup_keys.key_out(k, active.id if active else None) for k in await backup_keys.list_keys(db)],
        "age_available": backup_keys.age_available(),
        "modes": backup_keys.MODES,
    }


class CreateKeyIn(BaseModel):
    mode: str
    private_key: str | None = None  # وارد کردن کلید خصوصی موجود (مثلاً روی سرور جایگزین)


@router.post("/keys")
async def create_backup_key(
    payload: CreateKeyIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_backup("backup.key_manage")),
):
    """
    ساخت کلید تازه (یا وارد کردن کلید موجود) و فعال کردن آن؛ کلید قبلی retired می‌ماند. در حالت external کلید خصوصی فقط
    همین یک بار در پاسخ برمی‌گردد و باید بیرون از سرور نگهداری شود. مجوز backup.key_manage.
    """
    from app.services import backup_keys

    try:
        row, identity = await backup_keys.create_key(db, payload.mode, current_user.id, payload.private_key)
    except backup_keys.BackupKeyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    await db.commit()
    await db.refresh(row)
    out = backup_keys.key_out(row, row.id)
    if row.mode == "external" and not payload.private_key:
        out["private_key_once"] = identity  # فقط همین پاسخ؛ ذخیره نمی‌شود
    return out


class KeyPackageIn(BaseModel):
    passphrase: str


@router.post("/keys/package")
async def export_key_package(
    payload: KeyPackageIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_backup("backup.key_manage")),
):
    """بسته‌ی امن کلید فعال (حالت server_protected) رمزنگاری‌شده با عبارت عبور — برای خرابی کامل سرور."""
    from app.services import backup_keys

    key = await backup_keys.active_key(db)
    if key is None or not key.encrypted_private_key:
        raise HTTPException(status_code=400, detail="کلید فعال روی سرور ذخیره نشده است (فقط حالت «کلید محافظت‌شده روی سرور»).")
    try:
        package = backup_keys.export_package(backup_keys.stored_identity(key), payload.passphrase)
    except backup_keys.BackupKeyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return Response(
        content=package, media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="faipco-backup-key-{key.key_id}.json"'},
    )


@router.post("/keys/import-package")
async def import_key_package(
    passphrase: str = Form(...),
    mode: str = Form("server_protected"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_backup("backup.key_manage")),
):
    """وارد کردن بسته‌ی امن کلید (مثلاً روی سرور جایگزین) و فعال کردن آن."""
    from app.services import backup_keys

    try:
        identity = backup_keys.import_package(await file.read(65536), passphrase)
        row, _ = await backup_keys.create_key(db, mode, current_user.id, identity)
    except backup_keys.BackupKeyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    await db.commit()
    await db.refresh(row)
    return backup_keys.key_out(row, row.id)
