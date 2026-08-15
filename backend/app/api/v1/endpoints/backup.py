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

from app.core.deps import require_permission
from app.services.backup_service import (
    RESTORE_CONFIRMATION_PHRASE,
    BackupError,
    create_backup_archive,
    schedule_restore,
    validate_and_stage_archive,
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
    except Exception:
        logger.exception("راه‌اندازی فرآیند بازیابی ناموفق بود")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="راه‌اندازی فرآیند بازیابی ناموفق بود — جزئیات کامل در لاگ سرور ثبت شد.",
        )

    return {
        "success": True,
        "message": "بازیابی شروع شد. سرویس چند لحظه (معمولاً کمتر از یک دقیقه) در دسترس نخواهد بود، "
        "سپس خودکار دوباره بالا می‌آید — نیازی به ورود دوباره نیست. لطفاً ۳۰ تا ۶۰ ثانیه صبر کنید و "
        "بعد صفحه را Refresh کنید تا نتیجه واقعی را ببینید.",
    }
