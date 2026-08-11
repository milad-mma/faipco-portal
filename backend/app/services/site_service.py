"""
منطق تجاری مدیریت Site ها: ساخت Site، تعریف/ویرایش/حذف اتصال دیتابیس
(با رمزنگاری خودکار پسورد)، و تعریف/ویرایش/حذف Mapping ستون‌های پرسنلی.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_secret
from app.models.employee import EmployeeMapping
from app.models.site import Site, SiteConnection
from app.schemas.site import EmployeeMappingIn, SiteConnectionIn, SiteCreate


class SiteService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_sites(self) -> list[Site]:
        result = await self.db.execute(select(Site))
        return list(result.scalars().all())

    async def create_site(self, payload: SiteCreate) -> Site:
        site = Site(name=payload.name, code=payload.code, description=payload.description)
        self.db.add(site)
        await self.db.commit()
        await self.db.refresh(site)
        return site

    async def set_active(self, site_id: int, is_active: bool) -> Site | None:
        site = await self.db.get(Site, site_id)
        if site is None:
            return None
        site.is_active = is_active
        await self.db.commit()
        await self.db.refresh(site)
        return site

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
        result = await self.db.execute(select(SiteConnection).where(SiteConnection.site_id == site_id))
        return result.scalar_one_or_none()

    async def upsert_connection(self, site_id: int, payload: SiteConnectionIn) -> SiteConnection:
        conn = await self.get_connection(site_id)

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
        conn = await self.get_connection(site_id)
        if conn is None:
            return False
        await self.db.delete(conn)
        await self.db.commit()
        return True

    # ---------- Employee Mapping ----------

    async def get_mapping(self, site_id: int) -> EmployeeMapping | None:
        result = await self.db.execute(select(EmployeeMapping).where(EmployeeMapping.site_id == site_id))
        return result.scalar_one_or_none()

    async def upsert_mapping(self, site_id: int, payload: EmployeeMappingIn) -> EmployeeMapping:
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

    async def delete_mapping(self, site_id: int) -> bool:
        mapping = await self.get_mapping(site_id)
        if mapping is None:
            return False
        await self.db.delete(mapping)
        await self.db.commit()
        return True
