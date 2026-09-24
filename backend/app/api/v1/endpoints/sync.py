"""
Endpoint های بخش «Sync Management» در پنل Admin.

شامل: خواندن/تغییر فاصله اجرای خودکار Sync، خلاصه وضعیت امروز،
تست اتصال به دیتابیس منبع یک سایت، اجرای دستی Sync و تاریخچه اجراها.
"""
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
    """
    فاصله زمانی فعلی اجرای خودکار Sync (بر حسب دقیقه) + زمان آخرین اجرای موفق آن را برمی‌گرداند.
    مجوز لازم: sync.manage.
    """
    service = SystemSettingsService(db)
    interval = await service.get_sync_interval_minutes()
    last_auto_sync_at = await service.get_last_auto_sync_at()
    return SyncSettingsOut(interval_minutes=interval, last_auto_sync_at=last_auto_sync_at)


@router.put("/settings", response_model=SyncSettingsOut)
async def update_sync_settings(
    payload: SyncSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sync.manage")),
):
    """
    فاصله زمانی اجرای خودکار Sync را بدون Restart سرور تغییر می‌دهد (مجوز: sync.manage، خطای 400 برای مقدار نامعتبر).
    مقدار در دیتابیس ذخیره می‌شود و همه Worker ها در چک بعدی‌شان (حداکثر
    SYNC_CHECK_INTERVAL_MINUTES دقیقه، پیش‌فرض ۱) آن را می‌بینند، چون تصمیم
    «الان وقت اجراست یا نه» هر بار مستقیم از دیتابیس خوانده می‌شود، نه از حافظه Worker.
    """
    try:
        interval = await SystemSettingsService(db).set_sync_interval_minutes(payload.interval_minutes)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    reschedule_sync_interval(interval)  # فقط تغییر را لاگ می‌کند؛ اعمال واقعی از طریق مقدار ذخیره‌شده در دیتابیس است
    return SyncSettingsOut(interval_minutes=interval)


@router.get("/status-summary", response_model=SyncStatusSummaryOut)
async def get_sync_status_summary(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sync.view")),
):
    """خلاصه وضعیت Sync امروز همه سایت‌ها را برای کارت آمار داشبورد Admin برمی‌گرداند. مجوز: sync.view."""
    summary = await SyncService(db).get_status_summary()
    return SyncStatusSummaryOut(**summary)


@router.post("/{site_id}/test-connection", response_model=TestConnectionResult)
async def test_connection(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sync.view", site_scoped=True)),
):
    """
    اتصال به دیتابیس منبع سایت را تست می‌کند و نتیجه (موفق/ناموفق + پیام) را برمی‌گرداند.
    مجوز: sync.view برای همان سایت. خطای Sync به‌جای HTTP error به‌صورت success=False برگردانده می‌شود.
    """
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
    """
    Sync سایت را همین حالا به‌صورت دستی اجرا می‌کند و رکورد SyncLog این اجرا را برمی‌گرداند.
    مجوز: sync.run برای همان سایت. خطا: 400 اگر Sync قابل اجرا نباشد (SyncError).
    """
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
    """۵۰ اجرای آخر Sync سایت را (جدیدترین اول) برمی‌گرداند. مجوز: sync.view برای همان سایت."""
    result = await db.execute(
        select(SyncLog).where(SyncLog.site_id == site_id).order_by(SyncLog.started_at.desc()).limit(50)
    )
    return result.scalars().all()
