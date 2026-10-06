"""
سرویس «حضور مبتنی بر موقعیت مکانی» (GPS).

شامل بررسی محدوده‌ی جغرافیایی (geofence) سایت‌ها، افزودن/ویرایش/حذف دستی لاگ توسط مدیر و
گزارش‌های صفحه‌بندی‌شده‌ی لاگ‌ها و نشست‌های «پرسنل آنلاین / آنلاین در محیط کار».
ثبت ورود/خروج خودکار با اپ اندروید است (mobile_app_service)؛ ثبت دستی توسط خود پرسنل در Migration 104 حذف شد.

ثبت ورود/خروج رسمی از طریق دستگاه‌های حضور و غیاب کارخانه انجام می‌شود؛
این لاگ یک منبع مکمل دیجیتال است، نه جایگزین سامانه‌ی رسمی.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Integer, and_, func, not_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.geo import haversine_distance_meters
from app.core.persian_date import jalali_month_range_utc
from app.models.employee import Employee
from app.models.gps_activity_log import GpsActivityLog, GpsLogType
from app.models.presence_session import PresenceSession
from app.models.site import Site


class GeofenceCheckResult:
    """نتیجه‌ی بررسی محدوده: سایت منطبق (یا None)، فاصله به متر و اینکه داخل شعاع مجاز است یا نه."""
    def __init__(self, matched_site: Site | None, distance_meters: float | None, is_within: bool):
        self.matched_site = matched_site
        self.distance_meters = distance_meters
        self.is_within = is_within


async def check_geofence(db: AsyncSession, site_id: int | None, latitude: float, longitude: float) -> GeofenceCheckResult:
    """
    مختصات داده‌شده را با محدوده‌ی GPS سایت‌ها مقایسه می‌کند.
    اگر site_id مشخص باشد فقط همان سایت، وگرنه نزدیک‌ترین سایتِ دارای موقعیت GPS بررسی می‌شود.
    اگر هیچ سایتی موقعیت تنظیم‌شده نداشته باشد، بدون محدودیت (is_within=True، بدون سایت منطبق) برمی‌گردد.
    """
    # انتخاب سایت‌های کاندید
    if site_id is not None:
        sites = [await db.get(Site, site_id)]
        sites = [s for s in sites if s is not None]
    else:
        result = await db.execute(
            select(Site).where(
                Site.gps_latitude.is_not(None), Site.gps_longitude.is_not(None), Site.gps_radius_meters.is_not(None)
            )
        )
        sites = list(result.scalars().all())

    configured_sites = [s for s in sites if s.gps_latitude is not None and s.gps_longitude is not None and s.gps_radius_meters]  # فقط سایت‌های با موقعیت و شعاع
    # بدون تنظیمات GPS، هیچ محدودیتی اعمال نمی‌شود
    if not configured_sites:
        return GeofenceCheckResult(matched_site=None, distance_meters=None, is_within=True)

    # نزدیک‌ترین سایت با فاصله‌ی کروی (haversine)
    best_site = None
    best_distance = None
    for site in configured_sites:
        distance = haversine_distance_meters(latitude, longitude, site.gps_latitude, site.gps_longitude)
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_site = site

    is_within = best_distance is not None and best_distance <= best_site.gps_radius_meters
    return GeofenceCheckResult(matched_site=best_site, distance_meters=best_distance, is_within=is_within)


class GpsAttendanceService:
    """عملیات ثبت و گزارش لاگ‌های GPS و نشست‌های حضور روی یک AsyncSession."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_manual_log(
        self,
        *,
        employee_id: int,
        log_type: GpsLogType,
        created_at: datetime,
        site_id: int | None,
    ) -> GpsActivityLog:
        """
        یک رکورد ورود/خروج را دستی (توسط Admin/hr-manager) با زمان اعلام‌شده ثبت می‌کند.
        بدون مختصات GPS و با is_manual=True ذخیره می‌شود تا در گزارش مشخص باشد.
        """
        log = GpsActivityLog(
            employee_id=employee_id,
            log_type=log_type,
            latitude=None,
            longitude=None,
            accuracy_meters=None,
            matched_site_id=site_id,
            distance_meters=None,
            is_within_geofence=True,
            is_manual=True,
            source="manual",
            created_at=created_at,
        )
        self.db.add(log)
        await self.db.commit()  # expire_on_commit=False؛ مقدار ستون‌ها بدون refresh در دسترس است
        return log

    async def update_log(
        self,
        log_id: int,
        *,
        log_type: GpsLogType | None = None,
        created_at: datetime | None = None,
        site_id: int | None = None,
    ) -> GpsActivityLog | None:
        """
        فیلدهای داده‌شده‌ی یک لاگ موجود را تغییر می‌دهد و رکورد را برمی‌گرداند (None اگر پیدا نشود).
        بعد از ویرایش همیشه is_manual=True می‌شود تا مشخص باشد رکورد عیناً ثبت خودِ پرسنل نیست.
        """
        log = await self.db.get(GpsActivityLog, log_id)
        if log is None:
            return None
        # فقط فیلدهایی که مقدار دارند تغییر می‌کنند
        if log_type is not None:
            log.log_type = log_type
        if created_at is not None:
            log.created_at = created_at
        if site_id is not None:
            log.matched_site_id = site_id
        log.is_manual = True
        await self.db.commit()  # expire_on_commit=False؛ ستون server-side تغییرپذیری وجود ندارد، refresh لازم نیست
        return log

    async def delete_log(self, log_id: int) -> bool:
        """یک لاگ را حذف می‌کند؛ True اگر وجود داشت و حذف شد."""
        log = await self.db.get(GpsActivityLog, log_id)
        if log is None:
            return False
        await self.db.delete(log)
        await self.db.commit()
        return True

    async def get_all_logs_page(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        employee_id: int | None = None,
        log_type: GpsLogType | None = None,
        year: int,
        month: int,
        site_ids: set[int] | None = None,
    ) -> tuple[list[GpsActivityLog], int]:
        """
        یک صفحه از همه‌ی لاگ‌ها (حضور دوره‌ای + ورود/خروج) برای گزارش Admin/hr-manager و تعداد کل را برمی‌گرداند.
        همیشه به یک ماه شمسی محدود و صفحه‌بندی‌شده است، چون حضور دوره‌ای جدول را سریع بزرگ می‌کند.
        site_ids: اگر داده شود فقط لاگ‌های پرسنل همین سایت‌ها (ایزوله‌سازی چندسایتی)؛ None یعنی بدون محدودیت.
        """
        start, end = jalali_month_range_utc(year, month)
        # فیلترهای اختیاری روی بازه‌ی ماه
        filters = [GpsActivityLog.created_at >= start, GpsActivityLog.created_at < end]
        if employee_id is not None:
            filters.append(GpsActivityLog.employee_id == employee_id)
        if log_type is not None:
            filters.append(GpsActivityLog.log_type == log_type)
        if site_ids is not None:  # محدود به پرسنل سایت‌های مجاز (زیرکوئری)
            filters.append(
                GpsActivityLog.employee_id.in_(select(Employee.id).where(Employee.site_id.in_(site_ids)))
            )

        # تعداد کل برای صفحه‌بندی
        count_stmt = select(func.count()).select_from(GpsActivityLog).where(*filters)
        total = (await self.db.execute(count_stmt)).scalar_one()

        # صفحه‌ی درخواستی، جدیدترین اول
        stmt = (
            select(GpsActivityLog)
            .where(*filters)
            .order_by(GpsActivityLog.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def get_presence_sessions_page(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        employee_id: int | None = None,
        only_online: bool = False,
        site_ids: set[int] | None = None,
        kind: str | None = None,
    ) -> tuple[list[PresenceSession], int]:
        """
        یک صفحه از نشست‌های حضور آنلاین (مبتنی بر WebSocket) و تعداد کل را برمی‌گرداند.
        هر ردیف یک نشست واقعی با زمان اتصال/قطع است؛ only_online فقط نشست‌های باز را می‌دهد.
        site_ids: مثل get_all_logs_page برای ایزوله‌سازی چندسایتی.
        """
        # فیلترهای اختیاری
        filters = []
        if employee_id is not None:
            filters.append(PresenceSession.employee_id == employee_id)
        if kind:
            filters.append(PresenceSession.kind == kind)
        if only_online:
            # نشست باز و زنده: بدون زمان قطع و با Heartbeat اخیر (نشست رهاشده‌ای که هنوز Job نبسته، آنلاین نیست)
            filters.append(PresenceSession.disconnected_at.is_(None))
            filters.append(_alive_condition())
        if site_ids is not None:
            filters.append(
                PresenceSession.employee_id.in_(select(Employee.id).where(Employee.site_id.in_(site_ids)))
            )

        # تعداد کل برای صفحه‌بندی
        count_stmt = select(func.count()).select_from(PresenceSession).where(*filters)
        total = (await self.db.execute(count_stmt)).scalar_one()

        # صفحه‌ی درخواستی، جدیدترین اتصال اول
        stmt = (
            select(PresenceSession)
            .where(*filters)
            .order_by(PresenceSession.connected_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total


# ---------- نشست‌های حضور رهاشده ----------

# نشستی که این مدت Heartbeat نگرفته، زنده نیست (Heartbeat هر ۴۵ ثانیه، Timeout سرور ۹۰ ثانیه)
PRESENCE_STALE_SECONDS = 180
# نشست پس‌زمینه‌ی اپ اندروید («آنلاین در محیط کار» با اپ بسته): اپ تا وقتی گوشی آنلاین و داخل محدوده است حدود هر
# ۱۵ دقیقه «هنوز آنلاین» می‌فرستد (WorkManager؛ کمترین فاصله‌ی مجاز اندروید). نرسیدن گزارش در این مدت = قطع شده
BACKGROUND_STALE_SECONDS = 25 * 60


def presence_alive_since(source: str = "portal") -> datetime:
    """مرز زمانی «زنده»: نشستی که آخرین Heartbeat آن قبل از این لحظه است، رهاشده حساب می‌شود."""
    seconds = BACKGROUND_STALE_SECONDS if source == "background" else PRESENCE_STALE_SECONDS
    return datetime.now(timezone.utc) - timedelta(seconds=seconds)


def _alive_condition():
    """شرط SQL «آخرین Heartbeat اخیر است» با مرز جدا برای نشست‌های پرتال و پس‌زمینه."""
    last_seen = func.coalesce(PresenceSession.last_seen_at, PresenceSession.connected_at)
    return or_(
        and_(PresenceSession.source == "background", last_seen >= presence_alive_since("background")),
        and_(PresenceSession.source != "background", last_seen >= presence_alive_since("portal")),
    )


def is_presence_alive(session: PresenceSession) -> bool:
    """آیا نشست همین الان آنلاین است (باز و با Heartbeat اخیر)."""
    if session.disconnected_at is not None:
        return False
    last = session.last_seen_at or session.connected_at
    return last is not None and last >= presence_alive_since(session.source or "portal")


async def close_stale_presence_sessions(db: AsyncSession) -> int:
    """
    نشست‌های بازی را که Heartbeat اخیر ندارند (ری‌استارت سرور، قطع ناگهانی Worker، گزارش‌های اپ قطع شده، ...)
    با زمان آخرین Heartbeat می‌بندد؛ مدت هم تا همان لحظه حساب می‌شود. خروجی: تعداد نشست‌های بسته‌شده.
    """
    last_seen = func.coalesce(PresenceSession.last_seen_at, PresenceSession.connected_at)
    result = await db.execute(
        update(PresenceSession)
        .where(PresenceSession.disconnected_at.is_(None), not_(_alive_condition()))
        .values(
            disconnected_at=last_seen,
            duration_seconds=func.cast(
                func.extract("epoch", last_seen - PresenceSession.connected_at), Integer
            ),
        )
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    return result.rowcount or 0
