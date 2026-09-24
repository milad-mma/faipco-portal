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
   و در صورت نگاشت، همگام‌سازی تصویر بندانگشتی پرسنل
6. غیرفعال‌کردن (نه حذف فیزیکی) پرسنلی که دیگر در منبع دیده نشدند، یا طبق
   ستون is_active_column (در صورت تعریف) در منبع غیرفعال اعلام شده‌اند
7. ثبت نتیجه در SyncLog و به‌روزرسانی last_sync_* در SiteConnection

چند سایت با یک دیتابیس منبع مشترک (فیلتر واحد ریشه):
اگر در نگاشت پرسنل «واحدهای ریشه» تعریف شده باشد، درخت واحدها (مثل Sections.TFather)
خوانده و هر واحد به سایتی داده می‌شود که نزدیک‌ترین ریشه‌ی بالادستش را دارد
(core/org_tree.py، با در نظر گرفتن ریشه‌های همه‌ی سایت‌هایی که به همان دیتابیس وصل‌اند).
- پرسنل واحدهای این سایت Sync می‌شوند.
- پرسنل واحدهای سایت‌های دیگر نادیده گرفته می‌شوند، ولی اگر رکوردشان هنوز در این
  سایت است غیرفعال نمی‌شوند تا Sync سایت مقصد آن را منتقل کند.
- پرسنلی که واحدشان زیر هیچ ریشه‌ای نیست وارد نمی‌شوند، رکورد موجودشان دست نمی‌خورد
  و در SyncLog هشدار ثبت می‌شود.
- اگر پرسنلی که مال این سایت است هنوز در یک سایت هم‌منبع دیگر رکورد دارد، همان رکورد
  (با حساب کاربری و همه‌ی سوابق) به این سایت منتقل و در site_transfers ثبت می‌شود.
