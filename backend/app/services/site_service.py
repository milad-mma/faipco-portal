"""
منطق تجاری مدیریت Site ها: ساخت Site، تعریف/ویرایش/حذف اتصال دیتابیس
(با رمزنگاری خودکار پسورد)، و تعریف/ویرایش/حذف Mapping ستون‌های پرسنلی و تردد.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.org_tree import validate_roots
from app.core.security import encrypt_secret
from app.models.employee import EmployeeMapping
from app.models.site import AttendanceMapping, Site, SiteConnection
from app.schemas.site import AttendanceMappingIn, EmployeeMappingIn, SiteConnectionIn, SiteCreate


class SiteService:
    """عملیات CRUD روی Site، SiteConnection، EmployeeMapping و AttendanceMapping با یک AsyncSession."""

    def __init__(self, db: AsyncSession):
        """ورودی: AsyncSession دیتابیس پرتال."""
        self.db = db

    async def list_sites(self) -> list[Site]:
        """همه سایت‌ها را برمی‌گرداند."""
        result = await self.db.execute(select(Site))
        return list(result.scalars().all())

    async def create_site(self, payload: SiteCreate) -> Site:
        """یک سایت جدید از روی payload می‌سازد، commit می‌کند و آن را برمی‌گرداند."""
        site = Site(name=payload.name, code=payload.code, description=payload.description)
        self.db.add(site)
        await self.db.commit()
        await self.db.refresh(site)
        return site

    async def set_active(self, site_id: int, is_active: bool) -> Site | None:
        """وضعیت فعال بودن سایت را تغییر می‌دهد؛ اگر سایت پیدا نشود None برمی‌گرداند."""
        site = await self.db.get(Site, site_id)
        if site is None:
            return None
        site.is_active = is_active
        # با غیرفعال‌شدن Site، اتصال آن هم غیرفعال می‌شود تا Scheduler دیگر آن را Sync نکند.
        # این تغییر همیشه همراه غیرفعال‌کردن Site است؛ تأییدیه‌اش در UI گرفته می‌شود.
        if not is_active:
            conn = await self.get_connection(site_id)
            if conn is not None:
                conn.is_active = False
        await self.db.commit()
        await self.db.refresh(site)
        return site

    async def set_gps_location(
        self, site_id: int, latitude: float | None, longitude: float | None, radius_meters: int | None
    ) -> Site | None:
        """موقعیت GPS و شعاع مجاز سایت را ذخیره می‌کند (None برای پاک‌کردن)؛ سایت یا None را برمی‌گرداند."""
        site = await self.db.get(Site, site_id)
        if site is None:
            return None
        site.gps_latitude = latitude
        site.gps_longitude = longitude
        site.gps_radius_meters = radius_meters
        await self.db.commit()
        await self.db.refresh(site)
        return site

    async def get_attendance_mapping(self, site_id: int) -> AttendanceMapping | None:
        """نگاشت تردد سایت یا None را برمی‌گرداند."""
        result = await self.db.execute(select(AttendanceMapping).where(AttendanceMapping.site_id == site_id))
        return result.scalar_one_or_none()

    async def upsert_attendance_mapping(self, site_id: int, payload: AttendanceMappingIn) -> AttendanceMapping:
        """
        نگاشت جدول/ستون‌های تردد این سایت را می‌سازد یا به‌روزرسانی می‌کند و آن را برمی‌گرداند.
        اگر اتصال دیتابیس سایت (SQL Server، MySQL یا PostgreSQL) هنوز تعریف نشده باشد، ValueError می‌دهد.
        """
        conn = await self.get_connection(site_id)
        if conn is None:
            raise ValueError("گزارش تردد ماهانه فقط برای سایتی با اتصال دیتابیس تعریف‌شده قابل‌تنظیم است")

        mapping = await self.get_attendance_mapping(site_id)
        if mapping is None:
            mapping = AttendanceMapping(site_id=site_id, **payload.model_dump())
            self.db.add(mapping)
        else:
            # همه فیلدهای نگاشت موجود با مقادیر جدید جایگزین می‌شوند
            for field, value in payload.model_dump().items():
                setattr(mapping, field, value)

        await self.db.commit()
        await self.db.refresh(mapping)
        return mapping

    async def delete_attendance_mapping(self, site_id: int) -> bool:
        """نگاشت تردد سایت را حذف می‌کند؛ اگر وجود نداشت False برمی‌گرداند."""
        mapping = await self.get_attendance_mapping(site_id)
        if mapping is None:
            return False
        await self.db.delete(mapping)
        await self.db.commit()
        return True

    async def set_connection_active(self, site_id: int, is_active: bool) -> SiteConnection | None:
        """روشن/خاموش‌کردن همگام‌سازی خودکار این Site — بدون دست‌زدن به اطلاعات اتصال."""
        conn = await self.get_connection(site_id)
        if conn is None:
            return None
        conn.is_active = is_active
        await self.db.commit()
        await self.db.refresh(conn)
        return conn

    async def delete_site(self, site_id: int) -> bool:
        """
        حذف کامل و برگشت‌ناپذیر یک Site. به‌خاطر ondelete=CASCADE تعریف‌شده روی
        Department.site_id، Employee.site_id، EmployeeMapping.site_id و
        SiteConnection.site_id (در سطح دیتابیس)، همه واحدهای سازمانی و پرسنل
        همین Site هم به‌صورت خودکار حذف می‌شوند — به همین دلیل این عملیات باید
        فقط با تأییدیه صریح و قوی از سمت Admin در UI صدا زده شود.
        """
        site = await self.db.get(Site, site_id)
        if site is None:
            return False
        await self.db.delete(site)
        await self.db.commit()
        return True

    # ---------- Site Connection ----------

    async def get_connection(self, site_id: int) -> SiteConnection | None:
        """اتصال دیتابیس منبع سایت یا None را برمی‌گرداند."""
        result = await self.db.execute(select(SiteConnection).where(SiteConnection.site_id == site_id))
        return result.scalar_one_or_none()

    async def upsert_connection(self, site_id: int, payload: SiteConnectionIn) -> SiteConnection:
        """
        اتصال دیتابیس سایت را می‌سازد یا ویرایش می‌کند؛ رمز با encrypt_secret رمزنگاری می‌شود.
        برای اتصال جدید رمز الزامی است (در غیر این صورت ValueError). خروجی: رکورد اتصال.
        """
        conn = await self.get_connection(site_id)

        # ساخت اتصال جدید
        if conn is None:
            if not payload.password:
                raise ValueError("رمز عبور برای ساخت اتصال جدید الزامی است")
            conn = SiteConnection(
                site_id=site_id,
                db_type=payload.db_type,
                host=payload.host,
                port=payload.port,
                database_name=payload.database_name,
                username=payload.username,
                password_encrypted=encrypt_secret(payload.password),
            )
            self.db.add(conn)
        # ویرایش اتصال موجود
        else:
            conn.db_type = payload.db_type
            conn.host = payload.host
            conn.port = payload.port
            conn.database_name = payload.database_name
            conn.username = payload.username
            # اگر پسورد جدید داده نشده، پسورد قبلی حفظ می‌شود (رمزنگاری‌شده دست نمی‌خورد)
            if payload.password:
                conn.password_encrypted = encrypt_secret(payload.password)

        await self.db.commit()
        await self.db.refresh(conn)
        return conn

    async def delete_connection(self, site_id: int) -> bool:
        """اتصال دیتابیس سایت را حذف می‌کند؛ اگر وجود نداشت False برمی‌گرداند."""
        conn = await self.get_connection(site_id)
        if conn is None:
            return False
        await self.db.delete(conn)
        await self.db.commit()
        return True

    # ---------- Employee Mapping ----------

    async def get_mapping(self, site_id: int) -> EmployeeMapping | None:
        """نگاشت پرسنل سایت یا None را برمی‌گرداند."""
        result = await self.db.execute(select(EmployeeMapping).where(EmployeeMapping.site_id == site_id))
        return result.scalar_one_or_none()

    async def upsert_mapping(self, site_id: int, payload: EmployeeMappingIn) -> EmployeeMapping:
        """
        نگاشت پرسنل سایت را می‌سازد یا همه فیلدهایش را با payload جایگزین می‌کند و آن را برمی‌گرداند.
        اگر واحد ریشه‌ای در payload ریشه‌ی یک سایت هم‌منبع دیگر هم باشد، OrgTreeError می‌دهد (ذخیره نمی‌شود).
        """
        await self._ensure_roots_not_shared(site_id, payload.root_department_codes)
        mapping = await self.get_mapping(site_id)

        if mapping is None:
            mapping = EmployeeMapping(site_id=site_id, **payload.model_dump())
            self.db.add(mapping)
        else:
            for field, value in payload.model_dump().items():
                setattr(mapping, field, value)

        await self.db.commit()
        await self.db.refresh(mapping)
        return mapping

    async def _ensure_roots_not_shared(self, site_id: int, roots: list[str]) -> None:
        """
        بررسی می‌کند هیچ‌کدام از واحدهای ریشه‌ی این سایت ریشه‌ی سایت دیگری با همان دیتابیس منبع نباشد.
        بدون ریشه یا بدون اتصال تعریف‌شده، بررسی لازم نیست.
        """
        if not roots:
            return
        from app.sync_engine.sync_service import SyncService  # جلوگیری از import حلقه‌ای

        conn_result = await self.db.execute(select(SiteConnection).where(SiteConnection.site_id == site_id))
        conn = conn_result.scalar_one_or_none()
        if conn is None:
            return
        roots_by_site = await SyncService(self.db).sibling_roots(site_id, conn)
        roots_by_site[site_id] = set(roots)
        validate_roots(roots_by_site)

    async def delete_mapping(self, site_id: int) -> bool:
        """نگاشت پرسنل سایت را حذف می‌کند؛ اگر وجود نداشت False برمی‌گرداند."""
        mapping = await self.get_mapping(site_id)
        if mapping is None:
            return False
        await self.db.delete(mapping)
        await self.db.commit()
        return True
