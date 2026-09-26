"""
Endpoint های «گزارش جذب و ترک کار» (پیشوند /reports/turnover).

- GET  ""                       گزارش کامل (مجوز reports.turnover، سایت‌محور)
- GET  "/export"                همان گزارش به‌صورت Excel
- GET  "/categories"            دسته‌ها و متن‌های علت ترک کار با تعداد (reports.turnover یا reports.turnover_categories)
- POST/PUT/DELETE "/categories" و PUT "/aliases/{id}"  ویرایش دسته‌بندی (reports.turnover_categories)

داده مستقیماً از دیتابیس منبع هر سایت خوانده می‌شود و فقط شمارش/درصد برمی‌گردد.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.core.site_access import get_sites_with_permission
from app.db.session import get_db
from app.models.termination_reason import REASON_GROUPS, TerminationReasonAlias, TerminationReasonCategory
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.turnover_report_service import TurnoverReportError, TurnoverReportService, build_xlsx

router = APIRouter()


class CategoryIn(BaseModel):
    """ورودی ساخت/ویرایش دسته‌ی علت ترک کار."""

    title: str = Field(min_length=1, max_length=120)
    group: str
    legal_basis: str | None = Field(default=None, max_length=255)
    sort_order: int = 0

    @field_validator("group")
    @classmethod
    def _valid_group(cls, value: str) -> str:
        if value not in REASON_GROUPS:
            raise ValueError("گروه نامعتبر است")
        return value


class AliasIn(BaseModel):
    """دسته‌ی یک متن علت (None = دسته‌بندی نشده)."""

    category_id: int | None = None


async def _report_sites(db: AsyncSession, user: User, site_id: int | None) -> tuple[list[dict], list[dict]]:
    """
    سایت‌های قابل گزارش کاربر (دارای مجوز reports.turnover و نگاشت کامل) و سایت‌های انتخاب‌شده را برمی‌گرداند.
    403 اگر مجوز برای هیچ سایتی نباشد؛ 404 اگر site_id خارج از دسترس باشد.
    """
    allowed = await get_sites_with_permission(db, user, "reports.turnover")
    if allowed is not None and not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="دسترسی لازم برای گزارش جذب و ترک کار را ندارید")
    sites = await TurnoverReportService(db).configured_sites(allowed)
    if site_id is not None:
        selected = [s for s in sites if s["id"] == site_id]
        if not selected:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="این سایت در دسترس نیست یا نگاشت گزارش ندارد")
    else:
        selected = sites
    return sites, selected


async def _build(db, user, site_id, from_month, to_month, department, gender, refresh) -> tuple[dict, list[dict]]:
    sites, selected = await _report_sites(db, user, site_id)
    if not selected:
        return {"sites": sites, "not_configured": True}, selected
    try:
        report = await TurnoverReportService(db).build(
            [s["id"] for s in selected],
            [s["start_month"] for s in selected],
            from_month,
            to_month,
            department,
            gender,
            refresh=refresh,
        )
    except TurnoverReportError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    report["sites"] = sites
    report["selected_site_ids"] = [s["id"] for s in selected]
    return report, selected


@router.get("")
async def get_turnover_report(
    site_id: int | None = None,
    from_month: str | None = None,
    to_month: str | None = None,
    department: str | None = None,
    gender: int | None = Query(default=None, ge=1, le=2),
    refresh: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """گزارش کامل؛ بدون site_id همه‌ی سایت‌های مجاز با هم. from/to به شکل 1403/06؛ refresh=true داده‌ی تازه از منبع."""
    report, _selected = await _build(db, current_user, site_id, from_month, to_month, department, gender, refresh)
    return report


@router.get("/export")
async def export_turnover_report(
    site_id: int | None = None,
    from_month: str | None = None,
    to_month: str | None = None,
    department: str | None = None,
    gender: int | None = Query(default=None, ge=1, le=2),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """خروجی Excel همان گزارش."""
    report, selected = await _build(db, current_user, site_id, from_month, to_month, department, gender, False)
    if report.get("not_configured"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="هیچ سایتی نگاشت گزارش جذب و ترک کار ندارد")
    title = "گزارش جذب و ترک کار — " + "، ".join(s["name"] for s in selected)
    content = await asyncio.to_thread(build_xlsx, report, title)  # ساخت Excel حلقه‌ی async را معطل نکند
    filename = f"turnover-{datetime.now().strftime('%Y%m%d-%H%M')}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/categories")
async def get_categories(
    refresh: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    دسته‌ها و متن‌های علت ترک کار. فهرست متن‌ها پویا است: فقط متن‌هایی که همین حالا در منبع روی پرسنل
    قطع‌همکاری‌شده ثبت‌اند (تعداد > ۰) برمی‌گردند؛ دسته‌ی متن‌های حذف‌شده در دیتابیس می‌ماند تا اگر دوباره
    استفاده شدند خودکار همان دسته را بگیرند. دارنده‌ی reports.turnover_categories (کل سیستم) متن‌های همه‌ی
    سایت‌ها را می‌بیند و بقیه فقط سایت‌های مجاز خودشان را. اگر خواندن منبع ناموفق باشد، همه‌ی متن‌های ذخیره‌شده
    بدون تعداد برمی‌گردند. refresh=true داده‌ی تازه از منبع می‌خواند (بدون Cache پنج‌دقیقه‌ای).
    """
    codes = await UserRepository(db).get_all_permission_codes(current_user.id)
    can_manage = current_user.is_superuser or "reports.turnover_categories" in codes
    if not (can_manage or "reports.turnover" in codes):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="دسترسی لازم را ندارید")
    service = TurnoverReportService(db)
    counts = None
    count_error = None
    allowed = None if can_manage else await get_sites_with_permission(db, current_user, "reports.turnover")
    if allowed is None or allowed:
        sites = await service.configured_sites(allowed)
        try:
            counts = await service.reason_counts([s["id"] for s in sites], refresh=refresh)
        except TurnoverReportError as e:
            count_error = str(e)
    aliases = await service.list_aliases(counts)
    if counts is not None:
        # فقط متن‌هایی که الان در منبع استفاده می‌شوند
        aliases = [a for a in aliases if a["count"]]
    elif not can_manage:
        aliases = []  # بدون تعداد معلوم نیست کدام متن مال سایت‌های این کاربر است
    return {
        "can_manage": can_manage,
        "categories": await service.list_categories(),
        "aliases": aliases,
        "count_error": count_error,
    }


