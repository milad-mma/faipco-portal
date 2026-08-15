"""
/backup/export    (GET)   دانلود یک بکاپ کامل (Schema + Data) — فقط Admin کامل.
/backup/restore   (POST)  بازیابی یک بکاپ از همین پنل، روی همین سرور — فقط Admin کامل.

⚠️ این قابلیت فقط برای بازیابی روی همین سرور طراحی شده (نه Clone به سرور
دیگر) — .env و کلیدهای رمزنگاری دست‌نخورده می‌مانند، پس Session های ورود
فعلی هم باطل نمی‌شوند.
"""
import logging
import subprocess
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response

from app.core.deps import require_permission
from app.services.backup_service import (
    RESTORE_CONFIRMATION_PHRASE,
    BackupError,
    create_backup_archive,
    restore_from_archive,
)

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


def _schedule_backend_restart() -> None:
    """
    Restart را با یک فرآیند کاملاً مستقل (نه یک Task داخل همین Event Loop و
    نه فرزند این Worker) زمان‌بندی می‌کند — تا اگر خودِ این Worker همون لحظه
    از بین برود، Restart همچنان کامل انجام شود.

    چرا هنوز بعد از Restore نیاز به Restart داریم، با این‌که دیگر .env/کلید
    رمزنگاری‌ای عوض نمی‌شود؟ چون pg_restore --clean همه جدول‌ها را Drop و
    از نو می‌سازد — Connection Pool موجود بک‌اند ممکن است به OID های قدیمی/
    Prepared Statement های قدیمی اشاره داشته باشد. یک Restart ساده، Pool را
    کاملاً تازه می‌کند و از خطاهای گذرا و عجیب در اولین درخواست‌های بعد از
    بازیابی جلوگیری می‌کند.
    """
    try:
        subprocess.Popen(
            ["setsid", "sh", "-c", "sleep 4 && sudo -n /usr/bin/systemctl restart faipco-backend"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        logger.exception(
            "زمان‌بندی Restart خودکار بعد از Restore ناموفق بود — لطفاً دستی روی سرور اجرا کنید: "
            "sudo systemctl restart faipco-backend"
        )


@router.post("/restore")
async def restore_backup(
    confirm: str = Form(..., description=f'برای تأیید باید دقیقاً "{RESTORE_CONFIRMATION_PHRASE}" ارسال شود'),
    file: UploadFile = File(..., description="فایلی که از همین صفحه «پشتیبان‌گیری» دانلود شده"),
    _user=Depends(require_permission("system.backup")),
):
    """
    داده و ساختار فعلی دیتابیس همین سرور را کاملاً با محتوای فایل بکاپ
    جایگزین می‌کند — برگشت‌ناپذیر است. چون فقط روی همین سرور بازیابی می‌شود،
    .env و کلیدهای رمزنگاری دست‌نخورده می‌مانند — Session های ورود فعلی
    باطل نمی‌شوند (فقط چند ثانیه بعد از Restart، اولین درخواست ممکن است کند
    یا با یک خطای موقت مواجه شود؛ رفرش کردن صفحه کافی است).
    """
    file_bytes = await file.read()
    try:
        await restore_from_archive(file_bytes, confirm_phrase=confirm)
    except BackupError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logger.exception("بازیابی بکاپ با خطای پیش‌بینی‌نشده مواجه شد")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="بازیابی با خطای پیش‌بینی‌نشده مواجه شد — جزئیات کامل در لاگ سرور ثبت شد.",
        )

    _schedule_backend_restart()
    return {
        "success": True,
        "message": "بازیابی با موفقیت انجام شد. سرویس چند ثانیه دیگر Restart می‌شود — "
        "نیازی به ورود دوباره نیست، فقط چند لحظه بعد صفحه را Refresh کنید.",
    }
