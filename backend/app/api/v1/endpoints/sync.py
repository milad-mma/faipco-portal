"""Endpoint های بخش «Sync Management» در پنل Admin."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.sync_log import SyncLog
from app.schemas.sync import SyncLogOut, TestConnectionResult
from app.sync_engine.sync_service import SyncError, SyncService

router = APIRouter()


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