@router.post("/categories", status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("reports.turnover_categories")),
):
    """ساخت دسته‌ی جدید."""
    cat = TerminationReasonCategory(**payload.model_dump())
    db.add(cat)
    await db.commit()
    return {"id": cat.id}


@router.put("/categories/{category_id}")
async def update_category(
    category_id: int,
    payload: CategoryIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("reports.turnover_categories")),
):
    """ویرایش عنوان، گروه، مبنای قانونی یا ترتیب یک دسته."""
    cat = await db.get(TerminationReasonCategory, category_id)
    if cat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="دسته یافت نشد")
    for key, value in payload.model_dump().items():
        setattr(cat, key, value)
    await db.commit()
    return {"id": cat.id}


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("reports.turnover_categories")),
):
    """حذف دسته؛ متن‌های وصل به آن «دسته‌بندی نشده» می‌شوند."""
    cat = await db.get(TerminationReasonCategory, category_id)
    if cat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="دسته یافت نشد")
    await db.execute(
        update(TerminationReasonAlias).where(TerminationReasonAlias.category_id == category_id).values(category_id=None)
    )
    await db.delete(cat)
    await db.commit()


@router.put("/aliases/{alias_id}")
async def update_alias(
    alias_id: int,
    payload: AliasIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("reports.turnover_categories")),
):
    """تعیین دسته‌ی یک متن علت ترک کار."""
    alias = await db.get(TerminationReasonAlias, alias_id)
    if alias is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="متن یافت نشد")
    if payload.category_id is not None:
        exists = await db.execute(select(TerminationReasonCategory.id).where(TerminationReasonCategory.id == payload.category_id))
        if exists.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="دسته نامعتبر است")
    alias.category_id = payload.category_id
    await db.commit()
    return {"id": alias.id, "category_id": alias.category_id}
