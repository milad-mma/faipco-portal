"""
سرویس ماژول «بیمه تکمیلی».

این سرویس تمام عملیات دیتابیسی ماژول را انجام می‌دهد:
- خواندن/ذخیره تنظیمات ماژول (فعال/غیرفعال، جدول نرخ، نکات) در جدول system_settings
- ساخت نمای اطلاعات پرسنلی و وضعیت ثبت‌نام هر فرد
- آپلود، دانلود و حذف مدارک کفالت (فایل‌ها به‌صورت bytea در دیتابیس پرتال)
- ثبت/ویرایش فرم ثبت‌نام (اعتبارسنجی با core/insurance_rules و جایگزینی کامل اعضا)
- فهرست، جزئیات و خروجی Excel برای مدیران
- پاک‌سازی مدارک آپلودشده‌ای که هرگز به فرم نهایی متصل نشده‌اند
"""
from __future__ import annotations

import io
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import insurance_rules as rules
from app.models.employee import Department, Employee
from app.models.insurance import InsuranceDocument, InsuranceMember, InsuranceRegistration
from app.models.notice import Notice, NoticePriority, NoticeStatus, NoticeTarget, NoticeTargetType, NoticeType
from app.models.site import Site
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.schemas.insurance import (
    InsuranceEmployeeOut,
    InsuranceListItemOut,
    InsuranceListOut,
    InsuranceRegistrationIn,
)

logger = logging.getLogger(__name__)

# کلید رکورد تنظیمات ماژول در جدول system_settings؛ مقدار آن JSON با کلیدهای
# enabled / rate_table / notes است.
SETTINGS_KEY = "insurance_settings"

# مدرکی که قبل از ثبت نهایی فرم آپلود می‌شود به یک عضو موقت با
# member_type="pending" وصل می‌شود. اگر این عضو موقت بیش از این تعداد ساعت
# بماند (یعنی فرم هرگز ثبت نشده)، زمان‌بند آن را همراه مدرکش پاک می‌کند.
PENDING_MAX_AGE_HOURS = 24

# اطلاعیه‌ی رد مدرک: متن پیش‌فرض (قابل ویرایش در تنظیمات)؛ «{نام عضو}» با نام و نام خانوادگی عضو جایگزین می‌شود
MEMBER_NAME_PLACEHOLDER = "{نام عضو}"
DEFAULT_REJECT_NOTICE_TITLE = "مدرک بیمه تکمیلی تأیید نشد"
DEFAULT_REJECT_NOTICE_BODY = (
    "مدرک ارائه‌شده برای {نام عضو} مورد تأیید نیست. "
    "لطفاً جهت پیگیری علت رد مدارک به واحد منابع انسانی مراجعه نمائید."
)
REJECT_TITLE_MAX = 255
REJECT_BODY_MAX = 2000


class InsuranceError(Exception):
    """خطای قابل نمایش به کاربر (پیام فارسی در متن استثنا)."""


class InsuranceDisabledError(InsuranceError):
    """وقتی ماژول از پنل غیرفعال شده و عملیات ثبت/آپلود مجاز نیست."""


