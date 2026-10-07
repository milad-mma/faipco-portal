"""
زمان‌بندی کارهای پس‌زمینه با APScheduler (منطقه زمانی Asia/Tehran):
- Sync خودکار همه Siteهای فعال (فقط سایت‌های فعال با SiteConnection.is_active روشن؛
  اجرای دستی از پنل Admin مستقل از این پرچم است — به SyncService مراجعه کنید)
- ارسال روزانه پیام تبریک تولد و خلاصه واکنش‌های تبریک
- نمونه‌برداری آمار مصرف سرور، بکاپ زمان‌بندی‌شده، یادآوری ارزیابی عملکرد
  و پاک‌سازی مدارک موقت بیمه تکمیلی

Jobهای دوره‌ای (Sync، آمار سرور، بکاپ) با یک تیک ثابت و کوتاه اجرا می‌شوند و هر
بار از دیتابیس می‌خوانند که طبق تنظیمات فعلی وقت اجرا رسیده یا نه؛ چون سرویس با
چند Worker مستقل (uvicorn --workers) اجرا می‌شود، این تصمیم برای همه Workerها
یکسان است و تغییر تنظیمات از پنل بدون Reschedule اعمال می‌شود.
هر Job با یک PostgreSQL Advisory Lock محافظت می‌شود تا فقط یک Worker آن را اجرا کند.
اگر SYNC_ENABLED=false باشد، Job مربوط به Sync زمان‌بندی نمی‌شود.
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
from app.db.session import AsyncSessionLocal, engine
from app.models.server_stat import ServerStat
from app.models.site import Site, SiteConnection
from app.services.backup_settings_service import BackupSettingsService, run_scheduled_backup
from app.services.birthday_greetings_service import BirthdayGreetingsService
from app.services.server_stats_service import record_server_stats
from app.services.system_settings_service import SystemSettingsService
from app.sync_engine.sync_service import SyncService

logger = logging.getLogger("faipco.scheduler")
settings = get_settings()

# شناسه Jobها در APScheduler
JOB_ID = "auto_sync_all_sites"
BIRTHDAY_JOB_ID = "send_birthday_greetings"
SERVER_STATS_JOB_ID = "record_server_stats"
BACKUP_JOB_ID = "run_scheduled_backup"
EVALUATION_REMINDER_JOB_ID = "send_evaluation_reminders"
BIRTHDAY_REACTION_SUMMARY_JOB_ID = "send_birthday_reaction_summaries"
# فاصله «چک کردن که آیا وقت Sync رسیده» (نه فاصله خود Sync)؛ Sync حداکثر
# به همین اندازه دیرتر از زمان تنظیم‌شده اجرا می‌شود.
SYNC_CHECK_INTERVAL_MINUTES = 1
# Scheduler با منطقه زمانی ایران؛ ساعت‌های cron (مثل ساعت ارسال تبریک تولد) به وقت
# تهران تفسیر می‌شوند، نه منطقه زمانی سیستم‌عامل سرور (معمولاً UTC).
scheduler = AsyncIOScheduler(timezone=ZoneInfo("Asia/Tehran"))

# کلیدهای PostgreSQL Advisory Lock برای هر Job: هر Worker یک Scheduler مستقل دارد
# (start_scheduler در startup هر Worker صدا زده می‌شود)، پس فقط Worker ای که قفل را
# می‌گیرد Job را اجرا می‌کند و بقیه بی‌صدا رد می‌شوند تا اجرای تکراری رخ ندهد.
_SYNC_LOCK_KEY = 875312001
_BIRTHDAY_LOCK_KEY = 875312002
_SERVER_STATS_LOCK_KEY = 875312003
_BACKUP_LOCK_KEY = 875312004
_EVALUATION_REMINDER_LOCK_KEY = 875312005
_BIRTHDAY_REACTION_LOCK_KEY = 875312006
_PRESENCE_CLEANUP_LOCK_KEY = 875312007
PRESENCE_CLEANUP_JOB_ID = "close_stale_presence_sessions"
_LOGIN_SECURITY_CLEANUP_LOCK_KEY = 875312008
LOGIN_SECURITY_CLEANUP_JOB_ID = "login_security_cleanup"
# flush شمارنده‌ی در حافظه‌ی «میزان استفاده» هر Worker به دیتابیس؛ بدون Advisory Lock،
# چون هر Worker فقط شمارش خودش را می‌نویسد و UPSERT تجمعی است.
USAGE_FLUSH_JOB_ID = "flush_usage_stats"
USAGE_FLUSH_INTERVAL_SECONDS = 60
# آمار مصرف سرور هر ۱۰ دقیقه نمونه‌برداری می‌شود؛ Job هر ۲ دقیقه بر اساس آخرین
# نمونه ثبت‌شده در دیتابیس بررسی می‌کند که وقتش رسیده یا نه.
SERVER_STATS_CHECK_INTERVAL_MINUTES = 2  # فاصله تیک بررسی
SERVER_STATS_SAMPLE_INTERVAL_MINUTES = 10  # فاصله واقعی بین دو نمونه
# فاصله تیک بررسی موعد بکاپ؛ تصمیم «وقتش رسیده یا نه» با تنظیمات دیتابیس در
# app/core/backup_schedule_logic.py گرفته می‌شود.
BACKUP_CHECK_INTERVAL_MINUTES = 5


# اتصال اختصاصیِ هر قفل: Advisory Lock در PostgreSQL به «اتصال» تعلق دارد، ولی AsyncSession بعد از هر commit
# اتصالش را به Pool برمی‌گرداند و برای دستور بعدی ممکن است اتصال دیگری بگیرد. اگر قفل روی Session گرفته می‌شد،
# بدنه‌ی Job که commit می‌کند قفل را روی یک اتصال رهاشده در Pool جا می‌گذاشت و unlock روی اتصال دیگری بی‌اثر بود؛
# نتیجه: قفل تا پایان عمر آن اتصال باقی می‌ماند و تیک‌های بعدی (در هر دو Worker) رد می‌شدند.
# این‌جا قفل روی یک اتصال جدا از Engine گرفته و تا unlock همان اتصال نگه داشته می‌شود.
_lock_connections: dict[int, object] = {}


async def _try_advisory_lock(db: AsyncSession, lock_key: int) -> bool:
    """
    ورودی: session (برای سازگاری امضا؛ استفاده نمی‌شود) و کلید قفل. بدون انتظار تلاش می‌کند Advisory Lock را
    روی یک اتصال اختصاصی بگیرد؛ خروجی: True اگر گرفته شد. اتصال تا _advisory_unlock باز می‌ماند.
    """
    conn = await engine.connect()
    try:
        result = await conn.execute(select(func.pg_try_advisory_lock(lock_key)))
        acquired = bool(result.scalar_one())
    except Exception:
        await conn.close()
        raise
    if not acquired:
        await conn.close()
        return False
    _lock_connections[lock_key] = conn
    return True


async def _advisory_unlock(db: AsyncSession, lock_key: int) -> None:
    """ورودی: session (استفاده نمی‌شود) و کلید قفل. قفل را روی همان اتصالی که گرفته شده آزاد و اتصال را می‌بندد."""
    conn = _lock_connections.pop(lock_key, None)
    if conn is None:
        return
    try:
        await conn.execute(select(func.pg_advisory_unlock(lock_key)))
    except Exception:  # noqa: BLE001 - بستن اتصال خودش قفل Session-level را آزاد می‌کند
        logger.warning("آزاد کردن Advisory Lock %s با خطا مواجه شد؛ اتصال بسته می‌شود", lock_key)
    finally:
        await conn.close()


async def _run_sync_for_all_active_sites() -> None:
    """
    Job تیک Sync: اگر قفل گرفته شود و از آخرین Sync خودکار به اندازه فاصله تنظیم‌شده گذشته باشد،
    Sync را برای همه سایت‌های فعال اجرا و زمان آخرین اجرا را ثبت می‌کند.
    """
    async with AsyncSessionLocal() as lock_db:
        acquired = await _try_advisory_lock(lock_db, _SYNC_LOCK_KEY)
        if not acquired:
            logger.info("Job سینک خودکار همزمان توسط Worker دیگری در حال اجراست — این نمونه رد می‌شود.")
            return
        try:
            # فاصله Sync و زمان آخرین اجرا هر بار تازه از دیتابیس خوانده می‌شود
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

            # اجرای Sync هر سایت با session جداگانه
            for site in sites:
                async with AsyncSessionLocal() as db:
                    try:
                        await SyncService(db).run_sync(site.id)
                        logger.info("Sync خودکار موفق برای Site '%s'", site.code)
                    except Exception:  # noqa: BLE001 - خطای هر Site نباید بقیه را متوقف کند
                        logger.exception("خطا در Sync خودکار برای Site '%s'", site.code)

            await settings_service.set_last_auto_sync_at(now)  # ثبت زمان این دور برای محاسبه موعد بعدی
        finally:
            await _advisory_unlock(lock_db, _SYNC_LOCK_KEY)


async def _send_birthday_greetings() -> None:
    """Job روزانه (cron): با گرفتن قفل، پیام تبریک تولد متولدین امروز را ارسال می‌کند."""
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


async def _cleanup_insurance_pending_documents_job() -> None:
    """Job دوره‌ای: مدارک بیمه تکمیلی آپلودشده‌ای را که فرمشان ثبت نشده (قدیمی‌تر از ۲۴ ساعت) پاک می‌کند."""
    from app.services.insurance_service import InsuranceService

    async with AsyncSessionLocal() as db:
        try:
            removed = await InsuranceService(db).cleanup_pending_documents()
            if removed:
                logger.info("%s مدرک موقت بیمه تکمیلی پاک شد", removed)
        except Exception:  # noqa: BLE001
            logger.exception("پاک‌سازی مدارک موقت بیمه تکمیلی ناموفق بود")


async def _cleanup_family_unlinked_documents_job() -> None:
    """Job دوره‌ای: مدارک «مشخصات خانوادگی» که آپلود شده ولی در فرم ثبت نشده‌اند (قدیمی‌تر از ۷۲ ساعت) پاک می‌شوند."""
    from app.services.family_service import FamilyService

    async with AsyncSessionLocal() as db:
        try:
            removed = await FamilyService(db).cleanup_unlinked_documents()
            if removed:
                logger.info("%s مدرک ثبت‌نشده‌ی مشخصات خانوادگی پاک شد", removed)
        except Exception:  # noqa: BLE001
            logger.exception("پاک‌سازی مدارک ثبت‌نشده‌ی مشخصات خانوادگی ناموفق بود")


async def _close_stale_presence_sessions_job() -> None:
    """
    Job هر ۲ دقیقه: نشست‌های «آنلاین» که Heartbeat اخیر ندارند (مثلاً بعد از ری‌استارت سرویس) را با زمان
    آخرین Heartbeat می‌بندد تا برای همیشه «الان آنلاین» نمانند.
    """
    from app.services.gps_attendance_service import close_stale_presence_sessions

    async with AsyncSessionLocal() as db:
        acquired = await _try_advisory_lock(db, _PRESENCE_CLEANUP_LOCK_KEY)
        if not acquired:
            return
        try:
            closed = await close_stale_presence_sessions(db)
            if closed:
                logger.info("%s نشست حضور رهاشده بسته شد", closed)
        except Exception:  # noqa: BLE001
            logger.exception("بستن نشست‌های حضور رهاشده ناموفق بود")
        finally:
            await _advisory_unlock(db, _PRESENCE_CLEANUP_LOCK_KEY)


async def _login_security_cleanup_job() -> None:
    """حذف گزارش‌های امنیت ورود قدیمی‌تر از مدت نگهداری و چالش‌های منقضی کپچا (روزانه)."""
    from app.services.login_security_service import cleanup

    async with AsyncSessionLocal() as db:
        acquired = await _try_advisory_lock(db, _LOGIN_SECURITY_CLEANUP_LOCK_KEY)
        if not acquired:
            return
        try:
            events, captchas = await cleanup(db)
            if events or captchas:
                logger.info("پاک‌سازی امنیت ورود: %s رویداد قدیمی و %s کپچای منقضی حذف شد", events, captchas)
        except Exception:  # noqa: BLE001
            logger.exception("پاک‌سازی امنیت ورود ناموفق بود")
        finally:
            await _advisory_unlock(db, _LOGIN_SECURITY_CLEANUP_LOCK_KEY)


async def _error_logs_cleanup_job() -> None:
    """حذف گزارش خطاهای قدیمی‌تر از ۳۰ روز (روزانه)."""
    from app.services.error_log_service import purge_old

    async with AsyncSessionLocal() as db:
        try:
            removed = await purge_old(db)
            if removed:
                logger.info("پاک‌سازی گزارش خطاها: %s گروه قدیمی حذف شد", removed)
        except Exception:  # noqa: BLE001
            logger.exception("پاک‌سازی گزارش خطاها ناموفق بود")


async def _flush_usage_stats_job() -> None:
    """Job هر ۶۰ ثانیه: شمارنده‌های در حافظه‌ی استفاده از پرتال (این Worker) را به دیتابیس UPSERT می‌کند."""
    from app.services.usage_stats_service import flush_usage

    await flush_usage()  # خطاها داخل خودِ تابع لاگ می‌شوند و شمارش‌ها نگه داشته می‌شوند


async def _record_server_stats_job() -> None:
    """Job تیک آمار سرور: اگر از آخرین نمونه ثبت‌شده ۱۰ دقیقه گذشته باشد، مصرف CPU/RAM/دیسک را ثبت می‌کند."""
    async with AsyncSessionLocal() as db:
        acquired = await _try_advisory_lock(db, _SERVER_STATS_LOCK_KEY)
        if not acquired:
            return
        try:
            # زمان آخرین نمونه ثبت‌شده
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
    """Job تیک بکاپ: تنظیمات بکاپ را می‌خواند و اگر is_backup_due بگوید موعد است، بکاپ زمان‌بندی‌شده را اجرا می‌کند."""
    async with AsyncSessionLocal() as db:
        acquired = await _try_advisory_lock(db, _BACKUP_LOCK_KEY)
        if not acquired:
            return
        try:
            settings = await BackupSettingsService(db).get_settings()  # تنظیمات بکاپ از دیتابیس (متغیر محلی؛ settings سراسری ماژول را در این تابع می‌پوشاند)
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


async def _send_evaluation_reminders_job() -> None:
    """
    Job روزانه (cron): یادآوری به ارزیاب‌هایی که ارزیابی محول‌شده را انجام نداده‌اند و مهلت دوره نزدیک است.
    با Advisory Lock محافظت می‌شود تا یادآوری تکراری برای یک نفر ارسال نشود.
    """
    async with AsyncSessionLocal() as db:
        acquired = await _try_advisory_lock(db, _EVALUATION_REMINDER_LOCK_KEY)
        if not acquired:
            return
        try:
            from app.services.evaluation_process_service import EvaluationProcessService

            result = await EvaluationProcessService(db).send_pending_evaluation_reminders()
            if result["notified_evaluators"]:
                logger.info(
                    "یادآوری ارزیابی عملکرد برای %s ارزیاب ارسال شد (%s ارزیابی معوق)",
                    result["notified_evaluators"],
                    result["pending_total"],
                )
        except Exception:  # noqa: BLE001 - نباید کل Scheduler را متوقف کند
            logger.exception("خطا در ارسال یادآوری ارزیابی عملکرد")
        finally:
            await _advisory_unlock(db, _EVALUATION_REMINDER_LOCK_KEY)


async def _send_birthday_reaction_summaries_job() -> None:
    """
    Job روزانه (cron، ساعت ۲۰ به وقت تهران): به هر متولد امروز که تبریک گرفته، یک اعلان خلاصه واکنش‌ها می‌فرستد.
    """
    async with AsyncSessionLocal() as db:
        acquired = await _try_advisory_lock(db, _BIRTHDAY_REACTION_LOCK_KEY)
        if not acquired:
            return
        try:
            from app.services.birthday_reaction_service import BirthdayReactionService

            result = await BirthdayReactionService(db).send_end_of_day_summaries()
            if result["notified"]:
                logger.info("خلاصه تبریک تولد برای %s نفر ارسال شد", result["notified"])
        except Exception:  # noqa: BLE001 - نباید کل Scheduler را متوقف کند
            logger.exception("خطا در ارسال خلاصه تبریک تولد")
        finally:
            await _advisory_unlock(db, _BIRTHDAY_REACTION_LOCK_KEY)


async def start_scheduler() -> None:
    """همه Jobها را در Scheduler ثبت و آن را استارت می‌کند؛ در startup هر Worker از main.py صدا زده می‌شود."""
    # Job تیک Sync خودکار (فقط اگر SYNC_ENABLED روشن باشد)
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

    # Job تبریک تولد با ساعت ارسالی که از تنظیمات دیتابیس خوانده می‌شود
    async with AsyncSessionLocal() as db:
        birthday_hour, birthday_minute = await BirthdayGreetingsService(db).get_send_time()

    scheduler.add_job(
        _send_birthday_greetings,
        trigger="cron",
        hour=birthday_hour,
        minute=birthday_minute,
        id=BIRTHDAY_JOB_ID,
        replace_existing=True,
        # بازه اطمینان ۶ ساعته: اگر سرور سر ساعت ارسال در حال Restart باشد، اجرای همان روز
        # تا ۶ ساعت بعد از بالا آمدن انجام می‌شود (پیش‌فرض APScheduler حدود ۱ ثانیه است).
        misfire_grace_time=6 * 60 * 60,
    )
    logger.info("Scheduler پیام تبریک تولد هر روز ساعت %02d:%02d اجرا خواهد شد", birthday_hour, birthday_minute)

    # Job تیک نمونه‌برداری آمار سرور
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

    # Job بستن نشست‌های حضور رهاشده، هر ۲ دقیقه (اولین اجرا بلافاصله بعد از شروع سرویس)
    scheduler.add_job(
        _close_stale_presence_sessions_job,
        trigger="interval",
        minutes=2,
        id=PRESENCE_CLEANUP_JOB_ID,
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc),
    )

    # Job پاک‌سازی مدارک موقت بیمه، هر ۶ ساعت
    scheduler.add_job(
        _cleanup_insurance_pending_documents_job,
        trigger="interval",
        hours=6,
        id="insurance_pending_cleanup",
        replace_existing=True,
    )
    scheduler.add_job(
        _cleanup_family_unlinked_documents_job,
        trigger="interval",
        hours=6,
        id="family_unlinked_cleanup",
        replace_existing=True,
    )

    # Job تیک بررسی موعد بکاپ
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

    # Job یادآوری ارزیابی، هر روز ساعت ۹
    scheduler.add_job(
        _send_evaluation_reminders_job,
        trigger="cron",
        hour=9,
        minute=0,
        id=EVALUATION_REMINDER_JOB_ID,
        replace_existing=True,
        # بازه اطمینان ۶ ساعته برای اجرای جبرانی در صورت Restart سرور سر ساعت ۹
        misfire_grace_time=6 * 60 * 60,
    )
    logger.info("Scheduler یادآوری ارزیابی‌های انجام‌نشده هر روز ساعت ۰۹:۰۰ ارسال می‌شود")

    # Job خلاصه تبریک تولد، هر روز ساعت ۲۰
    scheduler.add_job(
        _send_birthday_reaction_summaries_job,
        trigger="cron",
        hour=20,
        minute=0,
        id=BIRTHDAY_REACTION_SUMMARY_JOB_ID,
        replace_existing=True,
        # بازه اطمینان ۳ ساعته تا اجرای جبرانی حتماً قبل از پایان همان روز تولد (نیمه‌شب) باشد
        misfire_grace_time=3 * 60 * 60,
    )
    logger.info("Scheduler خلاصه تبریک تولد هر روز ساعت ۲۰:۰۰ ارسال می‌شود")

    # Job flush شمارنده‌ی استفاده از پرتال، هر ۶۰ ثانیه (در هر Worker جداگانه)
    scheduler.add_job(
        _flush_usage_stats_job,
        trigger="interval",
        seconds=USAGE_FLUSH_INTERVAL_SECONDS,
        id=USAGE_FLUSH_JOB_ID,
        replace_existing=True,
    )

    # پاک‌سازی روزانه‌ی گزارش امنیت ورود و کپچاهای منقضی (ساعت ۳:۱۰ بامداد)
    scheduler.add_job(
        _login_security_cleanup_job,
        trigger="cron",
        hour=3,
        minute=10,
        id=LOGIN_SECURITY_CLEANUP_JOB_ID,
        replace_existing=True,
        misfire_grace_time=12 * 60 * 60,
    )

    # پاک‌سازی روزانه‌ی گزارش خطاها (۳۰ روز؛ ساعت ۳:۲۰ بامداد). DELETE تکراری در دو Worker بی‌ضرر است
    scheduler.add_job(
        _error_logs_cleanup_job,
        trigger="cron",
        hour=3,
        minute=20,
        id="error_logs_cleanup",
        replace_existing=True,
        misfire_grace_time=12 * 60 * 60,
    )

    scheduler.start()


def reschedule_sync_interval(minutes: int) -> None:
    """
    ورودی: فاصله جدید Sync به دقیقه. فقط تغییر را لاگ می‌کند و Jobی را Reschedule نمی‌کند؛
    فاصله جدید از دیتابیس در تیک بعدی (حداکثر SYNC_CHECK_INTERVAL_MINUTES دقیقه) برای همه Workerها اعمال می‌شود.
    این تابع برای endpoint تنظیمات Sync که آن را صدا می‌زند نگه داشته شده است.
    """
    logger.info("فاصله زمانی Sync خودکار به %s دقیقه تغییر کرد (در چک بعدی همه Worker ها اعمال می‌شود)", minutes)


def reschedule_birthday_send_time(hour: int, minute: int) -> None:
    """ورودی: ساعت و دقیقه جدید. ساعت ارسال روزانه پیام تبریک تولد را بدون Restart سرور تغییر می‌دهد."""
    try:
        # reschedule_job فقط Trigger را عوض می‌کند؛ misfire_grace_time (۶ ساعت، مثل start_scheduler)
        # صریحاً دوباره تنظیم می‌شود تا حتماً حفظ شود.
        scheduler.reschedule_job(BIRTHDAY_JOB_ID, trigger="cron", hour=hour, minute=minute)
        scheduler.modify_job(BIRTHDAY_JOB_ID, misfire_grace_time=6 * 60 * 60)
        logger.info("ساعت ارسال پیام تبریک تولد به %02d:%02d تغییر کرد", hour, minute)
    except JobLookupError:
        logger.warning("Job پیام تبریک تولد پیدا نشد — این نباید اتفاق بیفتد چون همیشه زمان‌بندی می‌شود.")


def stop_scheduler() -> None:
    """Scheduler را در صورت اجرا بودن، بدون انتظار برای Jobهای جاری متوقف می‌کند (هنگام shutdown)."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
