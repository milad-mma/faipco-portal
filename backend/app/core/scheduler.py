"""
اجرای خودکار و دوره‌ای Sync برای همه Site های فعال، با APScheduler.
فقط سایت‌هایی که هم خودشان فعال‌اند و هم SiteConnection.is_active روشن است
(یعنی Sync خودکار برایشان خاموش نشده) وارد این چرخه دوره‌ای می‌شوند. اجرای
دستی از پنل Admin مستقل از این پرچم است و همیشه کار می‌کند (به SyncService
مراجعه کنید).

⚠️ نکته حیاتی درباره فاصله زمانی: این Job با یک تیک **ثابت و مکرر** (هر ۱
دقیقه) اجرا می‌شود، نه مستقیم با همان فاصله‌ای که کاربر از پنل تنظیم
می‌کند — و هر بار خودش چک می‌کند «طبق آخرین Sync موفق و فاصله زمانی فعلی
(هر دو از دیتابیس، نه حافظه)، الان واقعاً وقتش شده یا نه». علتش یک باگ
واقعی بود: چون این سرویس با چند Worker جدا (uvicorn --workers 2) اجرا
می‌شود، هر Worker یک نسخه کاملاً مستقل از APScheduler دارد — وقتی کاربر
فاصله زمانی را از پنل تغییر می‌داد، فقط همان Worker ای که درخواست HTTP را
گرفته بود reschedule می‌شد؛ Worker دیگر همچنان با فاصله زمانی قدیمی (از
همان لحظه Startup) کار می‌کرد، و چون هرکدام مستقل تصمیم می‌گرفت «وقتشه»،
Sync می‌توانست خیلی زودتر از حد انتظار (یا اصلاً هیچ‌وقت با فاصله درست)
اجرا شود. با این طرح جدید، تصمیم «الان وقتشه یا نه» همیشه از یک منبع واحد
(دیتابیس) خوانده می‌شود — نتیجه‌اش برای هر Worker یکسان است، بدون نیاز به
Reschedule کردن هیچ Job ای.
اگر SYNC_ENABLED=false باشد، هیچ Job ای زمان‌بندی نمی‌شود.
"""
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.base import JobLookupError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.backup_schedule_logic import is_backup_due
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.server_stat import ServerStat
from app.models.site import Site, SiteConnection
from app.services.backup_settings_service import BackupSettingsService, run_scheduled_backup
from app.services.birthday_greetings_service import BirthdayGreetingsService
from app.services.server_stats_service import record_server_stats
from app.services.system_settings_service import SystemSettingsService
from app.sync_engine.sync_service import SyncService

logger = logging.getLogger("faipco.scheduler")
settings = get_settings()

JOB_ID = "auto_sync_all_sites"
BIRTHDAY_JOB_ID = "send_birthday_greetings"
SERVER_STATS_JOB_ID = "record_server_stats"
BACKUP_JOB_ID = "run_scheduled_backup"
# فاصله واقعی Sync دیگر مستقیم فاصله Job نیست (توضیح کامل بالا) — این فقط
# فاصله «چک کردن که آیا وقتشه» است؛ هرچه کوچک‌تر، دقت زمان‌بندی بهتر (کاربری
# که فاصله را روی ۵ دقیقه گذاشته، حداکثر ۱ دقیقه دیرتر اجرا می‌شود، نه بیشتر).
SYNC_CHECK_INTERVAL_MINUTES = 1
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
_SERVER_STATS_LOCK_KEY = 875312003
_BACKUP_LOCK_KEY = 875312004
# نمونه‌برداری واقعی مصرف سرور هر ۱۰ دقیقه یک‌بار — ولی مثل Sync، خودِ Job
# با تیک مکرر کوتاه‌تر (هر ۲ دقیقه) چک می‌کند «طبق آخرین نمونه ثبت‌شده در
# دیتابیس، وقتش رسیده یا نه» — همان دلیل بالا (هماهنگی بین چند Worker
# مستقل، بدون تکیه بر تایمر جداگانه هرکدام).
SERVER_STATS_CHECK_INTERVAL_MINUTES = 2
SERVER_STATS_SAMPLE_INTERVAL_MINUTES = 10
# مثل Sync/آمار سرور: یک تیک ثابت و کوتاه که هر بار از دیتابیس می‌پرسد
# «طبق زمان‌بندی فعلی بکاپ (روزانه/هفتگی/چندساعتی)، وقتش رسیده یا نه» -
# نگاه کنید به توضیح کامل در app/core/backup_schedule_logic.py
BACKUP_CHECK_INTERVAL_MINUTES = 5


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
            settings_service = SystemSettingsService(lock_db)
            interval_minutes = await settings_service.get_sync_interval_minutes()
            last_run = await settings_service.get_last_auto_sync_at()
            now = datetime.now(timezone.utc)

            if last_run is not None:
                elapsed_minutes = (now - last_run).total_seconds() / 60
                if elapsed_minutes < interval_minutes:
                    return  # هنوز وقتش نشده — طبق فاصله زمانی فعلی (تازه از دیتابیس خوانده‌شده)

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

            await settings_service.set_last_auto_sync_at(now)
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


