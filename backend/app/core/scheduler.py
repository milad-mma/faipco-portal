"""
اجرای خودکار و دوره‌ای Sync برای همه Site های فعال، با APScheduler.
فاصله زمانی از SYNC_INTERVAL_MINUTES در تنظیمات خوانده می‌شود.
اگر SYNC_ENABLED=false باشد، هیچ Job ای زمان‌بندی نمی‌شود.
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.site import Site
from app.sync_engine.sync_service import SyncService

logger = logging.getLogger("faipco.scheduler")
settings = get_settings()

scheduler = AsyncIOScheduler()


async def _run_sync_for_all_active_sites() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Site).where(Site.is_active.is_(True)))
        sites = list(result.scalars().all())

    for site in sites:
        async with AsyncSessionLocal() as db:
            try:
                await SyncService(db).run_sync(site.id)
                logger.info("Sync خودکار موفق برای Site '%s'", site.code)
            except Exception:  # noqa: BLE001 - خطای هر Site نباید بقیه را متوقف کند
                logger.exception("خطا در Sync خودکار برای Site '%s'", site.code)


def start_scheduler() -> None:
    if not settings.SYNC_ENABLED:
        logger.info("Sync خودکار غیرفعال است (SYNC_ENABLED=false)")
        return

    scheduler.add_job(
        _run_sync_for_all_active_sites,
        trigger="interval",
        minutes=settings.SYNC_INTERVAL_MINUTES,
        id="auto_sync_all_sites",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler سینک خودکار هر %s دقیقه اجرا خواهد شد", settings.SYNC_INTERVAL_MINUTES)


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
