"""
/system/cache-bust   (POST)   نصب اجباری Service Worker جدید برای همه کاربران
                                (پاک‌کردن کامل کش اپلیکیشن — انگار همه دارند
                                اولین‌بار اپ را باز می‌کنند) — فقط Admin کامل.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import require_permission
from app.services.cache_service import CacheBustError, bump_app_cache_version

logger = logging.getLogger("faipco.system")
router = APIRouter()


@router.post("/cache-bust")
async def cache_bust(
    _user=Depends(require_permission("system.cache_bust")),
):
    try:
        new_version = bump_app_cache_version()
    except CacheBustError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception:
        logger.exception("پاک‌کردن کش با خطای پیش‌بینی‌نشده مواجه شد")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="پاک‌کردن کش با خطای پیش‌بینی‌نشده مواجه شد — جزئیات کامل در لاگ سرور ثبت شد.",
        )

    return {
        "success": True,
        "version": new_version,
        "message": "با موفقیت انجام شد. هر کاربر دفعه بعدی که سایت را باز کند (یا صفحه را Refresh کند)، "
        "نسخه کاملاً تازه دریافت می‌کند — انگار اولین‌بار است.",
    }