async def _record_server_stats_job() -> None:
    async with AsyncSessionLocal() as db:
        acquired = await _try_advisory_lock(db, _SERVER_STATS_LOCK_KEY)
        if not acquired:
            return
        try:
            result = await db.execute(
                select(ServerStat.recorded_at).order_by(ServerStat.recorded_at.desc()).limit(1)
            )
            last_recorded = result.scalar_one_or_none()
            now = datetime.now(timezone.utc)
            if last_recorded is not None:
                elapsed_minutes = (now - last_recorded).total_seconds() / 60
                if elapsed_minutes < SERVER_STATS_SAMPLE_INTERVAL_MINUTES:
                    return  # هنوز وقتش نشده
            await record_server_stats(db)
        finally:
            await _advisory_unlock(db, _SERVER_STATS_LOCK_KEY)


async def _run_scheduled_backup_check() -> None:
    async with AsyncSessionLocal() as db:
        acquired = await _try_advisory_lock(db, _BACKUP_LOCK_KEY)
        if not acquired:
            return
        try:
            settings = await BackupSettingsService(db).get_settings()
            due = is_backup_due(
                schedule_enabled=settings.schedule_enabled,
                schedule_type=settings.schedule_type.value,
                schedule_hour=settings.schedule_hour,
                schedule_minute=settings.schedule_minute,
                schedule_weekday=settings.schedule_weekday,
                schedule_interval_hours=settings.schedule_interval_hours,
                last_run_at=settings.last_run_at,
            )
            if not due:
                return
            logger.info("زمان بکاپ خودکار طبق زمان‌بندی رسیده — شروع می‌شود")
            await run_scheduled_backup(db)
        except Exception:  # noqa: BLE001 - نباید کل Scheduler را متوقف کند
            logger.exception("خطا در بررسی/اجرای بکاپ زمان‌بندی‌شده")
        finally:
            await _advisory_unlock(db, _BACKUP_LOCK_KEY)


