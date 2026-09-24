"""
سرویس «حضور مبتنی بر موقعیت مکانی» (GPS) و ثبت ورود/خروج با موبایل.

شامل بررسی محدوده‌ی جغرافیایی (geofence) سایت‌ها، ثبت ورود/خروج پرسنل با
جلوگیری از رکورد تکراری، افزودن/ویرایش/حذف دستی لاگ توسط Admin و
گزارش‌های صفحه‌بندی‌شده‌ی لاگ‌ها و نشست‌های حضور آنلاین.

ثبت ورود/خروج رسمی از طریق دستگاه‌های حضور و غیاب کارخانه انجام می‌شود؛
این لاگ یک منبع مکمل دیجیتال است، نه جایگزین سامانه‌ی رسمی.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.geo import haversine_distance_meters
from app.core.persian_date import jalali_month_range_utc
from app.models.employee import Employee
from app.models.gps_activity_log import GpsActivityLog, GpsLogType
from app.models.presence_session import PresenceSession
from app.models.site import Site

DUPLICATE_WINDOW_MINUTES = 2  # فاصله‌ی حداقلی بین دو ثبت هم‌نوع یک پرسنل


class GpsAttendanceError(Exception):
    """خطای منطقی ثبت GPS با پیام فارسی قابل‌نمایش به کاربر (خارج از محدوده، ثبت تکراری)."""
    pass


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

    async def _record(
        self,
        *,
        employee_id: int,
        log_type: GpsLogType,
        latitude: float,
        longitude: float,
        accuracy_meters: float | None,
        site_id: int | None,
    ) -> GpsActivityLog:
        """
        یک لاگ GPS با نتیجه‌ی بررسی محدوده ذخیره و commit می‌کند و رکورد تازه‌شده را برمی‌گرداند.
        محدوده فقط ثبت می‌شود و جلوی ذخیره را نمی‌گیرد.
        """
        geofence = await check_geofence(self.db, site_id, latitude, longitude)
        log = GpsActivityLog(
            employee_id=employee_id,
            log_type=log_type,
            latitude=latitude,
            longitude=longitude,
            accuracy_meters=accuracy_meters,
            matched_site_id=geofence.matched_site.id if geofence.matched_site else None,
            distance_meters=geofence.distance_meters,
            is_within_geofence=geofence.is_within,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def clock_in_out(
        self,
        *,
        employee_id: int,
        log_type: GpsLogType,
        latitude: float,
        longitude: float,
        accuracy_meters: float | None,
        site_id: int | None,
    ) -> GpsActivityLog:
        """
        ورود یا خروج یک پرسنل را با مختصات فعلی ثبت می‌کند و لاگ ذخیره‌شده را برمی‌گرداند.
        اگر خارج از محدوده‌ی مجاز سایت باشد یا همین پرسنل کمتر از DUPLICATE_WINDOW_MINUTES دقیقه پیش
        ثبتی از همین نوع (ورود با ورود، خروج با خروج) داشته باشد، GpsAttendanceError می‌دهد.
        """
        # جلوگیری از ثبت تکراری با کلیک‌های پیاپی: آخرین ثبت هم‌نوع در پنجره‌ی زمانی
        recent_duplicate_cutoff = datetime.now(timezone.utc) - timedelta(minutes=DUPLICATE_WINDOW_MINUTES)
        result = await self.db.execute(
            select(GpsActivityLog.id)
            .where(
                GpsActivityLog.employee_id == employee_id,
                GpsActivityLog.log_type == log_type,
                GpsActivityLog.created_at >= recent_duplicate_cutoff,
            )
            .limit(1)
        )
        if result.scalar_one_or_none() is not None:
            action_fa = "ورود" if log_type == GpsLogType.check_in else "خروج"
            raise GpsAttendanceError(
                f"شما همین چند لحظه پیش یک ثبت {action_fa} انجام داده‌اید — برای جلوگیری از ثبت "
                f"تکراری، هر {DUPLICATE_WINDOW_MINUTES} دقیقه فقط یک بار امکان ثبت {action_fa} وجود دارد."
            )

        # ورود/خروج باید از داخل محدوده‌ی سایت باشد
        geofence = await check_geofence(self.db, site_id, latitude, longitude)
        if not geofence.is_within and geofence.matched_site is not None:
            distance_text = f"{int(geofence.distance_meters)} متر" if geofence.distance_meters else "نامشخص"
            raise GpsAttendanceError(
                f"موقعیت فعلی شما خارج از محدوده مجاز «{geofence.matched_site.name}» است "
                f"(فاصله: {distance_text}، محدوده مجاز: {geofence.matched_site.gps_radius_meters} متر). "
                "این ثبت انجام نشد."
            )

        return await self._record(
            employee_id=employee_id,
            log_type=log_type,
            latitude=latitude,
            longitude=longitude,
            accuracy_meters=accuracy_meters,
            site_id=site_id,
        )

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
            created_at=created_at,
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
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
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def delete_log(self, log_id: int) -> bool:
        """یک لاگ را حذف می‌کند؛ True اگر وجود داشت و حذف شد."""
        log = await self.db.get(GpsActivityLog, log_id)
        if log is None:
            return False
        await self.db.delete(log)
        await self.db.commit()
        return True

    async def get_my_logs(
        self, employee_id: int, *, year: int, month: int, limit: int = 200
    ) -> list[GpsActivityLog]:
        """
        لاگ‌های ورود/خروج خودِ پرسنل در یک ماه شمسی را (جدیدترین اول، حداکثر limit) برمی‌گرداند.
        لاگ‌های «حضور دوره‌ای» (presence) شامل نمی‌شوند.
        """
        start, end = jalali_month_range_utc(year, month)  # بازه‌ی ماه شمسی به UTC
        result = await self.db.execute(
            select(GpsActivityLog)
            .where(
                GpsActivityLog.employee_id == employee_id,
                GpsActivityLog.log_type != GpsLogType.presence,
                GpsActivityLog.created_at >= start,
                GpsActivityLog.created_at < end,
            )
            .order_by(GpsActivityLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

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
        if only_online:
            filters.append(PresenceSession.disconnected_at.is_(None))  # نشست باز = بدون زمان قطع
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
