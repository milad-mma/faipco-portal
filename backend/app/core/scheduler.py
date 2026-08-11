"""
اجرای خودکار و دوره‌ای Sync برای همه Site های فعال، با APScheduler.
فقط سایت‌هایی که هم خودشان فعال‌اند و هم SiteConnection.is_active روشن است
(یعنی Sync خودکار برایشان خاموش نشده) وارد این چرخه دوره‌ای می‌شوند. اجرای
دستی از پنل Admin مستقل از این پرچم است و همیشه کار می‌کند (به SyncService
مراجعه کنید). فاصله زمانی ابتدا از دیتابیس (system_settings) خوانده می‌شود —
اگر هنوز از پنل تغییر داده نشده باشد، از SYNC_INTERVAL_MINUTES در .env
استفاده می‌شود (سازگار با نصب‌های قبلی). با reschedule_sync_interval()
می‌توان فاصله زمانی Job در حال اجرا را بدون Restart سرور تغییر داد — از
Endpoint مدیریت Sync صدا زده می‌شود.
اگر SYNC_ENABLED=false باشد، هیچ Job ای زمان‌بندی نمی‌شود.
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.base import JobLookupError
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.site import Site, SiteConnection
from app.services.system_settings_service import SystemSettingsService
from app.sync_engine.sync_service import SyncService

logger = logging.getLogger("faipco.scheduler")
settings = get_settings()

JOB_ID = "auto_sync_all_sites"
scheduler = AsyncIOScheduler()


async def _run_sync_for_all_active_sites() -> None:
    async with AsyncSessionLocal() as db:
        # فقط سایت‌هایی که هم خودشان فعال‌اند و هم Sync خودکارشان روشن است
        # (SiteConnection.is_active) وارد چرخه خودکار می‌شوند — اجرای دستی از
        # پنل Admin از این محدودیت مستقل است و همیشه در دسترس می‌ماند.
        result = await db.execute(
            select(Site)
            .join(SiteConnection, SiteConnection.site_id == Site.id)
            .where(Site.is_active.is_(True), SiteConnection.is_active.is_(True))
        )
        sites = list(result.scalars().all())

    for site in sites:
        async with AsyncSessionLocal() as db:
            try:
                await SyncService(db).run_sync(site.id)
                logger.info("Sync خودکار موفق برای Site '%s'", site.code)
            except Exception:  # noqa: BLE001 - خطای هر Site نباید بقیه را متوقف کند
                logger.exception("خطا در Sync خودکار برای Site '%s'", site.code)


async def start_scheduler() -> None:
    if not settings.SYNC_ENABLED:
        logger.info("Sync خودکار غیرفعال است (SYNC_ENABLED=false)")
        return

    async with AsyncSessionLocal() as db:
        interval_minutes = await SystemSettingsService(db).get_sync_interval_minutes()

    scheduler.add_job(
        _run_sync_for_all_active_sites,
        trigger="interval",
        minutes=interval_minutes,
        id=JOB_ID,
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler سینک خودکار هر %s دقیقه اجرا خواهد شد", interval_minutes)


def reschedule_sync_interval(minutes: int) -> None:
    """
    فاصله زمانی Job سینک خودکار در حال اجرا را بدون Restart سرور تغییر می‌دهد.
    اگر SYNC_ENABLED=false بوده و اصلاً Job ای زمان‌بندی نشده، بی‌اثر است —
    مقدار جدید همچنان در دیتابیس ذخیره شده و در Restart بعدی (اگر Sync فعال شود) اعمال می‌شود.
    """
    try:
        scheduler.reschedule_job(JOB_ID, trigger="interval", minutes=minutes)
        logger.info("فاصله زمانی Sync خودکار به %s دقیقه تغییر کرد", minutes)
    except JobLookupError:
        logger.info(
            "Job سینک خودکار در حال حاضر زمان‌بندی نشده (SYNC_ENABLED=false) — "
            "مقدار جدید فقط در دیتابیس ذخیره شد و در اجرای بعدی اعمال می‌شود."
        )


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
