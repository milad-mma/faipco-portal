"""
سرویس ماژول «بیمه تکمیلی» - بازسازی سامانه قدیمی داخل پرتال.

منطق فرم و اعتبارسنجی عیناً همان سامانه قدیمی است (core/insurance_rules.py)؛
تفاوت‌ها فقط امنیتی/زیرساختی‌اند:
- هویت فرد از نشست پرتال (نه کد ملی به‌عنوان رمز)
- مدارک در دیتابیس پرتال (bytea) تا در بکاپ/بازیابی بمانند، با بررسی
  MIME واقعی محتوا (نه فقط پسوند) و محدودیت ۱۰ مگابایت
- هر مدرک فقط توسط صاحبش یا دارنده مجوز insurance.view قابل دانلود است
- ثبت مجدد = ویرایش (جایگزینی کامل، مثل سامانه قدیمی) در یک تراکنش
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
from app.models.site import Site
from app.models.system_setting import SystemSetting
from app.schemas.insurance import (
    InsuranceEmployeeOut,
    InsuranceListItemOut,
    InsuranceListOut,
    InsuranceRegistrationIn,
)

logger = logging.getLogger(__name__)

SETTINGS_KEY = "insurance_settings"  # JSON: enabled / rate_table / notes
# مدارک آپلودشده ولی هنوز به عضوی وصل‌نشده (قبل از ثبت نهایی فرم) به همین
# عضو موقت وصل می‌شوند و در ثبت نهایی جابه‌جا می‌شوند؛ مدارک یتیم قدیمی‌تر از
# ۲۴ ساعت پاک می‌شوند.
PENDING_MAX_AGE_HOURS = 24


class InsuranceError(Exception):
    pass


class InsuranceDisabledError(InsuranceError):
    pass


class InsuranceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- تنظیمات ----------

    async def get_settings(self) -> dict:
        row = await self.db.get(SystemSetting, SETTINGS_KEY)
        stored: dict = {}
        if row is not None:
            try:
                stored = json.loads(row.value) or {}
            except (ValueError, TypeError):
                stored = {}
        return {
            "enabled": bool(stored.get("enabled", True)),
            "rate_table": self._sanitize_rate_table(stored.get("rate_table")) or rules.DEFAULT_RATE_TABLE,
            "notes": self._sanitize_notes(stored.get("notes")) or list(rules.DEFAULT_NOTES),
        }

    async def update_settings(self, patch: dict) -> dict:
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
        row = await self.db.get(SystemSetting, SETTINGS_KEY)
        if row is None:
            self.db.add(SystemSetting(key=SETTINGS_KEY, value=json.dumps(current, ensure_ascii=False)))
        else:
            row.value = json.dumps(current, ensure_ascii=False)
        await self.db.commit()
        return current

    @staticmethod
    def _sanitize_rate_table(value) -> dict | None:
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
                continue
            if label:
                rows.append({"age_label": label, "non_dependent": max(0, non_dep), "dependent": max(0, dep)})
        if not rows:
            return None
        return {
            "unit": str(value.get("unit") or "تومان").strip()[:20],
            "age_header": str(value.get("age_header") or "سن").strip()[:40],
            "non_dependent_header": str(value.get("non_dependent_header") or "غیر تحت تکفل").strip()[:40],
            "dependent_header": str(value.get("dependent_header") or "تحت تکفل").strip()[:40],
            "rows": rows,
        }

    @staticmethod
    def _sanitize_notes(value) -> list[str] | None:
        if not isinstance(value, list):
            return None
        # متن ساده؛ **پررنگ** و __زیرخط__ در فرانت رندر می‌شود (بدون HTML)
        return [str(n).strip()[:500] for n in value[:30] if str(n).strip()]

    # ---------- وضعیت شخصی ----------

    @staticmethod
    def employee_view(employee: Employee) -> InsuranceEmployeeOut:
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
        result = await self.db.execute(
            select(InsuranceRegistration)
            .options(selectinload(InsuranceRegistration.members).selectinload(InsuranceMember.document))
            .where(InsuranceRegistration.employee_id == employee_id)
        )
        return result.scalar_one_or_none()

    async def my_status(self, employee: Employee | None) -> dict:
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
            "member_types": {k: {kk: vv for kk, vv in v.items() if kk != "gender"} for k, v in rules.MEMBER_TYPES.items()},
        }

    # ---------- مدارک ----------

    async def upload_document(
        self, employee: Employee, file_name: str, content_type: str, content: bytes
    ) -> InsuranceDocument:
        """
        آپلود مدرک قبل از ثبت نهایی (مثل upload_doc.php). به یک «عضو موقت»
        (member_type=pending) در ثبت‌نام همین پرسنل وصل می‌شود تا در ثبت
        نهایی به عضو واقعی منتقل شود. مالکیت: فقط همین پرسنل.
        """
        if not await self._is_enabled():
            raise InsuranceDisabledError("ثبت‌نام بیمه تکمیلی در حال حاضر غیرفعال است.")
        if len(content) > rules.DOCUMENT_MAX_BYTES:
            raise InsuranceError("حجم فایل نباید بیشتر از ۱۰ مگابایت باشد.")
        detected = _sniff_content_type(content)
        if detected not in rules.DOCUMENT_ALLOWED_TYPES:
            raise InsuranceError("فقط فایل تصویری (JPG/PNG/GIF/WEBP/BMP/TIFF) یا PDF پذیرفته می‌شود.")
        registration = await self._get_or_create_shell(employee)
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
        await self.db.flush()
        safe_name = (file_name or "document").replace("/", "_").replace("\\", "_")[:255]
        doc = InsuranceDocument(
            member_id=holder.id, file_name=safe_name, content_type=detected, size_bytes=len(content), data=content
        )
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        return doc

    async def get_document_for_download(self, document_id: int, employee_id: int | None, can_view_all: bool):
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
        if not await self._is_enabled():
            raise InsuranceDisabledError("ثبت‌نام بیمه تکمیلی در حال حاضر غیرفعال است.")
        view = self.employee_view(employee)
        if view.missing:
            raise InsuranceError(
                "اطلاعات پرسنلی شما کامل نیست (" + "، ".join(view.missing) + "). لطفاً به واحد منابع انسانی اطلاع دهید."
            )

        main = rules.validate_main(payload.model_dump(exclude={"members"}), view.national_id or "")
        employee_info = {"gender": view.gender, "first_name": employee.first_name, "last_name": employee.last_name}
        members = rules.validate_members(
            [m.model_dump() for m in payload.members], employee_info, main["marital_status"], main["mobile_number"]
        )

        registration = await self._get_or_create_shell(employee)
        # همه اعضای قبلی حذف می‌شوند (جایگزینی کامل، مثل سامانه قدیمی)؛ مدارک
        # آپلودشده‌ای که در فرم جدید ارجاع داده شده‌اند نگه داشته می‌شوند.
        existing_members = {m.id: m for m in registration.members}
        referenced_doc_ids = {m.document_id for m in payload.members if m.document_id}

        # مدارک قابل استفاده: مدارک همین ثبت‌نام (pending یا اعضای قبلی)
        docs_result = await self.db.execute(
            select(InsuranceDocument)
            .join(InsuranceMember, InsuranceMember.id == InsuranceDocument.member_id)
            .where(InsuranceMember.registration_id == registration.id)
        )
        own_docs = {d.id: d for d in docs_result.scalars().all()}
        for doc_id in referenced_doc_ids:
            if doc_id not in own_docs:
                raise InsuranceError("مدرک ارجاع‌شده یافت نشد یا متعلق به شما نیست.")

        # مدرک اجباری برای کفالت «بله»
        for spec, m_in in zip(members, payload.members):
            if spec["kafala_status"] == "yes" and not m_in.document_id:
                cfg = rules.MEMBER_TYPES[spec["member_type"]]
                raise InsuranceError(f"آپلود مدرک کفالت یا حضانت برای {cfg['title']} اجباری است.")

        # به‌روزرسانی شخص اصلی
        registration.personnel_code = employee.personnel_code
        registration.first_name = employee.first_name
        registration.last_name = employee.last_name
        registration.birth_date = view.birth_date or ""
        registration.gender = view.gender or 0
        registration.national_id = view.national_id or ""
        registration.employment_date = view.employment_date or ""
        for key, value in main.items():
            setattr(registration, key, value)

        # اعضای جدید
        new_members: list[InsuranceMember] = []
        for spec, m_in in zip(members, payload.members):
            spec.pop("client_key", None)
            member = InsuranceMember(registration_id=registration.id, **spec)
            self.db.add(member)
            await self.db.flush()
            if m_in.document_id and spec["kafala_status"] == "yes":
                doc = own_docs[m_in.document_id]
                doc.member_id = member.id
            new_members.append(member)
        await self.db.flush()

        # حذف اعضای قبلی + عضوهای موقت با DELETE مستقیم (cascade دیتابیس فقط
        # مدارکی را پاک می‌کند که هنوز به عضو قدیمی وصل‌اند؛ مدارک منتقل‌شده می‌مانند)
        if existing_members:
            await self.db.execute(delete(InsuranceMember).where(InsuranceMember.id.in_(list(existing_members))))
        await self.db.commit()
        return await self.get_registration(employee.id)

    async def delete_registration(self, employee_id: int) -> bool:
        registration = await self.get_registration(employee_id)
        if registration is None:
            return False
        await self.db.delete(registration)
        await self.db.commit()
        return True

    # ---------- مدیریت ----------

    async def list_registrations(
        self, site_ids: set[int] | None, search: str | None, page: int, page_size: int
    ) -> InsuranceListOut:
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
        if site_ids is not None:
            base = base.where(Employee.site_id.in_(site_ids))
            count_q = count_q.where(Employee.site_id.in_(site_ids))
            eligible_q = eligible_q.where(Employee.site_id.in_(site_ids))
        registered = (await self.db.execute(count_q)).scalar_one()
        eligible = (await self.db.execute(eligible_q)).scalar_one()
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
        total = (await self.db.execute(count_q)).scalar_one()
        base = base.order_by(InsuranceRegistration.updated_at.desc()).limit(page_size).offset((page - 1) * page_size)
        rows = (await self.db.execute(base)).all()
        reg_ids = [r[0].id for r in rows]
        members_count: dict[int, int] = {}
        docs_count: dict[int, int] = {}
        if reg_ids:
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
                created_at=reg.created_at,
                updated_at=reg.updated_at,
            )
            for reg, emp, site_id, site_name, department_name in rows
        ]
        return InsuranceListOut(items=items, total=total, registered=registered, eligible=eligible)

    async def get_registration_by_id(self, registration_id: int, site_ids: set[int] | None):
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
        """خروجی Excel با همان ۲۹ ستون و ترتیب سامانه قدیمی (admin/export.php)."""
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
            return [
                str(rules.GROUP_CODE), str(rules.BASE_INSURANCE_CODE), str(rules.REQUEST_REASON),
                str(rules.EMPLOYMENT_TYPE), str(rules.PREVIOUS_INSURANCE_CODE), str(rules.COVERAGE_MONTHS),
                str(rules.ORGANIZATION_CODE),
            ]  # fmt: skip

        def tail(reg: InsuranceRegistration) -> list[str]:
            return [
                reg.employment_date, reg.insurance_no, str(reg.bank_code), reg.account_number, reg.sheba,
                str(reg.account_type), reg.account_owner, reg.account_owner_national_id,
                reg.personnel_code, reg.national_id,
            ]  # fmt: skip

        for reg in registrations:
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
                ws.append([str(v) for v in row])  # همه رشته تا صفر ابتدایی حفظ شود
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = 16
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()

    # ---------- کمکی ----------

    async def _is_enabled(self) -> bool:
        return (await self.get_settings())["enabled"]

    async def _get_or_create_shell(self, employee: Employee) -> InsuranceRegistration:
        """ثبت‌نام (احتمالاً ناقص) این پرسنل - برای نگه‌داشتن مدارک قبل از ثبت نهایی."""
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
        await self.db.refresh(registration, attribute_names=["members"])
        return registration

    async def cleanup_pending_documents(self) -> int:
        """مدارک یتیم (آپلودشده ولی هرگز ثبت‌نشده) قدیمی‌تر از ۲۴ ساعت - برای زمان‌بند."""
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
    """نوع واقعی فایل از امضای محتوا (نه پسوند/Content-Type کلاینت)."""
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
