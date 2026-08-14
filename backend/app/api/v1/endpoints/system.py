"""
/system/cache-bust   (POST)   نصب اجباری Service Worker جدید برای همه کاربران
                                (پاک‌کردن کامل کش اپلیکیشن — انگار همه دارند
                                اولین‌بار اپ را باز می‌کنند) — فقط Admin کامل.
/system/ip-allowlist (GET/POST/DELETE) مدیریت رنج‌های IP مجاز برای ورود
                                (مثلاً فقط شبکه دفتر) — فقط Admin کامل.
/system/ip-allowlist/bulk-import (POST) استخراج IP/CIDR از یک متن خام
                                (مثلاً کپی از فایل txt یا لاگ) و ثبت دسته‌ای.
/system/ip-blocked-message (GET/PUT) پیامی که به کاربر مسدودشده نمایش داده می‌شود.
"""
import ipaddress
import logging
import re

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.ip_allowlist_entry import IpAllowlistEntry
from app.schemas.system import (
    IpAllowlistBulkAddIn,
    IpAllowlistBulkAddResult,
    IpAllowlistBulkImportIn,
    IpAllowlistCandidate,
    IpAllowlistEntryIn,
    IpAllowlistEntryOut,
    IpAllowlistExtractResult,
    IpBlockedMessageIn,
    IpBlockedMessageOut,
)
from app.services.cache_service import CacheBustError, bump_app_cache_version
from app.services.system_settings_service import SystemSettingsService

logger = logging.getLogger("faipco.system")
router = APIRouter()

# فقط IPv4 (با یا بدون /CIDR) — کافی برای Use Case واقعی (کپی از لاگ Nginx یا
# فهرست دستی IP دفتر)؛ هر چیز دیگری در متن پیست‌شده (تاریخ، دستور، User-Agent) نادیده گرفته می‌شود
_IPV4_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?\b")


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


@router.post("/ip-allowlist/extract", response_model=IpAllowlistExtractResult)
async def extract_ip_allowlist_candidates(
    payload: IpAllowlistBulkImportIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.ip_allowlist")),
):
    """
    متن خام را می‌گیرد (مثلاً محتوای یک فایل txt یا حتی یک لاگ کامل Nginx که
    کاربر مستقیم Copy-Paste کرده)، هر چیزی که واقعاً IPv4 یا CIDR معتبر باشد
    را با Regex پیدا می‌کند و برمی‌گرداند — چیزی ذخیره نمی‌شود. چون این روش
    گاهی چیزهای شبیه‌IP ولی نامرتبط (مثلاً عدد نسخه یک مرورگر در User-Agent)
    را هم پیدا می‌کند، فرانت‌اند این فهرست را برای تأیید/ویرایش دستی به کاربر
    نشان می‌دهد، نه این‌که مستقیم ذخیره کند.
    """
    candidates_raw = _IPV4_PATTERN.findall(payload.text)

    valid_cidrs: set[str] = set()
    for raw in candidates_raw:
        try:
            network = ipaddress.ip_network(raw, strict=False)
        except ValueError:
            continue
        valid_cidrs.add(str(network) if "/" in raw else f"{network.network_address}/32")

    result = await db.execute(select(IpAllowlistEntry.cidr))
    existing_cidrs = {row[0] for row in result.all()}

    candidates = [
        IpAllowlistCandidate(cidr=cidr, already_exists=cidr in existing_cidrs)
        for cidr in sorted(valid_cidrs)
    ]
    return IpAllowlistExtractResult(candidates=candidates)


@router.post("/ip-allowlist/bulk-add", response_model=IpAllowlistBulkAddResult)
async def bulk_add_ip_allowlist(
    payload: IpAllowlistBulkAddIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.ip_allowlist")),
):
    """فهرست نهایی که کاربر بعد از دیدن پیش‌نمایش تأیید کرده را یک‌جا ثبت می‌کند."""
    valid_cidrs: set[str] = set()
    for raw in payload.cidrs:
        try:
            ipaddress.ip_network(raw, strict=False)
        except ValueError:
            continue
        valid_cidrs.add(raw.strip())

    result = await db.execute(select(IpAllowlistEntry.cidr))
    existing_cidrs = {row[0] for row in result.all()}

    new_cidrs = valid_cidrs - existing_cidrs
    duplicate_count = len(valid_cidrs) - len(new_cidrs)

    now = datetime.now(timezone.utc)
    added_entries = []
    for cidr in sorted(new_cidrs):
        entry = IpAllowlistEntry(cidr=cidr, label=payload.label, created_at=now)
        db.add(entry)
        added_entries.append(entry)

    await db.commit()
    # نکته مهم برای عملکرد: عمداً db.refresh() برای هرکدام صدا زده نمی‌شود —
    # برای فهرست‌های بزرگ (مثلاً هزاران CIDR از یک فایرول کشوری)، این یعنی
    # هزاران Round-trip جداگانه به دیتابیس فقط برای گرفتن id، درحالی‌که
    # PostgreSQL خودش موقع commit با RETURNING ضمنی، id هر رکورد را همان
    # لحظه Insert روی خودِ Object پر می‌کند — نیازی به واکشی دوباره نیست.
    return IpAllowlistBulkAddResult(
        added=added_entries,
        added_count=len(added_entries),
        duplicate_count=duplicate_count,
    )


@router.get("/ip-blocked-message", response_model=IpBlockedMessageOut)
async def get_ip_blocked_message(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.ip_allowlist")),
):
    message = await SystemSettingsService(db).get_ip_blocked_message()
    return IpBlockedMessageOut(message=message)


@router.put("/ip-blocked-message", response_model=IpBlockedMessageOut)
async def update_ip_blocked_message(
    payload: IpBlockedMessageIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("system.ip_allowlist")),
):
    try:
        message = await SystemSettingsService(db).set_ip_blocked_message(payload.message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return IpBlockedMessageOut(message=message)
