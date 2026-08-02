"""Endpoint های مدیریت Site ها، اتصال دیتابیس هر Site و Mapping ستون‌های پرسنلی."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.site import (
    EmployeeMappingIn,
    EmployeeMappingOut,
    SiteConnectionIn,
    SiteConnectionOut,
    SiteCreate,
    SiteOut,
)
from app.services.site_service import SiteService

router = APIRouter()


@router.get("", response_model=list[SiteOut])
async def list_sites(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    # فهرست ساده سایت‌ها (نام/کد) اطلاعات حساسی نیست؛ هر کاربر لاگین‌شده برای
    # فرم ارسال اطلاعیه (نمایش نام سایت خودش) به آن نیاز دارد. اطلاعات حساس
    # (اتصال دیتابیس، پسورد) در Endpoint های جداگانه و همچنان محافظت‌شده هستند.
    return await SiteService(db).list_sites()


@router.post("", response_model=SiteOut)
async def create_site(
    payload: SiteCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage")),
):
    return await SiteService(db).create_site(payload)


# ---------- Site Connection ----------

@router.get("/{site_id}/connection", response_model=SiteConnectionOut | None)
async def get_connection(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage", site_scoped=True)),
):
    return await SiteService(db).get_connection(site_id)


@router.put("/{site_id}/connection", response_model=SiteConnectionOut)
async def upsert_connection(
    site_id: int,
    payload: SiteConnectionIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage", site_scoped=True)),
):
    try:
        return await SiteService(db).upsert_connection(site_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{site_id}/connection", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage", site_scoped=True)),
):
    await SiteService(db).delete_connection(site_id)


# ---------- Employee Mapping ----------

@router.get("/{site_id}/mapping", response_model=EmployeeMappingOut | None)
async def get_mapping(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage", site_scoped=True)),
):
    return await SiteService(db).get_mapping(site_id)


@router.put("/{site_id}/mapping", response_model=EmployeeMappingOut)
async def upsert_mapping(
    site_id: int,
    payload: EmployeeMappingIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage", site_scoped=True)),
):
    return await SiteService(db).upsert_mapping(site_id, payload)


@router.delete("/{site_id}/mapping", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mapping(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage", site_scoped=True)),
):
    await SiteService(db).delete_mapping(site_id)
