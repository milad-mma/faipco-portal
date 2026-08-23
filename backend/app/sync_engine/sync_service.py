"""
هسته اصلی Sync Engine.

جریان کار برای هر Site:
1. خواندن SiteConnection (رمزگشایی پسورد) و EmployeeMapping
2. اگر جدول Lookup واحدها تعریف شده باشد (مثل dbo.Sections با ستون‌های
   Sec_No/Title)، آن را یک‌بار در ابتدای Sync می‌خواند تا کد هر واحد را
   به نام واقعی‌اش ترجمه کند
3. ساخت Adapter مناسب و خواندن ردیف‌های خام جدول پرسنل از منبع
4. تبدیل هر ردیف خام به فیلدهای استاندارد Employee طبق Mapping — شامل
   پیدا/ساخت خودکار واحد سازمانی متناظر بر اساس کد بخش (Sec_No)
5. Insert رکوردهای جدید / Update رکوردهای موجود (بر اساس personnel_code در همان Site)
6. غیرفعال‌کردن (نه حذف فیزیکی) پرسنلی که دیگر در منبع دیده نشدند، یا طبق
   ستون is_active_column (در صورت تعریف) در منبع غیرفعال اعلام شده‌اند
7. ثبت نتیجه در SyncLog و به‌روزرسانی last_sync_* در SiteConnection
"""
from datetime import datetime, timezone
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_secret, normalize_login_credential
from app.models.employee import Department, Employee, EmployeeMapping
from app.models.site import Site, SiteConnection, SyncStatus
from app.models.sync_log import SyncLog, SyncRunStatus
from app.sync_engine.adapter_factory import get_adapter

logger = logging.getLogger("faipco.sync")