async def start_scheduler() -> None:
    if not settings.SYNC_ENABLED:
        logger.info("Sync خودکار غیرفعال است (SYNC_ENABLED=false)")
    else:
        scheduler.add_job(
            _run_sync_for_all_active_sites,
            trigger="interval",
            minutes=SYNC_CHECK_INTERVAL_MINUTES,
            id=JOB_ID,
            replace_existing=True,
        )
        logger.info(
            "Scheduler هر %s دقیقه چک می‌کند که آیا طبق فاصله زمانی تنظیم‌شده (که از دیتابیس خوانده "
            "می‌شود، نه حافظه) وقت Sync خودکار رسیده یا نه",
            SYNC_CHECK_INTERVAL_MINUTES,
        )

    async with AsyncSessionLocal() as db:
        birthday_hour, birthday_minute = await BirthdayGreetingsService(db).get_send_time()

    scheduler.add_job(
        _send_birthday_greetings,
        trigger="cron",
        hour=birthday_hour,
        minute=birthday_minute,
        id=BIRTHDAY_JOB_ID,
        replace_existing=True,
        # ⚠️ رفع یک باگ واقعی («بعضی روزها پیام تبریک تولد خودکار ارسال
        # نمی‌شود»): بدون misfire_grace_time، پیش‌فرض خودِ APScheduler
        # عملاً حدود ۱ ثانیه است — یعنی اگر Backend درست همان لحظه (مثلاً
        # هر بار که install.sh اجرا و سرویس Restart می‌شود) در حال
        # بالا‌آمدن باشد، حتی چند ثانیه تأخیر کافی بود که کل اجرای امروز
        # را کاملاً از دست بدهد، بدون هیچ تلاش دوباره تا فردا. حالا با
        # یک بازه اطمینان ۶ ساعته، اگر سرور دقیقاً سر ساعت ارسال Restart
        # شود، همین که دوباره بالا بیاید (تا ۶ ساعت بعد)، همان اجرای
        # امروز را انجام می‌دهد — نه اینکه کامل نادیده گرفته شود.
        misfire_grace_time=6 * 60 * 60,
    )
    logger.info("Scheduler پیام تبریک تولد هر روز ساعت %02d:%02d اجرا خواهد شد", birthday_hour, birthday_minute)

    scheduler.add_job(
        _record_server_stats_job,
        trigger="interval",
        minutes=SERVER_STATS_CHECK_INTERVAL_MINUTES,
        id=SERVER_STATS_JOB_ID,
        replace_existing=True,
    )
    logger.info(
        "Scheduler هر %s دقیقه یک‌بار مصرف CPU/RAM/دیسک سرور را نمونه‌برداری می‌کند",
        SERVER_STATS_SAMPLE_INTERVAL_MINUTES,
    )

    scheduler.add_job(
        _run_scheduled_backup_check,
        trigger="interval",
        minutes=BACKUP_CHECK_INTERVAL_MINUTES,
        id=BACKUP_JOB_ID,
        replace_existing=True,
    )
    logger.info(
        "Scheduler هر %s دقیقه چک می‌کند که آیا طبق زمان‌بندی بکاپ (که از دیتابیس خوانده می‌شود) وقتش رسیده یا نه",
        BACKUP_CHECK_INTERVAL_MINUTES,
    )

    scheduler.start()


def reschedule_sync_interval(minutes: int) -> None:
    """
    ⚠️ دیگر عملاً کاری لازم نیست انجام دهد — این تابع فقط برای سازگاری با
    Endpoint موجود (که هنوز صدایش می‌زند) نگه داشته شده و بلافاصله بی‌اثر
    برمی‌گردد. با طرح جدید (بالا)، تغییر فاصله زمانی همین که در دیتابیس
    ذخیره شود، همان لحظه برای همه Worker ها در چک بعدی (حداکثر
    SYNC_CHECK_INTERVAL_MINUTES دقیقه دیگر) اعمال می‌شود — نیازی به
    Reschedule کردن هیچ Job APScheduler ای نیست.
    """
    logger.info("فاصله زمانی Sync خودکار به %s دقیقه تغییر کرد (در چک بعدی همه Worker ها اعمال می‌شود)", minutes)


def reschedule_birthday_send_time(hour: int, minute: int) -> None:
    """ساعت ارسال روزانه پیام تبریک تولد را بدون Restart سرور تغییر می‌دهد."""
    try:
        # ⚠️ reschedule_job فقط Trigger را عوض می‌کند؛ برای اطمینان کامل
        # (مستقل از این‌که خودِ APScheduler سایر تنظیمات Job مثل
        # misfire_grace_time را حین Reschedule دست‌نخورده نگه می‌دارد یا
        # نه)، آن را هم صریحاً دوباره تنظیم می‌کنیم — همان بازه اطمینان
        # ۶ ساعته‌ای که هنگام تعریف اولیه Job در start_scheduler ست شده.
        scheduler.reschedule_job(BIRTHDAY_JOB_ID, trigger="cron", hour=hour, minute=minute)
        scheduler.modify_job(BIRTHDAY_JOB_ID, misfire_grace_time=6 * 60 * 60)
        logger.info("ساعت ارسال پیام تبریک تولد به %02d:%02d تغییر کرد", hour, minute)
    except JobLookupError:
        logger.warning("Job پیام تبریک تولد پیدا نشد — این نباید اتفاق بیفتد چون همیشه زمان‌بندی می‌شود.")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