"""
from datetime import datetime, timezone
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.org_tree import OrgTreeError, assign_units_to_sites, build_parent_map, normalize_code
from app.core.security import decrypt_secret, normalize_login_credential
from app.models.employee import Department, Employee, EmployeeMapping
from app.models.site import Site, SiteConnection, SyncStatus
from app.models.site_transfer import SiteTransfer
from app.models.sync_log import SyncLog, SyncRunStatus
from app.models.user import User
from app.sync_engine.adapter_factory import get_adapter

logger = logging.getLogger("faipco.sync")

# مقادیری که در ستون is_active منبع به معنای «غیرفعال» تلقی می‌شوند
_FALSY_ACTIVE_VALUES = {"0", "false", "no", "n", "inactive", "f", "غیرفعال"}


class SyncError(Exception):
    """خطای قابل نمایش به کاربر (مثلاً عدم وجود Mapping یا اتصال)."""


class SyncService:
    """اجرای Sync پرسنل یک سایت از دیتابیس منبع به جدول employees پرتال، تست اتصال و خلاصه وضعیت."""

    def __init__(self, db: AsyncSession):
        """ورودی: AsyncSession دیتابیس پرتال."""
        self.db = db

    # ---------- عمومی ----------

    async def test_connection(self, site_id: int) -> tuple[bool, str | None]:
        """اتصال به دیتابیس منبع سایت را تست می‌کند؛ خروجی: (موفق؟, پیام خطا). بدون اتصال تعریف‌شده SyncError."""
        conn = await self._get_site_connection(site_id)
        adapter = self._build_adapter(conn)
        return await adapter.test_connection()

    async def run_sync(self, site_id: int) -> SyncLog:
        """
        یک اجرای کامل Sync پرسنل سایت را انجام می‌دهد و رکورد SyncLog آن را برمی‌گرداند.
        هر خطای حین اجرا در SyncLog و SiteConnection ثبت می‌شود (نه پرتاب)؛ نبود اتصال/Mapping پیش از شروع SyncError می‌دهد.
        """
        conn = await self._get_site_connection(site_id)
        mapping = await self._get_mapping(site_id)
        adapter = self._build_adapter(conn)

        log = SyncLog(
            site_id=site_id, started_at=datetime.now(timezone.utc), status=SyncRunStatus.running
        )
        self.db.add(log)
        await self.db.flush()  # برای گرفتن log.id پیش از شروع

        try:
            # خواندن ردیف‌های خام پرسنل (ستون‌های تکراری حذف می‌شوند) و فیلتر شعبه
            columns = self._mapping_columns(mapping)
            raw_rows = await adapter.fetch_rows(mapping.table_name, list(dict.fromkeys(columns.values())))
            raw_rows = self._filter_branch(mapping, raw_rows)
            # جدول‌های Lookup واحد و سمت (در صورت تعریف)
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

            # فیلتر واحد ریشه (فقط اگر ریشه تعریف شده باشد)
            protected_codes: set[str] = set()  # کدهایی که در منبع هستند ولی مال این سایت نیستند
            sibling_site_ids: set[int] = set()
            warning: str | None = None
            skipped_unassigned = 0
            org_scope = await self._resolve_org_scope(site_id, conn, mapping, adapter)
            if org_scope is not None:
                assignment, sibling_site_ids = org_scope
                raw_rows, owned_elsewhere, unassigned_codes, skipped_unassigned, warning = self._split_rows_by_org(
                    site_id, columns, raw_rows, assignment, department_lookup
                )
                protected_codes, pending = await self._protected_codes(site_id, owned_elsewhere, unassigned_codes)
                if pending:
                    note = f"{pending} نفر هنوز در این سایت‌اند ولی واحدشان متعلق به سایت دیگری است و منتظر Sync آن سایت برای انتقال‌اند."
                    warning = f"{warning} | {note}" if warning else note

            inserted, updated, skipped_inactive, seen_codes, transferred = await self._upsert_employees(
                site_id,
                columns,
                raw_rows,
                department_lookup,
                position_lookup,
                mapping.is_active_inverted,
                transfer_from_site_ids=sibling_site_ids,
            )

            # همگام‌سازی عکس‌ها جدا از بقیه؛ خطای آن فقط لاگ می‌شود
            try:
                await self._sync_employee_photos(site_id, adapter, mapping)
            except Exception as photo_error:  # noqa: BLE001 - عکس پرسنل نباید کل Sync را ناموفق کند
                logger.warning(
                    "همگام‌سازی عکس پرسنل سایت %s ناموفق بود (بقیه Sync ادامه یافت): %s",
                    site_id,
                    photo_error,
                )

            deactivated = await self._deactivate_missing(site_id, seen_codes | protected_codes)

            # ثبت نتیجه موفق
            log.status = SyncRunStatus.success
            log.inserted_count = inserted
            log.updated_count = updated
            log.deactivated_count = deactivated
            log.skipped_inactive_count = skipped_inactive
            log.skipped_unassigned_count = skipped_unassigned
            log.transferred_count = transferred
            log.warning_message = warning

            conn.last_sync_status = SyncStatus.success
            conn.last_sync_error = None

        except Exception as e:  # noqa: BLE001 - هر خطایی باید در لاگ ثبت و به Admin نمایش داده شود
            log.status = SyncRunStatus.failed
            log.error_message = str(e)
            conn.last_sync_status = SyncStatus.failed
            conn.last_sync_error = str(e)

        finally:
            # زمان پایان و commit در هر حالت (موفق یا ناموفق)
            log.finished_at = datetime.now(timezone.utc)
            conn.last_sync_at = datetime.now(timezone.utc)
            await self.db.commit()

        return log

    async def preview_org_scope(self, site_id: int, mapping: EmployeeMapping) -> dict:
        """
        پیش‌نمایش فیلتر واحد ریشه بدون ذخیره: درخت واحدهای منبع را می‌خواند، با ریشه‌های پیشنهادی
        این سایت (mapping ذخیره‌نشده) و ریشه‌های ذخیره‌شده‌ی سایت‌های هم‌منبع تقسیم می‌کند و
        تعداد واحد و پرسنل فعال هر سایت و پرسنل بی‌سایت را برمی‌گرداند.
        خطای تنظیمات (فیلد ناقص، ریشه‌ی تکراری) در کلید error برمی‌گردد، نه به‌صورت استثنا.
        """
        conn = await self._get_site_connection(site_id)
        empty = {"units": [], "sites": [], "unassigned_active_employees": 0, "error": None}
        missing = self.org_filter_missing_fields(mapping)
        if missing:
            return {**empty, "error": "این فیلدهای نگاشت پرسنل باید پر شوند: " + "، ".join(missing)}

        adapter = self._build_adapter(conn)
        roots_by_site = await self.sibling_roots(site_id, conn)
        own_roots = self.root_codes(mapping)
        if own_roots:
            roots_by_site[site_id] = own_roots

        # درخت و نام واحدها
        parents = await self.load_parent_map(adapter, mapping)
        names = await self._load_lookup_table(
            adapter,
            mapping.department_lookup_table,
            mapping.department_lookup_id_column,
            mapping.department_lookup_name_column,
        )
        try:
            assignment = assign_units_to_sites(parents, roots_by_site)
        except OrgTreeError as e:
            return {**empty, "error": str(e)}

        # شمارش پرسنل فعال منبع در هر واحد (با فیلتر شعبه و ستون وضعیت، مثل Sync)
        columns = self._mapping_columns(mapping)
        rows = await adapter.fetch_rows(mapping.table_name, list(dict.fromkeys(columns.values())))
        rows = self._filter_branch(mapping, rows)
        active_by_unit: dict[str, int] = {}
        for row in rows:
            if "is_active_raw" in columns:
                active = self._coerce_is_active(row.get(columns["is_active_raw"]))
                if mapping.is_active_inverted:
                    active = not active
                if not active:
                    continue
            unit = normalize_code(row.get(columns["department_raw"])) or "—"
            active_by_unit[unit] = active_by_unit.get(unit, 0) + 1

        # نام سایت‌ها
        site_ids = set(roots_by_site) | {site_id}
        sites_result = await self.db.execute(select(Site.id, Site.name).where(Site.id.in_(site_ids)))
        site_names = dict(sites_result.all())

        all_roots = {code for codes in roots_by_site.values() for code in codes}
        units = [
            {
                "code": code,
                "name": names.get(code, code),
                "parent": parents.get(code),
                "site_id": assignment.get(code),
                "is_root": code in all_roots,
                "active_employees": active_by_unit.get(code, 0),
            }
            for code in sorted(set(parents) | set(assignment), key=lambda c: (len(c), c))
        ]
        sites = []
        for sid in sorted(site_ids, key=lambda x: (x != site_id, x)):
            owned = [u for u in units if u["site_id"] == sid]
            sites.append(
                {
                    "site_id": sid,
                    "site_name": site_names.get(sid, f"سایت {sid}"),
                    "is_current": sid == site_id,
                    "roots": sorted(roots_by_site.get(sid, set())),
                    "unit_count": len(owned),
                    "active_employee_count": sum(u["active_employees"] for u in owned),
                }
            )
        # پرسنل فعالی که واحدشان در درخت نیست یا به هیچ سایتی نمی‌رسد
        unassigned = sum(
            count for unit, count in active_by_unit.items() if assignment.get(unit) is None
        )
        return {"units": units, "sites": sites, "unassigned_active_employees": unassigned, "error": None}

    # ---------- کمکی ----------

    async def get_status_summary(self) -> dict:
        """
        خلاصه وضعیت Sync امروز برای همه Site های فعال — چند سایت امروز حداقل
        یک اجرای موفق داشته‌اند، چند سایت ناموفق بوده‌اند، و چند سایت اصلاً
        امروز اجرا نشده‌اند. برای کارت آمار داشبورد Admin استفاده می‌شود.
        «امروز» از نیمه‌شب UTC حساب می‌شود.
        """
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        # سایت‌های فعال
        sites_result = await self.db.execute(select(Site.id).where(Site.is_active.is_(True)))
        site_ids = [row[0] for row in sites_result.all()]

        # اجراهای امروز این سایت‌ها، مرتب بر اساس سایت و جدیدترین اول
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
        if conn is None:  # بدون اتصال تعریف‌شده: SyncError
            raise SyncError("اتصال دیتابیس برای این Site تعریف نشده است")
        return conn

    async def _get_mapping(self, site_id: int) -> EmployeeMapping:
        """نگاشت پرسنل سایت را برمی‌گرداند؛ اگر تعریف نشده باشد SyncError."""
        result = await self.db.execute(select(EmployeeMapping).where(EmployeeMapping.site_id == site_id))
        mapping = result.scalar_one_or_none()
        if mapping is None:
            raise SyncError("Mapping ستون‌های پرسنلی برای این Site تعریف نشده است")
        return mapping

    def _build_adapter(self, conn: SiteConnection):
        """Adapter دیتابیس منبع را با پسورد رمزگشایی‌شده می‌سازد."""
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
        """
        نگاشت نام فیلد استاندارد Employee -> نام ستون خام دیتابیس مبدأ.
        فیلدهای اختیاری فقط اگر در Mapping تعریف شده باشند اضافه می‌شوند؛ پسوند _raw یعنی مقدار نیاز به تبدیل دارد.
        """
        columns = {
            "personnel_code": mapping.personnel_code_column,
            "first_name": mapping.first_name_column,
            "last_name": mapping.last_name_column,
        }
        if mapping.national_code_column:
            columns["national_code"] = mapping.national_code_column
        if mapping.mobile_column:
            columns["mobile"] = mapping.mobile_column
        if mapping.email_column:
            columns["email"] = mapping.email_column
        if mapping.birth_date_column:
            columns["birth_date_raw"] = mapping.birth_date_column
        if (mapping.hire_date_column or "").strip():
            columns["hire_date_raw"] = mapping.hire_date_column.strip()
        if (mapping.gender_column or "").strip():
            columns["gender_raw"] = mapping.gender_column.strip()
        if mapping.is_active_column:
            columns["is_active_raw"] = mapping.is_active_column
        if mapping.department_column:
            columns["department_raw"] = mapping.department_column
        if mapping.position_column:
            columns["position_raw"] = mapping.position_column
        if (mapping.branch_code_column or "").strip():
            columns["branch_code_raw"] = mapping.branch_code_column.strip()
        return columns

    @staticmethod
    def _filter_branch(mapping: EmployeeMapping, rows: list[dict]) -> list[dict]:
        """
        اگر ستون و مقدار شعبه (مثل Employee.BranchCode) برای این سایت تنظیم شده باشد،
        فقط ردیف‌های همان شعبه را نگه می‌دارد؛ پرسنل موجودِ شعبه‌های دیگر در این اجرا
        «در منبع دیده نمی‌شوند» و غیرفعال می‌شوند. بدون تنظیم شعبه، همه ردیف‌ها برمی‌گردند.
        """
        column = (mapping.branch_code_column or "").strip()
        value = (mapping.branch_code_value or "").strip()
        if not column or not value:
            return rows
        return [row for row in rows if row.get(column) is not None and str(row.get(column)).strip() == value]

    @staticmethod
    def root_codes(mapping: EmployeeMapping | None) -> set[str]:
        """کدهای واحد ریشه‌ی نگاشت را نرمال‌شده برمی‌گرداند (مقادیر خالی حذف)؛ نگاشت بدون ریشه → مجموعه خالی."""
        if mapping is None:
            return set()
        return {code for code in (normalize_code(v) for v in (mapping.root_department_codes or [])) if code}

    @staticmethod
    def same_source(a: SiteConnection, b: SiteConnection) -> bool:
        """آیا دو اتصال به یک دیتابیس منبع اشاره می‌کنند؟ (نوع، میزبان، پورت و نام دیتابیس یکسان؛ بدون حساسیت به حروف)"""
        return (
            a.db_type == b.db_type
            and (a.host or "").strip().lower() == (b.host or "").strip().lower()
            and a.port == b.port
            and (a.database_name or "").strip().lower() == (b.database_name or "").strip().lower()
        )

    async def sibling_roots(self, site_id: int, conn: SiteConnection) -> dict[int, set[str]]:
        """
        ریشه‌های همه‌ی سایت‌های دیگری را برمی‌گرداند که به همین دیتابیس منبع وصل‌اند و ریشه تعریف کرده‌اند.
        خروجی: «شناسه سایت → مجموعه کد ریشه‌ها». سایت‌های غیرفعال هم حساب می‌شوند تا واحدهایشان به سایت دیگری نیفتد.
        """
        result = await self.db.execute(
            select(SiteConnection, EmployeeMapping)
            .join(EmployeeMapping, EmployeeMapping.site_id == SiteConnection.site_id)
            .where(SiteConnection.site_id != site_id)
        )
        roots: dict[int, set[str]] = {}
        for other_conn, other_mapping in result.all():
            codes = self.root_codes(other_mapping)
            if codes and self.same_source(conn, other_conn):
                roots[other_conn.site_id] = codes
        return roots

    async def load_parent_map(self, adapter, mapping: EmployeeMapping) -> dict[str, str | None]:
        """جدول واحدهای منبع را با ستون کد و ستون بالادست می‌خواند و نقشه‌ی «کد → بالادست» برمی‌گرداند."""
        rows = await adapter.fetch_rows(
            mapping.department_lookup_table,
            list(dict.fromkeys([mapping.department_lookup_id_column, mapping.department_lookup_parent_column])),
        )
        return build_parent_map(rows, mapping.department_lookup_id_column, mapping.department_lookup_parent_column)

    @staticmethod
    def org_filter_missing_fields(mapping: EmployeeMapping) -> list[str]:
        """فیلدهای نگاشتی که فیلتر واحد ریشه به آن‌ها نیاز دارد و خالی‌اند (برچسب فارسی)."""
        required = {
            "ستون واحد در جدول پرسنل": mapping.department_column,
            "جدول واحدها": mapping.department_lookup_table,
            "ستون کد واحد": mapping.department_lookup_id_column,
            "ستون واحد بالادست": mapping.department_lookup_parent_column,
        }
        return [label for label, value in required.items() if not (value or "").strip()]

    async def _resolve_org_scope(
        self, site_id: int, conn: SiteConnection, mapping: EmployeeMapping, adapter
    ) -> tuple[dict[str, int | None], set[int]] | None:
        """
        اگر این سایت واحد ریشه دارد، درخت واحدهای منبع را می‌خواند و هر واحد را به سایتش نسبت می‌دهد.
        خروجی: (نقشه «کد واحد → شناسه سایت یا None»، مجموعه سایت‌های هم‌منبع دیگر)؛ بدون ریشه → None.
        نگاشت ناقص یا ریشه‌ی مشترک بین دو سایت SyncError می‌دهد تا Sync با داده‌ی اشتباه اجرا نشود.
        """
        own_roots = self.root_codes(mapping)
        if not own_roots:
            return None
        missing = self.org_filter_missing_fields(mapping)
        if missing:
            raise SyncError("برای فیلتر واحد ریشه این فیلدهای نگاشت پرسنل باید پر شوند: " + "، ".join(missing))
        roots_by_site = await self.sibling_roots(site_id, conn)
        roots_by_site[site_id] = own_roots
        parents = await self.load_parent_map(adapter, mapping)
        try:
            assignment = assign_units_to_sites(parents, roots_by_site)
        except OrgTreeError as e:
            raise SyncError(str(e)) from e
        return assignment, set(roots_by_site) - {site_id}

    async def _protected_codes(
        self, site_id: int, owned_elsewhere: dict[str, int], unassigned_codes: set[str]
    ) -> tuple[set[str], int]:
        """
        کدهای پرسنلی‌ای را که رکوردشان در این سایت نباید غیرفعال شود مشخص می‌کند:
        - بی‌سایت‌ها همیشه (تا تنظیم ریشه‌ها، رکورد فعلی‌شان دست نمی‌خورد)؛
        - متعلق به سایت دیگر فقط تا وقتی آن سایت هنوز رکوردی برایشان ندارد (منتظر انتقال)؛
          اگر آن سایت رکورد دارد، نسخه‌ی این سایت تکراری است و غیرفعال می‌شود.
        خروجی: (مجموعه کدهای محافظت‌شده، تعداد رکوردهای این سایت که منتظر انتقال‌اند).
        """
        protected = set(unassigned_codes)
        if not owned_elsewhere:
            return protected, 0
        # کدهایی که سایت مالکشان هنوز رکوردی ندارد
        result = await self.db.execute(
            select(Employee.personnel_code, Employee.site_id).where(
                Employee.personnel_code.in_(owned_elsewhere.keys()),
                Employee.site_id.in_(set(owned_elsewhere.values())),
            )
        )
        present = {(code, sid) for code, sid in result.all()}
        waiting = {code for code, owner in owned_elsewhere.items() if (code, owner) not in present}
        protected |= waiting
        if not waiting:
            return protected, 0
        # چند نفر از این منتظران هنوز رکورد فعال در همین سایت دارند (برای هشدار)
        here = await self.db.execute(
            select(Employee.personnel_code).where(
                Employee.site_id == site_id,
                Employee.personnel_code.in_(waiting),
                Employee.is_active.is_(True),
            )
        )
        return protected, len(here.all())

    @staticmethod
    def _split_rows_by_org(
        site_id: int,
        columns: dict[str, str],
        rows: list[dict],
        assignment: dict[str, int | None],
        department_lookup: dict[str, str],
    ) -> tuple[list[dict], dict[str, int], set[str], int, str | None]:
        """
        ردیف‌های پرسنل را بر اساس سایتِ واحدشان جدا می‌کند.
        خروجی: (ردیف‌های این سایت، «کد پرسنلی → سایت مالک» برای پرسنل سایت‌های دیگر، کدهای پرسنل بی‌سایت،
        تعداد پرسنل بی‌سایت، متن هشدار یا None). کد پرسنلی مثل Upsert با str().strip() ساخته می‌شود.
        """
        own_rows: list[dict] = []
        owned_elsewhere: dict[str, int] = {}
        unassigned_codes: set[str] = set()
        unassigned_by_unit: dict[str, int] = {}
        for row in rows:
            raw_code = row.get(columns["personnel_code"])
            code = str(raw_code).strip() if raw_code is not None else ""  # همان قالب کد در _upsert_employees
            unit = normalize_code(row.get(columns["department_raw"]))
            owner = assignment.get(unit) if unit else None
            if owner == site_id:
                own_rows.append(row)
                continue
            if code:
                if owner is None:
                    unassigned_codes.add(code)
                else:
                    owned_elsewhere[code] = owner
            if owner is None:
                key = unit or "—"
                unassigned_by_unit[key] = unassigned_by_unit.get(key, 0) + 1
        skipped = sum(unassigned_by_unit.values())
        warning = None
        if skipped:
            # فهرست واحدهای بی‌سایت با نام و تعداد پرسنل (حداکثر ۲۰ مورد)
            parts = [
                (f"{department_lookup.get(unit, unit)} ({unit}): {count}" if unit != "—" else f"بدون واحد: {count}")
                for unit, count in sorted(unassigned_by_unit.items(), key=lambda kv: -kv[1])[:20]
            ]
            warning = (
                f"{skipped} نفر وارد نشدند چون واحدشان زیر هیچ واحد ریشه‌ای از سایت‌ها نیست: " + "، ".join(parts)
            )
        return own_rows, owned_elsewhere, unassigned_codes, skipped, warning

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

        # کد (strip‌شده) -> نام؛ اگر نام NULL باشد خود کد به‌جای نام استفاده می‌شود
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
        """
        واحد سازمانی متناظر با این کد را پیدا می‌کند، یا اگر نبود می‌سازد؛ نام تغییرکرده را هم به‌روز می‌کند.
        خروجی: شناسه واحد. cache برای جلوگیری از Query تکراری در طول یک اجرا است.
        """
        if code in cache:
            return cache[code]

        result = await self.db.execute(
            select(Department).where(Department.site_id == site_id, Department.code == code)
        )
        department = result.scalar_one_or_none()

        if department is None:
            department = Department(site_id=site_id, name=name, code=code)
            self.db.add(department)
            await self.db.flush()  # برای گرفتن department.id
        elif department.name != name:
            # اگر عنوان بخش در منبع (مثلاً ستون Title) تغییر کرده، همگام می‌کنیم
            department.name = name

        cache[code] = department.id
        return department.id

    @staticmethod
    def _coerce_is_active(raw_value) -> bool:
        """مقدار خام ستون is_active منبع را به True/False تبدیل می‌کند (NULL = فعال؛ رشته‌های _FALSY_ACTIVE_VALUES = غیرفعال)."""
        if raw_value is None:
            return True
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, (int, float)):
            return bool(raw_value)
        return str(raw_value).strip().lower() not in _FALSY_ACTIVE_VALUES

    @staticmethod
    def _normalize_jalali_date(raw_value) -> str | None:
        """
        تاریخ شمسی خام (مثل «13700521» یا «1370/5/21») → «1370/05/21» - فرمت
        فرم بیمه تکمیلی. نامعتبر → None (Sync شکست نمی‌خورد).
        """
        if raw_value is None:
            return None
        text = str(raw_value).strip()
        if not text:
            return None
        # جداکردن سال/ماه/روز: با جداکننده یا به‌صورت ۸ رقم چسبیده
        parts: list[str] | None = None
        for sep in ("/", "-", "."):
            if sep in text:
                parts = text.split(sep)
                break
        if parts is None and text.isdigit() and len(text) == 8:
            parts = [text[:4], text[4:6], text[6:8]]
        if not parts or len(parts) != 3:
            return None
        try:
            year, month, day = (int(p) for p in parts)
        except ValueError:
            return None
        if not (1300 <= year <= 1500 and 1 <= month <= 12 and 1 <= day <= 31):
            return None
        return f"{year:04d}/{month:02d}/{day:02d}"

    @staticmethod
    def _normalize_gender(raw_value) -> int | None:
        """جنسیت: ۱=مرد، ۲=زن (کد کاراوب)؛ متن «مرد/زن» یا M/F هم پذیرفته می‌شود."""
        if raw_value is None:
            return None
        text = str(raw_value).strip().lower()
        if text in ("1", "m", "male", "مرد"):
            return 1
        if text in ("2", "f", "female", "زن"):
            return 2
        return None

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

        # فرمت با جداکننده (سال/ماه/روز)
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

        # فرمت ۸ رقمی چسبیده (YYYYMMDD)
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
        مقدار خام فیلدهای طول‌ثابت مثل کد ملی (۱۰ رقم) و موبایل (۱۱ رقم) را به رشته ارقام لاتین
        با طول length تبدیل می‌کند. اگر ستون مبدأ عددی باشد، درایور int/float برمی‌گرداند و صفرهای
        ابتدایی (مثلاً کد ملی ۰۰۱۲۳۴۵۶۷۸) از بین می‌روند؛ این تابع آن‌ها را با zfill بازمی‌گرداند تا
        ورود با کد ملی (رمز پیش‌فرض) درست کار کند. خروجی: رشته نرمال‌شده یا None.
        """
        if raw_value is None:
            return None
        if isinstance(raw_value, float):
            raw_value = int(raw_value)  # حذف «.0» مقدار عددی
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
        transfer_from_site_ids: set[int] | None = None,
    ) -> tuple[int, int, int, set[str], int]:
        """
        ردیف‌های خام منبع را به رکوردهای Employee این سایت تبدیل و Insert/Update می‌کند.
        transfer_from_site_ids: سایت‌های هم‌منبعی که اگر پرسنلِ این سایت هنوز آنجا رکورد دارد، همان رکورد منتقل شود.
        خروجی: (تعداد درج، تعداد به‌روزرسانی، تعداد ردشده به‌خاطر غیرفعال بودن، مجموعه کدهای پرسنلی دیده‌شده، تعداد انتقال).
        """
        inserted = 0
        updated = 0
        skipped_inactive = 0
        transferred = 0
        seen_codes: set[str] = set()
        now = datetime.now(timezone.utc)
        has_department_mapping = "department_raw" in columns
        department_cache: dict[str, int] = {}

        # پیش‌بارگذاری پرسنل موجود این Site تا در حلقه Query تکراری نزنیم
        result = await self.db.execute(select(Employee).where(Employee.site_id == site_id))
        existing_by_code = {emp.personnel_code: emp for emp in result.scalars().all()}

        # پرسنلِ این سایت که هنوز در یک سایت هم‌منبع دیگر رکورد دارند (نامزد انتقال)
        transfer_candidates: dict[str, Employee] = {}
        if transfer_from_site_ids:
            new_codes = {
                str(row.get(columns["personnel_code"])).strip()
                for row in raw_rows
                if row.get(columns["personnel_code"]) is not None
            } - set(existing_by_code)
            if new_codes:
                cand_result = await self.db.execute(
                    select(Employee).where(
                        Employee.site_id.in_(transfer_from_site_ids),
                        Employee.personnel_code.in_(new_codes),
                        Employee.is_manually_created.is_(False),
                    )
                )
                for emp in cand_result.scalars().all():
                    # اگر در چند سایت رکورد داشت، رکورد فعال ترجیح دارد
                    current = transfer_candidates.get(emp.personnel_code)
                    if current is None or (emp.is_active and not current.is_active):
                        transfer_candidates[emp.personnel_code] = emp

        # پردازش هر ردیف منبع
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

            email = None
            if "email" in columns:
                raw_email = row.get(columns["email"])
                # فقط Trim و خالی→None - برخلاف موبایل/کدملی، ایمیل طول ثابت ندارد
                email = str(raw_email).strip() if raw_email not in (None, "") else None
                if not email:
                    email = None

            # تاریخ تولد (روز/ماه + تاریخ کامل)، تاریخ استخدام و جنسیت
            birth_month = birth_day = None
            birth_date_jalali = None
            if "birth_date_raw" in columns:
                parsed_birth = self._parse_birth_month_day(row.get(columns["birth_date_raw"]))
                if parsed_birth is not None:
                    birth_month, birth_day = parsed_birth
                birth_date_jalali = self._normalize_jalali_date(row.get(columns["birth_date_raw"]))
            hire_date_jalali = (
                self._normalize_jalali_date(row.get(columns["hire_date_raw"])) if "hire_date_raw" in columns else None
            )
            gender = self._normalize_gender(row.get(columns["gender_raw"])) if "gender_raw" in columns else None

            # سمت: ترجمه کد با جدول Lookup (در نبود، خود کد)
            position_title = None
            if "position_raw" in columns:
                raw_position = row.get(columns["position_raw"])
                position_code = str(raw_position).strip() if raw_position not in (None, "") else None
                if position_code:
                    position_title = position_lookup.get(position_code, position_code)

            # وضعیت فعال بودن در منبع (بدون ستون وضعیت: فعال)
            if "is_active_raw" in columns:
                is_active = self._coerce_is_active(row.get(columns["is_active_raw"]))
                if is_active_inverted:
                    # مثل ستون IsCut: ۱=غیرفعال، ۰=فعال — برعکس فرض پیش‌فرض
                    is_active = not is_active
            else:
                is_active = True

            # واحد سازمانی: پیدا/ساخت واحد متناظر با کد بخش
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

            # انتقال رکورد از سایت هم‌منبع دیگر (حساب کاربری و سوابق همراه رکورد می‌آیند)
            if existing is None and personnel_code in transfer_candidates:
                existing = transfer_candidates.pop(personnel_code)
                await self._record_transfer(existing, site_id, now)
                existing_by_code[personnel_code] = existing
                transferred += 1

            if existing is None and not is_active:
                # پرسنل جدیدی که در منبع غیرفعال/کات است اصلاً Import نمی‌شود. پرسنل موجودی که
                # کات شده رکورد و سوابقش حفظ می‌شود و فقط is_active=False می‌گیرد (شاخه Update پایین).
                skipped_inactive += 1
                continue

            # درج پرسنل جدید
            if existing is None:
                self.db.add(
                    Employee(
                        personnel_code=personnel_code,
                        national_code=national_code,
                        first_name=first_name,
                        last_name=last_name,
                        mobile=mobile,
                        email=email,
                        site_id=site_id,
                        department_id=department_id,
                        is_active=is_active,
                        birth_month=birth_month,
                        birth_day=birth_day,
                        birth_date_jalali=birth_date_jalali,
                        hire_date_jalali=hire_date_jalali,
                        gender=gender,
                        position_title=position_title,
                        # is_enabled عمداً اینجا تنظیم نمی‌شود — مقدار پیش‌فرض
                        # ستون (True) اعمال می‌شود؛ این فیلد فقط دستی از پنل تغییر می‌کند.
                        last_synced_at=now,
                    )
                )
                inserted += 1
            # به‌روزرسانی پرسنل موجود؛ فیلدهای اختیاری فقط اگر نگاشت/مقدار داشته باشند بازنویسی می‌شوند
            else:
                existing.first_name = first_name
                existing.last_name = last_name
                if national_code is not None:
                    existing.national_code = national_code
                if mobile is not None:
                    existing.mobile = mobile
                if email is not None:
                    existing.email = email
                if "birth_date_raw" in columns:
                    existing.birth_month = birth_month
                    existing.birth_day = birth_day
                    existing.birth_date_jalali = birth_date_jalali
                if "hire_date_raw" in columns:
                    existing.hire_date_jalali = hire_date_jalali
                if "gender_raw" in columns:
                    existing.gender = gender
                if "position_raw" in columns:
                    existing.position_title = position_title
                if has_department_mapping:
                    existing.department_id = department_id
                existing.is_active = is_active
                # is_enabled عمداً اینجا دست‌کاری نمی‌شود. آن یک
                # تصمیم دستی Admin است (از پنل «پرسنل») و باید مستقل از نتیجه
                # هر اجرای Sync باقی بماند.
                existing.last_synced_at = now
                updated += 1

        await self.db.flush()
        return inserted, updated, skipped_inactive, seen_codes, transferred

    async def _record_transfer(self, employee: Employee, to_site_id: int, now: datetime) -> None:
        """
        رکورد پرسنل را به سایت مقصد منتقل و یک SiteTransfer برای بازبینی نقش‌های سایت قبلی ثبت می‌کند.
        واحد پرسنل در ادامه‌ی همان Sync با واحد سایت مقصد به‌روز می‌شود.
        """
        from_site_id = employee.site_id
        user_result = await self.db.execute(select(User.id).where(User.employee_id == employee.id).limit(1))
        user_id = user_result.scalar_one_or_none()
        employee.site_id = to_site_id
        employee.department_id = None  # واحد سایت قبلی نباید بماند؛ در ادامه واحد سایت مقصد تنظیم می‌شود
        self.db.add(
            SiteTransfer(
                employee_id=employee.id,
                personnel_code=employee.personnel_code,
                from_site_id=from_site_id,
                to_site_id=to_site_id,
                user_id=user_id,
                transferred_at=now,
            )
        )
        await self.db.flush()
        logger.info(
            "پرسنل %s از سایت %s به سایت %s منتقل شد", employee.personnel_code, from_site_id, to_site_id
        )

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

        # کد پرسنلی -> بایت‌های تصویر (ردیف‌های بدون کد یا بدون تصویر نادیده گرفته می‌شوند)
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

        # اعمال تصویر روی پرسنل همین سایت که در منبع عکس دارند
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
        """
        پرسنل فعال این سایت که در این اجرا در منبع دیده نشدند (seen_codes) را غیرفعال می‌کند (بدون حذف).
        پرسنل افزوده‌شده دستی (is_manually_created) مستثنا هستند، چون هرگز در منبع وجود ندارند.
        خروجی: تعداد پرسنل غیرفعال‌شده.
        """
        result = await self.db.execute(
            select(Employee).where(
                Employee.site_id == site_id,
                Employee.is_active.is_(True),
                Employee.is_manually_created.is_(False),
            )
        )
        count = 0
        for emp in result.scalars().all():
            if emp.personnel_code not in seen_codes:
                emp.is_active = False
                count += 1
        await self.db.flush()
        return count
