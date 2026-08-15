"""Endpoint های بخش «Sync Management» در پنل Admin."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.core.scheduler import reschedule_sync_interval
from app.db.session import get_db
from app.models.sync_log import SyncLog
from app.schemas.sync import SyncLogOut, SyncSettingsOut, SyncSettingsUpdate, SyncStatusSummaryOut, TestConnectionResult
from app.services.system_settings_service import SystemSettingsService
from app.sync_engine.sync_service import SyncError, SyncService

router = APIRouter()


@router.get("/settings", response_model=SyncSettingsOut)
async def get_sync_settings(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sync.manage")),
):
    """فاصله زمانی فعلی اجرای خودکار Sync (بر حسب دقیقه)."""
    interval = await SystemSettingsService(db).get_sync_interval_minutes()
    return SyncSettingsOut(interval_minutes=interval)


@router.put("/settings", response_model=SyncSettingsOut)
async def update_sync_settings(
    payload: SyncSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sync.manage")),
):
    """
    تغییر فاصله زمانی اجرای خودکار Sync — بدون نیاز به Restart سرور یا ویرایش
    دستی .env؛ هم در دیتابیس ذخیره می‌شود (برای ماندگاری بعد از Restart) و هم
    بلافاصله روی Job در حال اجرای APScheduler اعمال می‌شود.
    """
    try:
        interval = await SystemSettingsService(db).set_sync_interval_minutes(payload.interval_minutes)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    reschedule_sync_interval(interval)
    return SyncSettingsOut(interval_minutes=interval)


@router.get("/status-summary", response_model=SyncStatusSummaryOut)
async def get_sync_status_summary(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sync.view")),
):
    """خلاصه وضعیت Sync امروز همه سایت‌ها — برای کارت آمار داشبورد Admin."""
    summary = await SyncService(db).get_status_summary()
    return SyncStatusSummaryOut(**summary)


@router.post("/{site_id}/test-connection", response_model=TestConnectionResult)
async def test_connection(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sync.view", site_scoped=True)),
):
    service = SyncService(db)
    try:
        success, message = await service.test_connection(site_id)
    except SyncError as e:
        return TestConnectionResult(success=False, message=str(e))
    return TestConnectionResult(success=success, message=message)


@router.post("/{site_id}/run", response_model=SyncLogOut)
async def run_sync(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sync.run", site_scoped=True)),
):
    service = SyncService(db)
    try:
        log = await service.run_sync(site_id)
    except SyncError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return log


@router.get("/{site_id}/logs", response_model=list[SyncLogOut])
async def list_sync_logs(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sync.view", site_scoped=True)),
):
    result = await db.execute(
        select(SyncLog).where(SyncLog.site_id == site_id).order_by(SyncLog.started_at.desc()).limit(50)
    )
    return result.scalars().all()
