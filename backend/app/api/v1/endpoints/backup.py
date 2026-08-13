"""
/backup/export    (GET)   دانلود یک بکاپ کامل و قابل‌جابه‌جایی — فقط Admin کامل.
/backup/restore   (POST)  بازیابی یک بکاپ از همین پنل، روی همین سرور — فقط Admin کامل.

Restore داخل یک Transaction واحد اجرا می‌شود (اگر هر خطایی وسط پیش بیاید،
کل عملیات Rollback می‌شود و داده فعلی دست‌نخورده می‌ماند)، و بعد از موفقیت،
خودِ سرویس Backend را (از طریق sudo systemctl restart — که نصب‌کننده مجوزش
را از قبل به‌صورت محدود به همین یک دستور به کاربر www-data داده) در پس‌زمینه
Restart می‌کند تا کلیدهای رمزنگاری تازه از .env واقعاً بارگذاری شوند.
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
        # هر خطای پیش‌بینی‌نشده هم باید حتماً در لاگ سرور ثبت شود و یک پیام
        # قابل‌فهم (نه یک 500 خالی و بی‌جزئیات) به کاربر برگردد — تا هیچ‌وقت
        # مثل قبل، فقط یک پیام عمومی بی‌فایده («ساخت بکاپ ناموفق بود») باقی نماند.
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
    نه فرزند این Worker) زمان‌بندی می‌کند. اگر این کار به‌صورت یک Task
    Async با Sleep داخل همین فرآیند انجام می‌شد، درست همون لحظه‌ای که uvicorn
    Worker خودش در جریان Restart از بین می‌رفت (Race Condition واقعی)، آن
    Task هم قبل از رسیدن به دستور واقعی Restart کشته می‌شد — این خودش دقیقاً
    می‌توانست باعث شود Restore واقعاً کامل انجام شود ولی سرویس هرگز درست
    بالا نیاید. با setsid + start_new_session، این فرآیند کاملاً از Session
    والدش جدا می‌شود و مستقل از سرنوشت Worker فعلی، کارش را کامل انجام می‌دهد.
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
    داده فعلی همین سرور را کاملاً پاک و با محتوای فایل بکاپ جایگزین می‌کند —
    برگشت‌ناپذیر است. بعد از موفقیت، سرویس Backend خودکار Restart می‌شود
    (چند ثانیه طول می‌کشد) و همه Session های ورود باطل می‌شوند (چون
    SECRET_KEY هم از بکاپ جایگزین می‌شود) — باید دوباره وارد شوید.
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
            detail="بازیابی با خطای پیش‌بینی‌نشده مواجه شد — جزئیات کامل در لاگ سرور ثبت شد. "
            "چون قبل از هر تغییری در دیتابیس، .env با نسخه اصلی جایگزین می‌شود، سیستم به‌حالت "
            "قبل از شروع Restore برگردانده شده است.",
        )

    # Popen بدون بلاک‌شدن فوراً برمی‌گردد — نیازی به BackgroundTasks نیست؛
    # پاسخ HTTP زیر، مستقل از این فرآیند مجزا، به‌طور معمول برای کاربر ارسال می‌شود.
    _schedule_backend_restart()
    return {
        "success": True,
        "message": "بازیابی با موفقیت انجام شد. سرویس چند ثانیه دیگر Restart می‌شود؛ "
        "بعد از آن باید دوباره وارد شوید.",
    }
