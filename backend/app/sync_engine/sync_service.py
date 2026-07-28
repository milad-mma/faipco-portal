"""
هسته اصلی Sync Engine.

جریان کار برای هر Site:
1. خواندن SiteConnection (رمزگشایی پسورد) و EmployeeMapping
2. ساخت Adapter مناسب و خواندن ردیف‌های خام از جدول مبدأ
3. تبدیل هر ردیف خام به فیلدهای استاندارد Employee طبق Mapping
4. Insert رکوردهای جدید / Update رکوردهای موجود (بر اساس personnel_code در همان Site)
5. غیرفعال‌کردن (نه حذف فیزیکی) پرسنلی که دیگر در منبع دیده نشدند
6. ثبت نتیجه در SyncLog و به‌روزرسانی last_sync_* در SiteConnection
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_secret
from app.models.employee import Employee, EmployeeMapping
from app.models.site import SiteConnection, SyncStatus
from app.models.sync_log import SyncLog, SyncRunStatus
from app.sync_engine.adapter_factory import get_adapter


class SyncError(Exception):
    """خطای قابل نمایش به کاربر (مثلاً عدم وجود Mapping یا اتصال)."""


class SyncService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- عمومی ----------

    async def test_connection(self, site_id: int) -> tuple[bool, str | None]:
        conn = await self._get_site_connection(site_id)
        adapter = self._build_adapter(conn)
        return await adapter.test_connection()

    async def run_sync(self, site_id: int) -> SyncLog:
        conn = await self._get_site_connection(site_id)
        mapping = await self._get_mapping(site_id)
        adapter = self._build_adapter(conn)

        log = SyncLog(
            site_id=site_id, started_at=datetime.now(timezone.utc), status=SyncRunStatus.running
        )
        self.db.add(log)
        await self.db.flush()

        try:
            columns = self._mapping_columns(mapping)
            raw_rows = await adapter.fetch_rows(mapping.table_name, list(columns.values()))

            inserted, updated, seen_codes = await self._upsert_employees(site_id, columns, raw_rows)
            deactivated = await self._deactivate_missing(site_id, seen_codes)

            log.status = SyncRunStatus.success
            log.inserted_count = inserted
            log.updated_count = updated
            log.deactivated_count = deactivated

            conn.last_sync_status = SyncStatus.success
            conn.last_sync_error = None

        except Exception as e:  # noqa: BLE001 - هر خطایی باید در لاگ ثبت و به Admin نمایش داده شود
            log.status = SyncRunStatus.failed
            log.error_message = str(e)
            conn.last_sync_status = SyncStatus.failed
            conn.last_sync_error = str(e)

        finally:
            log.finished_at = datetime.now(timezone.utc)
            conn.last_sync_at = datetime.now(timezone.utc)
            await self.db.commit()

        return log

    # ---------- کمکی ----------

    async def _get_site_connection(self, site_id: int) -> SiteConnection:
        result = await self.db.execute(select(SiteConnection).where(SiteConnection.site_id == site_id))
        conn = result.scalar_one_or_none()
        if conn is None:
            raise SyncError("اتصال دیتابیس برای این Site تعریف نشده است")
        if not conn.is_active:
            raise SyncError("اتصال دیتابیس این Site غیرفعال است")
        return conn

    async def _get_mapping(self, site_id: int) -> EmployeeMapping:
        result = await self.db.execute(select(EmployeeMapping).where(EmployeeMapping.site_id == site_id))
        mapping = result.scalar_one_or_none()
        if mapping is None:
            raise SyncError("Mapping ستون‌های پرسنلی برای این Site تعریف نشده است")
        return mapping

    def _build_adapter(self, conn: SiteConnection):
        return get_adapter(
            conn.db_type,
            host=conn.host,
            port=conn.port,
            database=conn.database_name,
            username=conn.username,
            password=decrypt_secret(conn.password_encrypted),
        )

    @staticmethod
    def _mapping_columns(mapping: EmployeeMapping) -> dict[str, str]:
        """نگاشت نام فیلد استاندارد Employee -> نام ستون خام دیتابیس مبدأ."""
        columns = {
            "personnel_code": mapping.personnel_code_column,
            "first_name": mapping.first_name_column,
            "last_name": mapping.last_name_column,
        }
        if mapping.national_code_column:
            columns["national_code"] = mapping.national_code_column
        if mapping.mobile_column:
            columns["mobile"] = mapping.mobile_column
        return columns

    async def _upsert_employees(
        self, site_id: int, columns: dict[str, str], raw_rows: list[dict]
    ) -> tuple[int, int, set[str]]:
        inserted = 0
        updated = 0
        seen_codes: set[str] = set()
        now = datetime.now(timezone.utc)

        # پیش‌بارگذاری پرسنل موجود این Site تا در حلقه Query تکراری نزنیم
        result = await self.db.execute(select(Employee).where(Employee.site_id == site_id))
        existing_by_code = {emp.personnel_code: emp for emp in result.scalars().all()}

        for row in raw_rows:
            raw_code = row.get(columns["personnel_code"])
            personnel_code = str(raw_code).strip() if raw_code is not None else ""
            if not personnel_code:
                continue  # ردیف بدون کد پرسنلی معتبر نادیده گرفته می‌شود
            seen_codes.add(personnel_code)

            first_name = str(row.get(columns["first_name"]) or "").strip()
            last_name = str(row.get(columns["last_name"]) or "").strip()

            national_code = None
            if "national_code" in columns:
                raw_nc = row.get(columns["national_code"])
                national_code = str(raw_nc).strip() if raw_nc is not None else None

            mobile = None
            if "mobile" in columns:
                raw_mobile = row.get(columns["mobile"])
                mobile = str(raw_mobile).strip() if raw_mobile is not None else None

            existing = existing_by_code.get(personnel_code)
            if existing is None:
                self.db.add(
                    Employee(
                        personnel_code=personnel_code,
                        national_code=national_code,
                        first_name=first_name,
                        last_name=last_name,
                        mobile=mobile,
                        site_id=site_id,
                        is_active=True,
                        last_synced_at=now,
                    )
                )
                inserted += 1
            else:
                existing.first_name = first_name
                existing.last_name = last_name
                if national_code is not None:
                    existing.national_code = national_code
                if mobile is not None:
                    existing.mobile = mobile
                existing.is_active = True
                existing.last_synced_at = now
                updated += 1

        await self.db.flush()
        return inserted, updated, seen_codes

    async def _deactivate_missing(self, site_id: int, seen_codes: set[str]) -> int:
        """پرسنلی که دیگر در منبع دیده نشدند، غیرفعال می‌شوند (حذف فیزیکی هرگز انجام نمی‌شود)."""
        result = await self.db.execute(
            select(Employee).where(Employee.site_id == site_id, Employee.is_active.is_(True))
        )
        count = 0
        for emp in result.scalars().all():
            if emp.personnel_code not in seen_codes:
                emp.is_active = False
                count += 1
        await self.db.flush()
        return count