# مقادیری که در ستون is_active منبع به معنای «غیرفعال» تلقی می‌شوند
_FALSY_ACTIVE_VALUES = {"0", "false", "no", "n", "inactive", "f", "غیرفعال"}


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
            department_lookup = await self._load_lookup_table(
                adapter,
                mapping.department_lookup_table,
                mapping.department_lookup_id_column,
                mapping.department_lookup_name_column,
            )
            position_lookup = await self._load_lookup_table(
                adapter,
                mapping.position_lookup_table,
                mapping.position_lookup_id_column,
                mapping.position_lookup_name_column,
            )

            inserted, updated, skipped_inactive, seen_codes = await self._upsert_employees(
                site_id, columns, raw_rows, department_lookup, position_lookup, mapping.is_active_inverted
            )

            try:
                await self._sync_employee_photos(site_id, adapter, mapping)
            except Exception as photo_error:  # noqa: BLE001 - عکس پرسنل نباید کل Sync را ناموفق کند
                logger.warning(
                    "همگام‌سازی عکس پرسنل سایت %s ناموفق بود (بقیه Sync ادامه یافت): %s",
                    site_id,
                    photo_error,
                )

            deactivated = await self._deactivate_missing(site_id, seen_codes)

            log.status = SyncRunStatus.success
            log.inserted_count = inserted
            log.updated_count = updated
            log.deactivated_count = deactivated
            log.skipped_inactive_count = skipped_inactive

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

    async def get_status_summary(self) -> dict:
        """
        خلاصه وضعیت Sync امروز برای همه Site های فعال — چند سایت امروز حداقل
        یک اجرای موفق داشته‌اند، چند سایت ناموفق بوده‌اند، و چند سایت اصلاً
        امروز اجرا نشده‌اند. برای کارت آمار داشبورد Admin استفاده می‌شود.
        """
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        sites_result = await self.db.execute(select(Site.id).where(Site.is_active.is_(True)))
        site_ids = [row[0] for row in sites_result.all()]

        logs_result = await self.db.execute(
            select(SyncLog.site_id, SyncLog.status, SyncLog.started_at)
            .where(SyncLog.site_id.in_(site_ids), SyncLog.started_at >= today_start)
            .order_by(SyncLog.site_id, SyncLog.started_at.desc())
        )
        # فقط آخرین اجرای امروز هر Site مهم است — چون ردیف‌ها بر اساس
        # site_id و بعد started_at نزولی مرتب شده‌اند، اولین باری که یک
        # site_id دیده می‌شود دقیقاً همان آخرین اجرای امروزش است.
        latest_status_by_site: dict[int, SyncRunStatus] = {}
        for site_id, run_status, _started_at in logs_result.all():
            if site_id not in latest_status_by_site:
                latest_status_by_site[site_id] = run_status

        success_today = sum(1 for s in latest_status_by_site.values() if s == SyncRunStatus.success)
        failed_today = sum(1 for s in latest_status_by_site.values() if s == SyncRunStatus.failed)
        not_run_today = len(site_ids) - len(latest_status_by_site)

        return {
            "total_sites": len(site_ids),
            "success_today": success_today,
            "failed_today": failed_today,
            "not_run_today": not_run_today,
        }

    async def _get_site_connection(self, site_id: int) -> SiteConnection:
        """
        اتصال دیتابیس این Site را برمی‌گرداند — صرف‌نظر از این‌که Sync خودکار
        برایش روشن است یا خاموش (SiteConnection.is_active). آن فیلد فقط تعیین
        می‌کند آیا Scheduler خودکار این Site را در چرخه دوره‌ای اجرا کند یا نه؛
        اجرای دستی (از پنل Admin) و تست اتصال همیشه باید کار کنند تا وقتی Sync
        خودکار خاموش است هم بشود در صورت نیاز به‌صورت دستی همگام‌سازی کرد.
        """
        result = await self.db.execute(select(SiteConnection).where(SiteConnection.site_id == site_id))
        conn = result.scalar_one_or_none()
        if conn is None:
            raise SyncError("اتصال دیتابیس برای این Site تعریف نشده است")
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
        if mapping.birth_date_column:
            columns["birth_date_raw"] = mapping.birth_date_column
        if mapping.is_active_column:
            columns["is_active_raw"] = mapping.is_active_column
        if mapping.department_column:
            columns["department_raw"] = mapping.department_column
        if mapping.position_column:
            columns["position_raw"] = mapping.position_column
        return columns

    async def _load_lookup_table(
        self, adapter, table: str | None, id_column: str | None, name_column: str | None
    ) -> dict[str, str]:
        """
        یک جدول Lookup عمومی «کد -> نام واقعی» را می‌خواند — هم برای واحد
        سازمانی (مثل dbo.Sections) و هم برای سمت (مثل Position با ستون‌های
        Pos_No/Title) استفاده می‌شود. اگر تعریف نشده باشد، دیکشنری خالی
        برمی‌گردد (یعنی همان کد خام به‌جای نام واقعی نمایش داده می‌شود).
        """
        if not (table and id_column and name_column):
            return {}

        rows = await adapter.fetch_rows(table, [id_column, name_column])

        lookup: dict[str, str] = {}
        for row in rows:
            raw_id = row.get(id_column)
            if raw_id is None:
                continue
            raw_name = row.get(name_column)
            lookup[str(raw_id).strip()] = str(raw_name).strip() if raw_name is not None else str(raw_id).strip()
        return lookup

    async def _get_or_create_department(
        self, site_id: int, code: str, name: str, cache: dict[str, int]
    ) -> int:
        """واحد سازمانی متناظر با این کد را پیدا می‌کند، یا اگر نبود می‌سازد."""
        if code in cache:
            return cache[code]

        result = await self.db.execute(
            select(Department).where(Department.site_id == site_id, Department.code == code)
        )
        department = result.scalar_one_or_none()

        if department is None:
            department = Department(site_id=site_id, name=name, code=code)
            self.db.add(department)
            await self.db.flush()
        elif department.name != name:
            # اگر عنوان بخش در منبع (مثلاً ستون Title) تغییر کرده، همگام می‌کنیم
            department.name = name

        cache[code] = department.id
        return department.id

    @staticmethod
    def _coerce_is_active(raw_value) -> bool:
        """مقدار خام ستون is_active منبع را به True/False تبدیل می‌کند."""
        if raw_value is None:
            return True
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, (int, float)):
            return bool(raw_value)
        return str(raw_value).strip().lower() not in _FALSY_ACTIVE_VALUES

    @staticmethod
    def _parse_birth_month_day(raw_value) -> tuple[int, int] | None:
        """
        روز/ماه تولد را از مقدار خام ستون تاریخ تولد (شمسی) دیتابیس مبدأ
        استخراج می‌کند — بدون نیاز به تبدیل تقویم، چون فقط برای «متولدین
        روز جاری» لازم است، نه محاسبه سن. دو فرمت رایج پشتیبانی می‌شود:
        - رشته جداشده با / یا - یا . به ترتیب سال-ماه-روز (مثل «1370/05/21»)
        - رشته ۸ رقمی چسبیده به همان ترتیب (مثل «13700521»)
        اگر مقدار خام قابل‌تفسیر نبود (خالی، NULL، فرمت ناشناس)، None برمی‌گردد
        و آن پرسنل فقط بدون تاریخ تولد ثبت می‌شود — Sync هرگز به همین دلیل شکست نمی‌خورد.
        """
        if raw_value is None:
            return None
        text = str(raw_value).strip()
        if not text:
            return None

        for sep in ("/", "-", "."):
            if sep in text:
                parts = text.split(sep)
                if len(parts) == 3:
                    try:
                        _year, month, day = (int(p) for p in parts)
                        if 1 <= month <= 12 and 1 <= day <= 31:
                            return month, day
                    except ValueError:
                        return None
                return None

        if text.isdigit() and len(text) == 8:
            try:
                month, day = int(text[4:6]), int(text[6:8])
                if 1 <= month <= 12 and 1 <= day <= 31:
                    return month, day
            except ValueError:
                return None

        return None

    @staticmethod
    def _normalize_fixed_length_digits(raw_value, length: int) -> str | None:
        """
        برای فیلدهایی مثل کد ملی (همیشه دقیقاً ۱۰ رقم) و موبایل (همیشه دقیقاً
        ۱۱ رقم، با ۰ شروع می‌شود) — یک باگ واقعی که روی همین پروژه کشف شد:
        اگر ستون مبدأ در دیتابیس خارجی به‌صورت عددی (نه متنی) ذخیره شده باشد،
        درایور دیتابیس این مقدار را به‌صورت int/float برمی‌گرداند، که صفرهای
        ابتدایی را برای همیشه از دست می‌دهد (چون در یک عدد، ۰۰۱۲۳۴۵۶۷۸ همان
        ۱۲۳۴۵۶۷۸ است) — دقیقاً پرسنلی که کد ملی‌شان با ۰ یا ۰۰ شروع می‌شود
        (خیلی از استان‌ها) از این آسیب می‌دیدند: ورود اولشان (که کد ملی رمز
        پیش‌فرض است) با «اطلاعات ورود اشتباه است» رد می‌شد، چون مقدار
        ذخیره‌شده در دیتابیس پرتال با کد ملی واقعی روی کارتشان یکی نبود.

        چون طول این دو فیلد در ایران همیشه ثابت است، این تابع با اطمینان
        صفرهای ابتدایی گم‌شده را با zfill بازمی‌گرداند — چه مقدار مبدأ از
        اول رشته بوده چه عدد.
        """
        if raw_value is None:
            return None
        if isinstance(raw_value, float):
            raw_value = int(raw_value)
        # normalize_login_credential ارقام فارسی/عربی احتمالی را هم به لاتین
        # تبدیل می‌کند و کاراکترهای نامرئی را حذف می‌کند — برای هم‌خوانی با
        # همان تابعی که هنگام ورود کاربر استفاده می‌شود.
        text = normalize_login_credential(str(raw_value))
        if not text:
            return None
        return text.zfill(length)

    async def _upsert_employees(
        self,
        site_id: int,
        columns: dict[str, str],
        raw_rows: list[dict],
        department_lookup: dict[str, str],
        position_lookup: dict[str, str],
        is_active_inverted: bool = False,
    ) -> tuple[int, int, int, set[str]]:
        inserted = 0
        updated = 0
        skipped_inactive = 0
        seen_codes: set[str] = set()
        now = datetime.now(timezone.utc)
        has_department_mapping = "department_raw" in columns
        department_cache: dict[str, int] = {}

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
                national_code = self._normalize_fixed_length_digits(raw_nc, 10)

            mobile = None
            if "mobile" in columns:
                raw_mobile = row.get(columns["mobile"])
                mobile = self._normalize_fixed_length_digits(raw_mobile, 11)

            birth_month = birth_day = None
            if "birth_date_raw" in columns:
                parsed_birth = self._parse_birth_month_day(row.get(columns["birth_date_raw"]))
                if parsed_birth is not None:
                    birth_month, birth_day = parsed_birth

            position_title = None
            if "position_raw" in columns:
                raw_position = row.get(columns["position_raw"])
                position_code = str(raw_position).strip() if raw_position not in (None, "") else None
                if position_code:
                    position_title = position_lookup.get(position_code, position_code)

            if "is_active_raw" in columns:
                is_active = self._coerce_is_active(row.get(columns["is_active_raw"]))
                if is_active_inverted:
                    # مثل ستون IsCut: ۱=غیرفعال، ۰=فعال — برعکس فرض پیش‌فرض
                    is_active = not is_active
            else:
                is_active = True

            department_id = None
            if has_department_mapping:
                raw_dept = row.get(columns["department_raw"])
                dept_code = str(raw_dept).strip() if raw_dept not in (None, "") else None
                if dept_code:
                    dept_name = department_lookup.get(dept_code, dept_code)
                    department_id = await self._get_or_create_department(
                        site_id, dept_code, dept_name, department_cache
                    )

            existing = existing_by_code.get(personnel_code)

            if existing is None and not is_active:
                # ⚠️ پرسنلی که تا امروز اصلاً وارد پرتال نشده و همین الان هم در
                # منبع IsActive=۰ یا IsCut=۱ است، اصلاً Import نمی‌شود — نه فقط
                # is_active=False. برخلاف پرسنلی که قبلاً فعال بوده و بعداً کات
                # شده (که رکورد و سوابقش، مثل فیش حقوقی، دست‌نخورده می‌ماند —
                # فقط پایین همین تابع is_active=False می‌شود)، اینجا اصلاً هیچ
                # رکوردی برایش وجود نداشته که نگهش داریم.
                skipped_inactive += 1
                continue

            if existing is None:
                self.db.add(
                    Employee(
                        personnel_code=personnel_code,
                        national_code=national_code,
                        first_name=first_name,
                        last_name=last_name,
                        mobile=mobile,
                        site_id=site_id,
                        department_id=department_id,
                        is_active=is_active,
                        birth_month=birth_month,
                        birth_day=birth_day,
                        position_title=position_title,
                        # is_enabled عمداً اینجا تنظیم نمی‌شود — مقدار پیش‌فرض
                        # ستون (True) اعمال می‌شود؛ این فیلد فقط دستی از پنل تغییر می‌کند.
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
                if "birth_date_raw" in columns:
                    existing.birth_month = birth_month
                    existing.birth_day = birth_day
                if "position_raw" in columns:
                    existing.position_title = position_title
                if has_department_mapping:
                    existing.department_id = department_id
                existing.is_active = is_active
                # نکته مهم: is_enabled عمداً اینجا دست‌کاری نمی‌شود. آن یک
                # تصمیم دستی Admin است (از پنل «پرسنل») و باید مستقل از نتیجه
                # هر اجرای Sync باقی بماند.
                existing.last_synced_at = now
                updated += 1

        await self.db.flush()
        return inserted, updated, skipped_inactive, seen_codes

    async def _sync_employee_photos(self, site_id: int, adapter, mapping: EmployeeMapping) -> None:
        """
        اگر Mapping شامل اطلاعات جدول عکس پرسنل باشد (مثل EmployeeExtendedInfo
        با ستون‌های Emp_No/ThumbnailImg)، تصویر بندانگشتی هر پرسنل را می‌خواند
        و روی همان رکورد Employee که در همین چرخه Sync درج/به‌روزرسانی شد،
        ذخیره می‌کند. اگر این سه فیلد در Mapping تعریف نشده باشند، کاری انجام
        نمی‌دهد — یعنی این قابلیت کاملاً اختیاری است و نبودش خطا ایجاد نمی‌کند.
        فراخوانی این تابع در run_sync داخل try/except جداگانه است، پس حتی اگر
        جدول/ستون‌ها اشتباه تعریف شده باشند، کل Sync پرسنل شکست نمی‌خورد.
        """
        if not (mapping.photo_table and mapping.photo_emp_no_column and mapping.photo_thumbnail_column):
            return

        rows = await adapter.fetch_rows(
            mapping.photo_table, [mapping.photo_emp_no_column, mapping.photo_thumbnail_column]
        )

        photo_by_code: dict[str, bytes] = {}
        for row in rows:
            raw_code = row.get(mapping.photo_emp_no_column)
            if raw_code is None:
                continue
            raw_photo = row.get(mapping.photo_thumbnail_column)
            if raw_photo:
                photo_by_code[str(raw_code).strip()] = bytes(raw_photo)

        if not photo_by_code:
            return

        result = await self.db.execute(
            select(Employee).where(
                Employee.site_id == site_id, Employee.personnel_code.in_(photo_by_code.keys())
            )
        )
        for employee in result.scalars().all():
            photo = photo_by_code.get(employee.personnel_code)
            if photo is not None:
                employee.photo_thumbnail = photo

        await self.db.flush()

    async def _deactivate_missing(self, site_id: int, seen_codes: set[str]) -> int:
        """پرسنلی که دیگر اصلاً در منبع دیده نشدند (حذف فیزیکی از منبع)، غیرفعال می‌شوند."""
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
