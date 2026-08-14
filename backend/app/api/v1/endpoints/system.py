"""
/system/cache-bust   (POST)   نصب اجباری Service Worker جدید برای همه کاربران
                                (پاک‌کردن کامل کش اپلیکیشن — انگار همه دارند
                                اولین‌بار اپ را باز می‌کنند) — فقط Admin کامل.
/system/ip-allowlist (GET/POST/DELETE) مدیریت رنج‌های IP مجاز برای ورود
                                (مثلاً فقط شبکه دفتر) — فقط Admin کامل.
"""
import logging

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.ip_allowlist_entry import IpAllowlistEntry
from app.schemas.system import IpAllowlistEntryIn, IpAllowlistEntryOut
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


@router.get("/ip-allowlist", response_model=list[IpAllowlistEntryOut])
async def list_ip_allowlist(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.ip_allowlist")),
):
    result = await db.execute(select(IpAllowlistEntry).order_by(IpAllowlistEntry.created_at.desc()))
    return result.scalars().all()


@router.post("/ip-allowlist", response_model=IpAllowlistEntryOut, status_code=status.HTTP_201_CREATED)
async def add_ip_allowlist_entry(
    payload: IpAllowlistEntryIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.ip_allowlist")),
):
    entry = IpAllowlistEntry(cidr=payload.cidr, label=payload.label, created_at=datetime.now(timezone.utc))
    db.add(entry)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="این رنج قبلاً ثبت شده است.")
    await db.refresh(entry)
    return entry


@router.delete("/ip-allowlist/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ip_allowlist_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.ip_allowlist")),
):
    entry = await db.get(IpAllowlistEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="رکورد یافت نشد")
    await db.delete(entry)
    await db.commit()
