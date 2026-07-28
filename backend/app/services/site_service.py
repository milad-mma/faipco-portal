"""
منطق تجاری مدیریت Site ها: ساخت Site، تعریف/ویرایش اتصال دیتابیس (با رمزنگاری پسورد)،
و تعریف/ویرایش Mapping ستون‌های پرسنلی.
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

    async def upsert_connection(self, site_id: int, payload: SiteConnectionIn) -> SiteConnection:
        result = await self.db.execute(select(SiteConnection).where(SiteConnection.site_id == site_id))
        conn = result.scalar_one_or_none()
        encrypted_password = encrypt_secret(payload.password)

        if conn is None:
            conn = SiteConnection(
                site_id=site_id,
                db_type=payload.db_type,
                host=payload.host,
                port=payload.port,
                database_name=payload.database_name,
                username=payload.username,
                password_encrypted=encrypted_password,
            )
            self.db.add(conn)
        else:
            conn.db_type = payload.db_type
            conn.host = payload.host
            conn.port = payload.port
            conn.database_name = payload.database_name
            conn.username = payload.username
            conn.password_encrypted = encrypted_password

        await self.db.commit()
        await self.db.refresh(conn)
        return conn

    async def upsert_mapping(self, site_id: int, payload: EmployeeMappingIn) -> EmployeeMapping:
        result = await self.db.execute(select(EmployeeMapping).where(EmployeeMapping.site_id == site_id))
        mapping = result.scalar_one_or_none()

        if mapping is None:
            mapping = EmployeeMapping(site_id=site_id, **payload.model_dump())
            self.db.add(mapping)
        else:
            for field, value in payload.model_dump().items():
                setattr(mapping, field, value)

        await self.db.commit()
        await self.db.refresh(mapping)
        return mapping