class InsuranceService:
    """عملیات ماژول بیمه تکمیلی روی یک نشست دیتابیس (AsyncSession)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- تنظیمات ----------

    async def get_settings(self) -> dict:
        """
        تنظیمات ماژول را از system_settings می‌خواند.
        خروجی همیشه سه کلید enabled / rate_table / notes دارد؛ اگر رکوردی نباشد
        یا JSON آن خراب/ناقص باشد، مقدارهای پیش‌فرض insurance_rules برمی‌گردد.
        """
        row = await self.db.get(SystemSetting, SETTINGS_KEY)
        stored: dict = {}
        if row is not None:
            try:
                stored = json.loads(row.value) or {}
            except (ValueError, TypeError):
                stored = {}  # مقدار خراب در دیتابیس → مثل نبودن رکورد رفتار می‌شود
        return {
            "enabled": bool(stored.get("enabled", True)),
            "rate_table": self._sanitize_rate_table(stored.get("rate_table")) or rules.DEFAULT_RATE_TABLE,
            "notes": self._sanitize_notes(stored.get("notes")) or list(rules.DEFAULT_NOTES),
            "reject_notice_title": (str(stored.get("reject_notice_title") or "").strip() or DEFAULT_REJECT_NOTICE_TITLE)[:REJECT_TITLE_MAX],
            "reject_notice_body": (str(stored.get("reject_notice_body") or "").strip() or DEFAULT_REJECT_NOTICE_BODY)[:REJECT_BODY_MAX],
        }

    async def update_settings(self, patch: dict) -> dict:
        """
        بخشی از تنظیمات را تغییر می‌دهد و کل تنظیمات جدید را برمی‌گرداند.
        فقط کلیدهایی که در patch مقدار غیر None دارند اعمال می‌شوند؛ جدول نرخ
        نامعتبر باعث خطای InsuranceError می‌شود.
        """
        current = await self.get_settings()
        if "enabled" in patch and patch["enabled"] is not None:
            current["enabled"] = bool(patch["enabled"])
        if patch.get("rate_table") is not None:
            table = self._sanitize_rate_table(patch["rate_table"])
            if table is None:
                raise InsuranceError("جدول نرخ نامعتبر است.")
            current["rate_table"] = table
        if patch.get("notes") is not None:
            current["notes"] = self._sanitize_notes(patch["notes"]) or []
        # متن خالی = برگشت به متن پیش‌فرض
        if patch.get("reject_notice_title") is not None:
            current["reject_notice_title"] = str(patch["reject_notice_title"]).strip()[:REJECT_TITLE_MAX] or DEFAULT_REJECT_NOTICE_TITLE
        if patch.get("reject_notice_body") is not None:
            current["reject_notice_body"] = str(patch["reject_notice_body"]).strip()[:REJECT_BODY_MAX] or DEFAULT_REJECT_NOTICE_BODY
        # ذخیره: رکورد موجود به‌روز می‌شود، وگرنه رکورد جدید ساخته می‌شود
        row = await self.db.get(SystemSetting, SETTINGS_KEY)
        if row is None:
            self.db.add(SystemSetting(key=SETTINGS_KEY, value=json.dumps(current, ensure_ascii=False)))
        else:
            row.value = json.dumps(current, ensure_ascii=False)
        await self.db.commit()
        return current

    @staticmethod
    def _sanitize_rate_table(value) -> dict | None:
        """
        ساختار جدول نرخ ورودی را پاک‌سازی می‌کند و نسخه‌ی امن آن را برمی‌گرداند.
        سطرهای بدون برچسب سن یا با مبلغ غیرعددی حذف می‌شوند، متن‌ها کوتاه می‌شوند
        و حداکثر ۵۰ سطر نگه داشته می‌شود. اگر ساختار یا همه‌ی سطرها نامعتبر باشند
        None برمی‌گردد.
        """
        if not isinstance(value, dict):
            return None
        rows_in = value.get("rows")
        if not isinstance(rows_in, list):
            return None
        rows = []
        for r in rows_in[:50]:
            if not isinstance(r, dict):
                continue
            label = str(r.get("age_label") or "").strip()[:60]
            try:
                non_dep = int(r.get("non_dependent") or 0)
                dep = int(r.get("dependent") or 0)
            except (TypeError, ValueError):
                continue  # مبلغ غیرعددی → این سطر نادیده گرفته می‌شود
            if label:
                rows.append({"age_label": label, "non_dependent": max(0, non_dep), "dependent": max(0, dep)})
        if not rows:
            return None
        # عنوان ستون‌ها و واحد پول با مقدار پیش‌فرض در صورت خالی بودن
        return {
            "unit": str(value.get("unit") or "تومان").strip()[:20],
            "age_header": str(value.get("age_header") or "سن").strip()[:40],
            "non_dependent_header": str(value.get("non_dependent_header") or "غیر تحت تکفل").strip()[:40],
            "dependent_header": str(value.get("dependent_header") or "تحت تکفل").strip()[:40],
            "rows": rows,
        }

    @staticmethod
    def _sanitize_notes(value) -> list[str] | None:
        """
        فهرست نکات (کادر آبی) را پاک‌سازی می‌کند: هر مورد به رشته‌ی حداکثر ۵۰۰
        کاراکتری تبدیل می‌شود، موارد خالی حذف می‌شوند و حداکثر ۳۰ مورد می‌ماند.
        متن ساده است؛ نشانه‌های **پررنگ** و __زیرخط__ در فرانت رندر می‌شوند.
        """
        if not isinstance(value, list):
            return None
        return [str(n).strip()[:500] for n in value[:30] if str(n).strip()]

    # ---------- وضعیت شخصی ----------

    @staticmethod
    def employee_view(employee: Employee) -> InsuranceEmployeeOut:
        """
        از رکورد پرسنل، اطلاعات لازم برای فرم بیمه را می‌سازد.
        کد ملی و موبایل نرمال می‌شوند (ارقام فارسی → انگلیسی) و فهرست missing
        نام فیلدهایی را دارد که در پرتال خالی‌اند و بدون آن‌ها ثبت‌نام ممکن نیست.
        """
        missing = []
        if not employee.national_code:
            missing.append("کد ملی")
        if not employee.birth_date_jalali:
            missing.append("تاریخ تولد")
        if not employee.hire_date_jalali:
            missing.append("تاریخ استخدام")
        if employee.gender not in (rules.GENDER_MALE, rules.GENDER_FEMALE):
            missing.append("جنسیت")
        return InsuranceEmployeeOut(
            personnel_code=employee.personnel_code,
            first_name=employee.first_name,
            last_name=employee.last_name,
            national_id=rules.normalize_national_id(employee.national_code) if employee.national_code else None,
            mobile=rules.normalize_mobile(employee.mobile) if employee.mobile else None,
            birth_date=employee.birth_date_jalali,
            employment_date=employee.hire_date_jalali,
            gender=employee.gender,
            missing=missing,
        )

    async def get_registration(self, employee_id: int) -> InsuranceRegistration | None:
        """ثبت‌نام یک پرسنل را همراه اعضا و مدرک هر عضو می‌خواند؛ اگر نباشد None."""
        result = await self.db.execute(
            select(InsuranceRegistration)
            .options(selectinload(InsuranceRegistration.members).selectinload(InsuranceMember.document))
            .where(InsuranceRegistration.employee_id == employee_id)
            # جلسه expire_on_commit=False دارد؛ بدون populate_existing، بعد از ذخیره
            # فهرست اعضای قبلی (حذف‌شده) از identity map برمی‌گشت و تغییرات تا رفرش دیده نمی‌شد
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def my_status(self, employee: Employee | None) -> dict:
        """
        داده‌ی کامل صفحه‌ی بیمه برای کاربر جاری را می‌سازد: وضعیت فعال بودن،
        اطلاعات پرسنلی، ثبت‌نام قبلی (اگر باشد)، جدول نرخ، نکات و فهرست‌های ثابت
        (بانک‌ها، انواع حساب، انواع عضو). اگر کاربر به پرسنلی وصل نباشد
        employee و registration خالی برمی‌گردند.
        """
        settings = await self.get_settings()
        registration = await self.get_registration(employee.id) if employee else None
        return {
            "enabled": settings["enabled"],
            "employee": self.employee_view(employee) if employee else None,
            "registration": registration,
            "rate_table": settings["rate_table"],
            "notes": settings["notes"],
            "bank_codes": rules.BANK_CODES,
            "account_types": rules.ACCOUNT_TYPES,
            # کلید gender هر نوع عضو فقط برای اعتبارسنجی سرور است و به کلاینت نمی‌رود
            "member_types": {k: {kk: vv for kk, vv in v.items() if kk != "gender"} for k, v in rules.MEMBER_TYPES.items()},
        }

    # ---------- مدارک ----------

    async def upload_document(
        self, employee: Employee, file_name: str, content_type: str, content: bytes
    ) -> InsuranceDocument:
        """
        یک فایل مدرک را برای پرسنل ذخیره می‌کند و رکورد مدرک را برمی‌گرداند.
        ورودی: پرسنل، نام فایل، نوع اعلام‌شده توسط کلاینت (استفاده نمی‌شود) و بایت‌ها.
        فایل به یک عضو موقت (pending) در ثبت‌نام همین پرسنل وصل می‌شود تا هنگام
        ثبت نهایی فرم به عضو واقعی منتقل شود.
        """
        if not await self._is_enabled():
            raise InsuranceDisabledError("ثبت‌نام بیمه تکمیلی در حال حاضر غیرفعال است.")
        if len(content) > rules.DOCUMENT_MAX_BYTES:
            raise InsuranceError("حجم فایل نباید بیشتر از ۱۰ مگابایت باشد.")
        # نوع فایل از امضای بایت‌های ابتدایی تشخیص داده می‌شود، نه از پسوند یا Content-Type
        detected = _sniff_content_type(content)
        if detected not in rules.DOCUMENT_ALLOWED_TYPES:
            raise InsuranceError("فقط فایل تصویری (JPG/PNG/GIF/WEBP/BMP/TIFF) یا PDF پذیرفته می‌شود.")
        registration = await self._get_or_create_shell(employee)
        # عضو موقت نگهدارنده‌ی مدرک؛ همه فیلدها خالی و sort_order بزرگ تا آخر لیست بماند
        holder = InsuranceMember(
            registration_id=registration.id,
            member_type="pending",
            relation_code=0,
            dependency_code=0,
            first_name="",
            last_name="",
            father_name="",
            birth_date="",
            gender=0,
            marital_status=0,
            national_id="",
            birth_certificate_no="",
            mobile_number="",
            kafala_status=None,
            sort_order=9999,
        )
        self.db.add(holder)
        await self.db.flush()  # برای گرفتن holder.id
        # نام فایل بدون جداکننده‌ی مسیر و حداکثر ۲۵۵ کاراکتر
        safe_name = (file_name or "document").replace("/", "_").replace("\\", "_")[:255]
        doc = InsuranceDocument(
            member_id=holder.id, file_name=safe_name, content_type=detected, size_bytes=len(content), data=content
        )
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        return doc

    async def get_document_for_download(self, document_id: int, employee_id: int | None, can_view_all: bool):
        """
        مدرک را برای دانلود برمی‌گرداند اگر درخواست‌کننده مجاز باشد.
        مجاز = صاحب مدرک (employee_id همان پرسنل ثبت‌نام) یا can_view_all=True
        (مجوز insurance.view). در غیر این صورت یا اگر مدرک نباشد None.
        """
        result = await self.db.execute(
            select(InsuranceDocument, InsuranceRegistration.employee_id)
            .join(InsuranceMember, InsuranceMember.id == InsuranceDocument.member_id)
            .join(InsuranceRegistration, InsuranceRegistration.id == InsuranceMember.registration_id)
            .where(InsuranceDocument.id == document_id)
        )
        row = result.first()
        if row is None:
            return None
        doc, owner_employee_id = row
        if not can_view_all and owner_employee_id != employee_id:
            return None
        return doc

    async def delete_own_document(self, document_id: int, employee_id: int) -> bool:
        """
        مدرک متعلق به پرسنل را حذف می‌کند. اگر مدرک به عضو موقت وصل بود، آن عضو
        هم پاک می‌شود. خروجی True یعنی حذف شد، False یعنی مدرک پیدا نشد یا مال
        این پرسنل نبود.
        """
        doc = await self.get_document_for_download(document_id, employee_id, can_view_all=False)
        if doc is None:
            return False
        member = await self.db.get(InsuranceMember, doc.member_id)
        await self.db.delete(doc)
        if member is not None and member.member_type == "pending":
            await self.db.delete(member)
        await self.db.commit()
        return True

    # ---------- ثبت / ویرایش ----------

    async def save(self, employee: Employee, payload: InsuranceRegistrationIn) -> InsuranceRegistration:
        """
        فرم ثبت‌نام را اعتبارسنجی و ذخیره می‌کند و ثبت‌نام نهایی را برمی‌گرداند.
        ثبت مجدد یعنی ویرایش: اطلاعات شخص اصلی به‌روز می‌شود و همه‌ی اعضای
        قبلی با اعضای فرم جدید جایگزین می‌شوند. مدارکی که در فرم جدید ارجاع
        داده شده‌اند به عضو جدید منتقل می‌شوند؛ بقیه همراه عضو قبلی حذف می‌شوند.
        """
        if not await self._is_enabled():
            raise InsuranceDisabledError("ثبت‌نام بیمه تکمیلی در حال حاضر غیرفعال است.")
        view = self.employee_view(employee)
        if view.missing:
            raise InsuranceError(
                "اطلاعات پرسنلی شما کامل نیست (" + "، ".join(view.missing) + "). لطفاً به واحد منابع انسانی اطلاع دهید."
            )

        # اعتبارسنجی فیلدهای شخص اصلی و اعضا با قواعد ماژول؛ خروجی داده‌ی نرمال‌شده است
        main = rules.validate_main(payload.model_dump(exclude={"members"}), view.national_id or "")
        employee_info = {"gender": view.gender, "first_name": employee.first_name, "last_name": employee.last_name}
        members = rules.validate_members(
            [m.model_dump() for m in payload.members], employee_info, main["marital_status"], main["mobile_number"]
        )

        registration = await self._get_or_create_shell(employee)
        existing_members = {m.id: m for m in registration.members}
        referenced_doc_ids = {m.document_id for m in payload.members if m.document_id}

        # هر مدرک ارجاع‌شده باید متعلق به همین ثبت‌نام باشد (عضو موقت یا عضو قبلی)
        docs_result = await self.db.execute(
            select(InsuranceDocument)
            .join(InsuranceMember, InsuranceMember.id == InsuranceDocument.member_id)
            .where(InsuranceMember.registration_id == registration.id)
        )
        own_docs = {d.id: d for d in docs_result.scalars().all()}
        for doc_id in referenced_doc_ids:
            if doc_id not in own_docs:
                raise InsuranceError("مدرک ارجاع‌شده یافت نشد یا متعلق به شما نیست.")

        # عضوی که کفالتش «بله» است باید مدرک داشته باشد
        for spec, m_in in zip(members, payload.members):
            if spec["kafala_status"] == "yes" and not m_in.document_id:
                cfg = rules.MEMBER_TYPES[spec["member_type"]]
                raise InsuranceError(f"آپلود مدرک کفالت یا حضانت برای {cfg['title']} اجباری است.")

        # فیلدهای هویتی شخص اصلی همیشه از رکورد پرسنل (نه از فرم) نوشته می‌شوند
        registration.personnel_code = employee.personnel_code
        registration.first_name = employee.first_name
        registration.last_name = employee.last_name
        registration.birth_date = view.birth_date or ""
        registration.gender = view.gender or 0
        registration.national_id = view.national_id or ""
        registration.employment_date = view.employment_date or ""
        # بقیه‌ی فیلدهای فرم (تأهل، شماره حساب، ...) از خروجی اعتبارسنجی
        for key, value in main.items():
            setattr(registration, key, value)

        # ساخت اعضای جدید و انتقال مدرک ارجاع‌شده به عضو جدید
        new_members: list[InsuranceMember] = []
        for spec, m_in in zip(members, payload.members):
            spec.pop("client_key", None)  # شناسه‌ی سمت کلاینت؛ ستون دیتابیس نیست
            member = InsuranceMember(registration_id=registration.id, **spec)
            self.db.add(member)
            await self.db.flush()  # برای گرفتن member.id
            if m_in.document_id and spec["kafala_status"] == "yes":
                doc = own_docs[m_in.document_id]
                doc.member_id = member.id
            new_members.append(member)
        await self.db.flush()

        # حذف اعضای قبلی و عضوهای موقت با DELETE مستقیم: cascade دیتابیس فقط
        # مدارکی را پاک می‌کند که هنوز به عضو قدیمی وصل‌اند؛ مدارک منتقل‌شده می‌مانند
        if existing_members:
            await self.db.execute(delete(InsuranceMember).where(InsuranceMember.id.in_(list(existing_members))))
        await self.db.commit()
        return await self.get_registration(employee.id)

    async def delete_registration(self, employee_id: int) -> bool:
        """ثبت‌نام پرسنل را همراه اعضا و مدارک (cascade) حذف می‌کند؛ False اگر نبود."""
        registration = await self.get_registration(employee_id)
        if registration is None:
            return False
        await self.db.delete(registration)
        await self.db.commit()
        return True

    # ---------- مدیریت ----------

    async def list_registrations(
        self,
        site_ids: set[int] | None,
        search: str | None,
        page: int,
        page_size: int,
        member_filter: str | None = None,
    ) -> InsuranceListOut:
        """
        فهرست صفحه‌بندی‌شده‌ی ثبت‌نام‌ها برای صفحه‌ی مدیریت.
        ورودی: مجموعه سایت‌های مجاز (None = همه)، عبارت جستجو، شماره و اندازه صفحه و فیلتر اعضا
        (non_dependent = دارای عضو غیر تحت کفالت، with_documents = دارای مدرک، rejected = دارای مدرک ردشده).
        خروجی: آیتم‌ها + total (با جستجو) + registered (کل ثبت‌نام‌ها) +
        eligible (پرسنل فعال) برای نمایش آمار.
        """
        # کوئری اصلی: ثبت‌نام + پرسنل + سایت + واحد
        base = (
            select(InsuranceRegistration, Employee, Site.id, Site.name, Department.name)
            .join(Employee, Employee.id == InsuranceRegistration.employee_id)
            .join(Site, Site.id == Employee.site_id)
            .outerjoin(Department, Department.id == Employee.department_id)
        )
        count_q = select(func.count()).select_from(InsuranceRegistration).join(
            Employee, Employee.id == InsuranceRegistration.employee_id
        )
        eligible_q = select(func.count()).select_from(Employee).where(Employee.is_active.is_(True))
        # محدودیت سایت روی هر سه کوئری اعمال می‌شود
        if site_ids is not None:
            base = base.where(Employee.site_id.in_(site_ids))
            count_q = count_q.where(Employee.site_id.in_(site_ids))
            eligible_q = eligible_q.where(Employee.site_id.in_(site_ids))
        registered = (await self.db.execute(count_q)).scalar_one()
        eligible = (await self.db.execute(eligible_q)).scalar_one()
        # جستجو روی کد پرسنلی، نام، نام خانوادگی و کد ملی
        if search:
            term = f"%{search.strip()}%"
            cond = (
                Employee.personnel_code.ilike(term)
                | Employee.first_name.ilike(term)
                | Employee.last_name.ilike(term)
                | InsuranceRegistration.national_id.ilike(term)
            )
            base = base.where(cond)
            count_q = count_q.where(cond)
        # فیلتر بر اساس وضعیت اعضا (عضو موقت نگهدارنده‌ی مدرک حساب نمی‌شود)
        member_cond = self._member_filter_condition(member_filter)
        if member_cond is not None:
            base = base.where(member_cond)
            count_q = count_q.where(member_cond)
        total = (await self.db.execute(count_q)).scalar_one()
        # جدیدترین ویرایش اول؛ صفحه‌بندی با limit/offset
        base = base.order_by(InsuranceRegistration.updated_at.desc()).limit(page_size).offset((page - 1) * page_size)
        rows = (await self.db.execute(base)).all()
        # تعداد اعضا و مدارک هر ثبت‌نامِ همین صفحه با دو کوئری گروهی (عضو موقت شمرده نمی‌شود)
        reg_ids = [r[0].id for r in rows]
        members_count: dict[int, int] = {}
        docs_count: dict[int, int] = {}
        non_dependent_count: dict[int, int] = {}
        rejected_count: dict[int, int] = {}
        if reg_ids:
            # اعضای غیر تحت کفالت و اعضای دارای مدرک ردشده در هر ثبت‌نام
            nd = await self.db.execute(
                select(InsuranceMember.registration_id, func.count())
                .where(InsuranceMember.registration_id.in_(reg_ids), InsuranceMember.kafala_status == "no")
                .group_by(InsuranceMember.registration_id)
            )
            non_dependent_count = {rid: c for rid, c in nd.all()}
            rj = await self.db.execute(
                select(InsuranceMember.registration_id, func.count())
                .where(
                    InsuranceMember.registration_id.in_(reg_ids),
                    InsuranceMember.document_rejected_at.is_not(None),
                )
                .group_by(InsuranceMember.registration_id)
            )
            rejected_count = {rid: c for rid, c in rj.all()}
            mc = await self.db.execute(
                select(InsuranceMember.registration_id, func.count())
                .where(InsuranceMember.registration_id.in_(reg_ids), InsuranceMember.member_type != "pending")
                .group_by(InsuranceMember.registration_id)
            )
            members_count = {rid: c for rid, c in mc.all()}
            dc = await self.db.execute(
                select(InsuranceMember.registration_id, func.count(InsuranceDocument.id))
                .join(InsuranceDocument, InsuranceDocument.member_id == InsuranceMember.id)
                .where(InsuranceMember.registration_id.in_(reg_ids), InsuranceMember.member_type != "pending")
                .group_by(InsuranceMember.registration_id)
            )
            docs_count = {rid: c for rid, c in dc.all()}
        items = [
            InsuranceListItemOut(
                id=reg.id,
                employee_id=emp.id,
                personnel_code=reg.personnel_code,
                first_name=reg.first_name,
                last_name=reg.last_name,
                national_id=reg.national_id,
                mobile_number=reg.mobile_number,
                site_id=site_id,
                site_name=site_name,
                department_name=department_name,
                members_count=members_count.get(reg.id, 0),
                documents_count=docs_count.get(reg.id, 0),
                non_dependent_count=non_dependent_count.get(reg.id, 0),
                rejected_documents_count=rejected_count.get(reg.id, 0),
                created_at=reg.created_at,
                updated_at=reg.updated_at,
            )
            for reg, emp, site_id, site_name, department_name in rows
        ]
        return InsuranceListOut(items=items, total=total, registered=registered, eligible=eligible)

    @staticmethod
    def _member_filter_condition(member_filter: str | None):
        """
        شرط SQL فیلتر فهرست ثبت‌نام‌ها بر اساس اعضا؛ مقدار ناشناخته یا خالی → None (بدون فیلتر).
        non_dependent: حداقل یک عضو «غیر تحت کفالت»؛ with_documents: حداقل یک عضو دارای مدرک؛
        rejected: حداقل یک عضو که مدرکش رد شده است.
        """
        member_exists = (
            select(InsuranceMember.id)
            .where(
                InsuranceMember.registration_id == InsuranceRegistration.id,
                InsuranceMember.member_type != "pending",
            )
        )
        if member_filter == "non_dependent":
            return member_exists.where(InsuranceMember.kafala_status == "no").exists()
        if member_filter == "with_documents":
            return member_exists.where(
                select(InsuranceDocument.id).where(InsuranceDocument.member_id == InsuranceMember.id).exists()
            ).exists()
        if member_filter == "rejected":
            return member_exists.where(InsuranceMember.document_rejected_at.is_not(None)).exists()
        return None

    async def reject_document(
        self,
        registration_id: int,
        member_id: int,
        site_ids: set[int] | None,
        sender: User,
        title: str | None = None,
        body: str | None = None,
    ) -> tuple[str, int] | None:
        """
        مدرک یک عضو را رد می‌کند: فایل حذف، زمان رد روی عضو ثبت و یک اطلاعیه‌ی منتشرشده برای پرسنل
        ثبت‌نام‌کننده ساخته می‌شود. ورودی: شناسه ثبت‌نام و عضو، سایت‌های مجاز مدیر (None = همه) و فرستنده.
        خروجی: (نام عضو، شناسه اطلاعیه) برای ارسال Push؛ ثبت‌نام/عضو ناموجود یا خارج از سایت‌ها → None؛
        عضو بدون مدرک → InsuranceError. title/body: متن ویرایش‌شده در پنجره‌ی رد (خالی = متن تنظیمات)؛
        «{نام عضو}» در هر دو با نام عضو جایگزین می‌شود.
        """
        registration = await self.get_registration_by_id(registration_id, site_ids)
        if registration is None:
            return None
        member = next((m for m in registration.members if m.id == member_id and m.member_type != "pending"), None)
        if member is None:
            return None
        if member.document is None:
            raise InsuranceError("این عضو مدرکی برای رد کردن ندارد.")

        member_name = f"{member.first_name} {member.last_name}".strip()
        settings = await self.get_settings()
        notice_title = ((title or "").strip() or settings["reject_notice_title"]).replace(MEMBER_NAME_PLACEHOLDER, member_name)
        notice_body = ((body or "").strip() or settings["reject_notice_body"]).replace(MEMBER_NAME_PLACEHOLDER, member_name)
        if len(notice_title) > REJECT_TITLE_MAX or len(notice_body) > REJECT_BODY_MAX:
            raise InsuranceError("عنوان یا متن اطلاعیه بیش از حد طولانی است.")
        await self.db.delete(member.document)
        member.document_rejected_at = datetime.now(timezone.utc)

        # اطلاعیه‌ی شخصی برای ثبت‌نام‌کننده (مثل پیام تبریک تولد: هدف فقط همان پرسنل)
        notice = Notice(
            sender_id=sender.id,
            title=notice_title,
            body=notice_body,
            priority=NoticePriority.high,
            status=NoticeStatus.published,
            notice_type=NoticeType.normal,
            publish_at=datetime.now(timezone.utc),
        )
        self.db.add(notice)
        await self.db.flush()  # برای گرفتن notice.id
        self.db.add(
            NoticeTarget(
                notice_id=notice.id, target_type=NoticeTargetType.employee, target_id=registration.employee_id
            )
        )
        await self.db.commit()
        return member_name, notice.id

    async def get_registration_by_id(self, registration_id: int, site_ids: set[int] | None):
        """
        یک ثبت‌نام را با شناسه برای مدیر می‌خواند (همراه اعضا و مدارک).
        اگر site_ids داده شده و پرسنل در آن سایت‌ها نباشد None برمی‌گردد.
        """
        result = await self.db.execute(
            select(InsuranceRegistration, Employee.site_id)
            .options(selectinload(InsuranceRegistration.members).selectinload(InsuranceMember.document))
            .join(Employee, Employee.id == InsuranceRegistration.employee_id)
            .where(InsuranceRegistration.id == registration_id)
        )
        row = result.first()
        if row is None:
            return None
        registration, site_id = row
        if site_ids is not None and site_id not in site_ids:
            return None
        return registration

    async def export_xlsx(self, site_ids: set[int] | None) -> bytes:
        """
        خروجی Excel ثبت‌نام‌ها را می‌سازد و بایت‌های فایل xlsx را برمی‌گرداند.
        هر شخص (بیمه‌شده‌ی اصلی و هر عضو خانواده) یک سطر ۲۹ ستونی است:
        ۷ ستون کد ثابت + ۱۲ ستون مشخصات فرد + ۱۰ ستون حساب/ارجاع به شخص اصلی.
        """
        from openpyxl import Workbook

        q = (
            select(InsuranceRegistration)
            .options(selectinload(InsuranceRegistration.members))
            .join(Employee, Employee.id == InsuranceRegistration.employee_id)
            .order_by(InsuranceRegistration.personnel_code)
        )
        if site_ids is not None:
            q = q.where(Employee.site_id.in_(site_ids))
        registrations = (await self.db.execute(q)).scalars().all()

        wb = Workbook()
        ws = wb.active
        ws.title = "Insurance"
        ws.sheet_view.rightToLeft = True
        headers = [
            "کد گروه", "شماره بیمه پایه", "کد درخواست", "نوع استخدام", "کد بیمه قبلی",
            "ماه‌های پوشش", "کد سازمان", "کد پرسنلی", "نام", "نام خانوادگی", "نام پدر",
            "تاریخ تولد", "جنسیت", "وضعیت تاهل", "کد ملی", "شماره شناسنامه", "شماره تماس",
            "کد نسبت", "کد تکفل", "تاریخ استخدام", "شماره بیمه", "کد بانک", "شماره حساب",
            "شماره شبا", "نوع حساب", "نام صاحب حساب", "کد ملی صاحب حساب",
            "کد پرسنلی اصلی", "کد ملی اصلی",
        ]  # fmt: skip
        ws.append(headers)

        def shared(reg: InsuranceRegistration) -> list[str]:
            """۷ ستون اول: کدهای ثابت بیمه‌گر که برای همه یکسان است."""
            return [
                str(rules.GROUP_CODE), str(rules.BASE_INSURANCE_CODE), str(rules.REQUEST_REASON),
                str(rules.EMPLOYMENT_TYPE), str(rules.PREVIOUS_INSURANCE_CODE), str(rules.COVERAGE_MONTHS),
                str(rules.ORGANIZATION_CODE),
            ]  # fmt: skip

        def tail(reg: InsuranceRegistration) -> list[str]:
            """۱۰ ستون آخر: اطلاعات حساب و ارجاع به شخص اصلی (برای همه اعضای یک ثبت‌نام یکسان)."""
            return [
                reg.employment_date, reg.insurance_no, str(reg.bank_code), reg.account_number, reg.sheba,
                str(reg.account_type), reg.account_owner, reg.account_owner_national_id,
                reg.personnel_code, reg.national_id,
            ]  # fmt: skip

        for reg in registrations:
            # فهرست اشخاص هر ثبت‌نام: اول شخص اصلی، سپس اعضای واقعی (عضو موقت حذف می‌شود)
            people = [
                (reg.personnel_code, reg.first_name, reg.last_name, reg.father_name, reg.birth_date, reg.gender,
                 reg.marital_status, reg.national_id, reg.birth_certificate_no, reg.mobile_number,
                 rules.RELATION_SELF, rules.DEPENDENCY_SELF)
            ]  # fmt: skip
            for m in reg.members:
                if m.member_type == "pending":
                    continue
                people.append(
                    (reg.personnel_code, m.first_name, m.last_name, m.father_name, m.birth_date, m.gender,
                     m.marital_status, m.national_id, m.birth_certificate_no, m.mobile_number,
                     m.relation_code, m.dependency_code)
                )  # fmt: skip
            for p in people:
                (code, fn, ln, father, bdate, gender, marital, nid, cert, mobile, rel, dep) = p
                row = shared(reg) + [
                    code, fn, ln, father, bdate,
                    "مرد" if gender == rules.GENDER_MALE else "زن",
                    "مجرد" if marital == rules.MARITAL_SINGLE else "متاهل",
                    nid, cert, mobile, str(rel), str(dep),
                ] + tail(reg)  # fmt: skip
                ws.append([str(v) for v in row])  # همه‌ی مقادیر رشته تا صفر ابتدایی کدها حفظ شود
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = 16
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()

    # ---------- کمکی ----------

    async def _is_enabled(self) -> bool:
        """True اگر ماژول در تنظیمات فعال باشد."""
        return (await self.get_settings())["enabled"]

    async def _get_or_create_shell(self, employee: Employee) -> InsuranceRegistration:
        """
        ثبت‌نام پرسنل را برمی‌گرداند؛ اگر وجود نداشت یک رکورد خالی (پوسته) با
        اطلاعات هویتی پرسنل می‌سازد. این پوسته قبل از ثبت نهایی فقط برای
        نگه‌داشتن مدارک آپلودشده استفاده می‌شود.
        """
        registration = await self.get_registration(employee.id)
        if registration is not None:
            return registration
        view = self.employee_view(employee)
        registration = InsuranceRegistration(
            employee_id=employee.id,
            personnel_code=employee.personnel_code,
            first_name=employee.first_name,
            last_name=employee.last_name,
            father_name="",
            birth_date=view.birth_date or "",
            gender=view.gender or 0,
            marital_status=0,
            national_id=view.national_id or "",
            birth_certificate_no="",
            mobile_number=view.mobile or "",
            employment_date=view.employment_date or "",
            insurance_no="",
            bank_code=0,
            account_number="",
            sheba="",
            account_type=0,
            account_owner="",
            account_owner_national_id="",
        )
        self.db.add(registration)
        await self.db.flush()
        await self.db.refresh(registration, attribute_names=["members"])  # بارگذاری رابطه‌ی members (خالی)
        return registration

    async def cleanup_pending_documents(self) -> int:
        """
        عضوهای موقت (pending) را که مدرک ندارند یا مدرکشان قدیمی‌تر از
        PENDING_MAX_AGE_HOURS است حذف می‌کند (مدرک با cascade پاک می‌شود).
        توسط زمان‌بند صدا زده می‌شود؛ تعداد حذف‌شده‌ها را برمی‌گرداند.
        """
        cutoff = datetime.now(timezone.utc).timestamp() - PENDING_MAX_AGE_HOURS * 3600
        result = await self.db.execute(
            select(InsuranceMember)
            .options(selectinload(InsuranceMember.document))
            .where(InsuranceMember.member_type == "pending")
        )
        removed = 0
        for member in result.scalars().all():
            doc = member.document
            if doc is None or doc.uploaded_at.timestamp() < cutoff:
                await self.db.delete(member)
                removed += 1
        if removed:
            await self.db.commit()
        return removed


def _sniff_content_type(content: bytes) -> str:
    """
    نوع فایل را از بایت‌های ابتدایی (magic number) تشخیص می‌دهد و MIME آن را
    برمی‌گرداند. برای فرمت‌های ناشناخته "application/octet-stream" برمی‌گردد
    که در فهرست مجاز نیست و آپلود را رد می‌کند.
    """
    head = content[:16]
    if head.startswith(b"%PDF"):
        return "application/pdf"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"BM"):
        return "image/bmp"
    if head.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    return "application/octet-stream"
