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
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.base import JobLookupError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.site import Site, SiteConnection
from app.services.birthday_greetings_service import BirthdayGreetingsService
from app.services.system_settings_service import SystemSettingsService
from app.sync_engine.sync_service import SyncService

logger = logging.getLogger("faipco.scheduler")
settings = get_settings()

JOB_ID = "auto_sync_all_sites"
BIRTHDAY_JOB_ID = "send_birthday_greetings"
# نکته حیاتی: بدون این، APScheduler به‌طور پیش‌فرض از منطقه زمانی سیستم‌عامل
# سرور استفاده می‌کند — که روی اکثر VPS های تازه‌نصب UTC است، نه ایران. یعنی
# «ساعت ۱۲» که مدیر منابع انسانی از پنل تنظیم می‌کند، بدون این خط ممکن است
# در عمل ساعت ۱۵:۳۰ ایران اجرا شود (یا اصلاً هنوز به آن زمان نرسیده باشد).
scheduler = AsyncIOScheduler(timezone=ZoneInfo("Asia/Tehran"))

# نکته حیاتی دیگر: این سرویس با چند Worker جدا (uvicorn --workers 2) اجرا
# می‌شود — هر Worker یک نسخه کاملاً مستقل از این Scheduler را استارت می‌کند
# (چون start_scheduler() در main.py، در startup هر Worker جدا صدا زده
# می‌شود). یعنی بدون قفل، هر Job زمان‌بندی‌شده (مثل ارسال پیام تبریک تولد)
# هم‌زمان توسط هر دو Worker اجرا می‌شود — دقیقاً همان چیزی که باعث شد یک نفر
# دو پیام (با متن‌های متفاوت، چون هرکدام تصادفی جدا انتخاب می‌کند) دریافت کند.
# راه‌حل: یک Advisory Lock سطح PostgreSQL — فقط Worker ای که قفل را می‌گیرد
# واقعاً Job را اجرا می‌کند؛ Worker دیگر می‌بیند قفل گرفته شده و بی‌صدا رد می‌شود.
_SYNC_LOCK_KEY = 875312001
_BIRTHDAY_LOCK_KEY = 875312002


async def _try_advisory_lock(db: AsyncSession, lock_key: int) -> bool:
    result = await db.execute(select(func.pg_try_advisory_lock(lock_key)))
    return bool(result.scalar_one())


async def _advisory_unlock(db: AsyncSession, lock_key: int) -> None:
    await db.execute(select(func.pg_advisory_unlock(lock_key)))


async def _run_sync_for_all_active_sites() -> None:
    async with AsyncSessionLocal() as lock_db:
        acquired = await _try_advisory_lock(lock_db, _SYNC_LOCK_KEY)
        if not acquired:
            logger.info("Job سینک خودکار همزمان توسط Worker دیگری در حال اجراست — این نمونه رد می‌شود.")
            return
        try:
            # فقط سایت‌هایی که هم خودشان فعال‌اند و هم Sync خودکارشان روشن است
            # (SiteConnection.is_active) وارد چرخه خودکار می‌شوند — اجرای دستی از
            # پنل Admin از این محدودیت مستقل است و همیشه در دسترس می‌ماند.
            result = await lock_db.execute(
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
        finally:
            await _advisory_unlock(lock_db, _SYNC_LOCK_KEY)


async def _send_birthday_greetings() -> None:
    async with AsyncSessionLocal() as db:
        acquired = await _try_advisory_lock(db, _BIRTHDAY_LOCK_KEY)
        if not acquired:
            logger.info("Job پیام تبریک تولد همزمان توسط Worker دیگری در حال اجراست — این نمونه رد می‌شود.")
            return
        try:
            await BirthdayGreetingsService(db).send_todays_birthday_greetings()
        except Exception:  # noqa: BLE001 - نباید کل Scheduler را متوقف کند
            logger.exception("خطا در ارسال خودکار پیام تبریک تولد")
        finally:
            await _advisory_unlock(db, _BIRTHDAY_LOCK_KEY)


async def start_scheduler() -> None:
    if not settings.SYNC_ENABLED:
        logger.info("Sync خودکار غیرفعال است (SYNC_ENABLED=false)")
    else:
        async with AsyncSessionLocal() as db:
            interval_minutes = await SystemSettingsService(db).get_sync_interval_minutes()

        scheduler.add_job(
            _run_sync_for_all_active_sites,
            trigger="interval",
            minutes=interval_minutes,
            id=JOB_ID,
            replace_existing=True,
        )
        logger.info("Scheduler سینک خودکار هر %s دقیقه اجرا خواهد شد", interval_minutes)

    async with AsyncSessionLocal() as db:
        birthday_hour, birthday_minute = await BirthdayGreetingsService(db).get_send_time()

    scheduler.add_job(
        _send_birthday_greetings,
        trigger="cron",
        hour=birthday_hour,
        minute=birthday_minute,
        id=BIRTHDAY_JOB_ID,
        replace_existing=True,
    )
    logger.info("Scheduler پیام تبریک تولد هر روز ساعت %02d:%02d اجرا خواهد شد", birthday_hour, birthday_minute)

    scheduler.start()


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


def reschedule_birthday_send_time(hour: int, minute: int) -> None:
    """ساعت ارسال روزانه پیام تبریک تولد را بدون Restart سرور تغییر می‌دهد."""
    try:
        scheduler.reschedule_job(BIRTHDAY_JOB_ID, trigger="cron", hour=hour, minute=minute)
        logger.info("ساعت ارسال پیام تبریک تولد به %02d:%02d تغییر کرد", hour, minute)
    except JobLookupError:
        logger.warning("Job پیام تبریک تولد پیدا نشد — این نباید اتفاق بیفتد چون همیشه زمان‌بندی می‌شود.")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
