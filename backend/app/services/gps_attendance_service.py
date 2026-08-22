"""
سرویس «حضور مبتنی بر موقعیت مکانی» و «ثبت ورود/خروج آزمایشی».

⚠️ این قابلیت آزمایشی است. ثبت ورود/خروج رسمی باید از طریق دستگاه‌های
تعبیه‌شده در کارخانه انجام شود؛ این فقط یک لاگ مکمل دیجیتال است — نه
جایگزین سامانه حضور و غیاب رسمی.
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

DUPLICATE_WINDOW_MINUTES = 2


class GpsAttendanceError(Exception):
    pass


class GeofenceCheckResult:
    def __init__(self, matched_site: Site | None, distance_meters: float | None, is_within: bool):
        self.matched_site = matched_site
        self.distance_meters = distance_meters
        self.is_within = is_within


async def check_geofence(db: AsyncSession, site_id: int | None, latitude: float, longitude: float) -> GeofenceCheckResult:
    """
    اگر site_id مشخص شده باشد، فقط همان سایت چک می‌شود؛ وگرنه نزدیک‌ترین
    سایتی که موقعیت GPS برایش تنظیم شده، در نظر گرفته می‌شود. اگر هیچ سایتی
    اصلاً موقعیت GPS تنظیم‌شده نداشته باشد، هیچ محدودیتی اعمال نمی‌شود
    (is_within=True، بدون سایت مطابق) — تا این قابلیت هرگز به‌خاطر نبود
    تنظیمات، کسی را مسدود نکند.
    """
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

    configured_sites = [s for s in sites if s.gps_latitude is not None and s.gps_longitude is not None and s.gps_radius_meters]
    if not configured_sites:
        return GeofenceCheckResult(matched_site=None, distance_meters=None, is_within=True)

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

    async def log_presence(
        self, *, employee_id: int, latitude: float, longitude: float, accuracy_meters: float | None, site_id: int | None
    ) -> GpsActivityLog:
        """حضور دوره‌ای — همیشه لاگ می‌شود، چه داخل محدوده باشد چه نه (برای گزارش‌گیری بعدی مفید است)."""
        return await self._record(
            employee_id=employee_id,
            log_type=GpsLogType.presence,
            latitude=latitude,
            longitude=longitude,
            accuracy_meters=accuracy_meters,
            site_id=site_id,
        )

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
        برخلاف log_presence، اینجا اگر خارج از محدوده مجاز باشد، عملاً ثبت
        رد می‌شود (Exception) — چون ورود/خروج باید واقعاً از محل کارخانه باشد.

        همچنین اگر همین پرسنل کمتر از ۲ دقیقه پیش از همین نوع (فقط ورود با
        ورود، یا فقط خروج با خروج — نه ورود با خروج) ثبت کرده باشد، رد
        می‌شود — جلوگیری از رکورد تکراری با کلیک‌های پیاپی/تصادفی.
        """
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
        """Admin/hr-manager یک رکورد را دستی اضافه می‌کند — بدون مختصات GPS
        واقعی (چون خودِ پرسنل آنجا نبوده)، با is_manual=True تا در گزارش با
        یک ستاره مشخص شود."""
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
        """ویرایش دستی یک رکورد موجود (توسط خودِ پرسنل ثبت‌شده باشد یا از قبل
        دستی) — همیشه بعد از ویرایش is_manual=True می‌شود تا مشخص باشد این
        رکورد دیگر عیناً همان چیزی نیست که خودِ پرسنل فرستاده."""
        log = await self.db.get(GpsActivityLog, log_id)
        if log is None:
            return None
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
        log = await self.db.get(GpsActivityLog, log_id)
        if log is None:
            return False
        await self.db.delete(log)
        await self.db.commit()
        return True

    async def get_my_logs(
        self, employee_id: int, *, year: int, month: int, limit: int = 200
    ) -> list[GpsActivityLog]:
        start, end = jalali_month_range_utc(year, month)
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
        گزارش کامل Admin/hr-manager — همه لاگ‌ها (حضور دوره‌ای + ورود/خروج)
        برای همه پرسنل، همیشه محدود به یک ماه شمسی مشخص. چون «حضور دوره‌ای»
        هر ۱۰ دقیقه به‌ازای هر پرسنل آزمایش ثبت می‌شود، این جدول می‌تواند
        خیلی سریع بزرگ شود — همیشه هم به یک ماه محدود است هم Paginated.

        site_ids (اختیاری): اگر داده شود، فقط لاگ‌های پرسنل همین سایت‌ها —
        برای ایزوله‌سازی چندسایتی (مثلاً hr-manager سایت‌محور نباید گزارش
        حضور سایت دیگری را ببیند). None یعنی بدون محدودیت.
        """
        start, end = jalali_month_range_utc(year, month)
        filters = [GpsActivityLog.created_at >= start, GpsActivityLog.created_at < end]
        if employee_id is not None:
            filters.append(GpsActivityLog.employee_id == employee_id)
        if log_type is not None:
            filters.append(GpsActivityLog.log_type == log_type)
        if site_ids is not None:
            filters.append(
                GpsActivityLog.employee_id.in_(select(Employee.id).where(Employee.site_id.in_(site_ids)))
            )

        count_stmt = select(func.count()).select_from(GpsActivityLog).where(*filters)
        total = (await self.db.execute(count_stmt)).scalar_one()

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
        """گزارش «آنلاین/آفلاین» زنده مبتنی بر WebSocket — هر ردیف یک Session
        واقعی با شروع/پایان دقیق است، نه یک لاگ نقطه‌ای.

        site_ids: مثل get_all_logs_page — برای ایزوله‌سازی چندسایتی."""
        filters = []
        if employee_id is not None:
            filters.append(PresenceSession.employee_id == employee_id)
        if only_online:
            filters.append(PresenceSession.disconnected_at.is_(None))
        if site_ids is not None:
            filters.append(
                PresenceSession.employee_id.in_(select(Employee.id).where(Employee.site_id.in_(site_ids)))
            )

        count_stmt = select(func.count()).select_from(PresenceSession).where(*filters)
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = (
            select(PresenceSession)
            .where(*filters)
            .order_by(PresenceSession.connected_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total
