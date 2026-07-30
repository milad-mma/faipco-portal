"""Endpoint های مدیریت Site ها، اتصال دیتابیس هر Site و Mapping ستون‌های پرسنلی."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
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
    _user=Depends(require_permission("sites.view")),
):
    return await SiteService(db).list_sites()


@router.post("", response_model=SiteOut)
async def create_site(
    payload: SiteCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage")),
):
    return await SiteService(db).create_site(payload)


@router.put("/{site_id}/connection", response_model=SiteConnectionOut)
async def upsert_connection(
    site_id: int,
    payload: SiteConnectionIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage", site_scoped=True)),
):
    return await SiteService(db).upsert_connection(site_id, payload)


@router.put("/{site_id}/mapping", response_model=EmployeeMappingOut)
async def upsert_mapping(
    site_id: int,
    payload: EmployeeMappingIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage", site_scoped=True)),
):
    return await SiteService(db).upsert_mapping(site_id, payload)
