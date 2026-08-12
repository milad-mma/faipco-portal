"""
/backup/export   (GET)   دانلود یک بکاپ کامل و قابل‌جابه‌جایی — فقط Admin کامل.

این Endpoint فقط بکاپ را می‌سازد و برای دانلود برمی‌گرداند؛ خودِ Restore
عمداً از طریق پنل وب انجام نمی‌شود (چون بازنویسی کامل دیتابیسِ در حالِ سرویس‌دهی
از داخل خودِ همان برنامه، ریسک واقعی دارد). Restore باید روی یک نصب کاملاً
تازه، از طریق `install.sh --restore-backup` انجام شود — راهنمای دقیقش در
پاسخ همین Endpoint (و در صفحه «پشتیبان‌گیری» پنل Admin) نوشته شده.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from app.core.deps import require_permission
from app.services.backup_service import BackupError, create_backup_archive

router = APIRouter()


@router.get("/export")
async def export_backup(
    _user=Depends(require_permission("system.backup")),
):
    try:
        archive_bytes = await create_backup_archive()
    except BackupError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    filename = f"faipco-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.zip"
    return Response(
        content=archive_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
