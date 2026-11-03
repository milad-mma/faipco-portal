"""
اتوماسیون اداری فاز ۲: قالب نسخه‌دار و پیش‌نویس نامه (docs/office-automation.md).

- قالب: برای همه‌ی سایت‌ها یکسان؛ هر ذخیره یک نسخه‌ی تغییرناپذیر تازه (oa_template_versions) با چیدمان مستقل A4/A5؛ لوگو یک فایل
  اتوماسیون (purpose=template) که با استفاده در نسخه‌ی قالب permanent می‌شود. مجوز automation.templates همان سایت.
- پیش‌نویس: فقط ایجادکننده می‌بیند و ویرایش می‌کند (فاز ۲)؛ متن همیشه در سرور پاک‌سازی می‌شود؛ قفل خوش‌بینانه با row_version؛
  content_hash در هر ذخیره. مجوز automation.access؛ نامه متعلق به سایت خود پرسنل.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import oa_letter_rules as rules
from app.core.oa_html import HtmlTooLarge, plain_text, sanitize_html
from app.models.office_automation import (
    OaFile,
    OaLetter,
    OaLetterVersion,
    OaTemplate,
    OaTemplateVersion,
)
from app.models.site import Site
from app.models.user import User
from app.services.oa_file_service import OaFileService

LOGO_EXTENSIONS = ("png", "jpg", "jpeg", "webp")


class OaLetterError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class OaLetterService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.files = OaFileService(db)

    # ================= قالب =================

    async def list_templates(self, include_inactive: bool = True) -> list[dict]:
        """همه‌ی قالب‌ها — قالب برای همه‌ی سایت‌ها یکسان است (تصمیم کاربر، Migration 138)."""
        stmt = select(OaTemplate).order_by(OaTemplate.id)
        if not include_inactive:
            stmt = stmt.where(OaTemplate.is_active.is_(True))
        rows = (await self.db.execute(stmt)).scalars().all()
        versions = {}
        ids = [t.current_version_id for t in rows if t.current_version_id]
        if ids:
            versions = {
                v.id: v for v in (await self.db.execute(select(OaTemplateVersion).where(OaTemplateVersion.id.in_(ids)))).scalars()
            }
        out = []
        for t in rows:
            v = versions.get(t.current_version_id)
            out.append({
                "id": t.id, "name": t.name,
                "default_paper_size": t.default_paper_size, "is_active": t.is_active,
                "version_id": v.id if v else None, "version_no": v.version_no if v else None,
                "layouts": v.layouts if v else rules.default_layouts(), "updated_at": t.updated_at,
            })
        return out

    async def get_template(self, template_id: int) -> OaTemplate:
        t = await self.db.get(OaTemplate, template_id)
        if t is None:
            raise OaLetterError("قالب یافت نشد", 404)
        return t

    async def _activate_logos(self, layouts: dict) -> None:
        """لوگوهای استفاده‌شده در چیدمان باید فایل سالم قالب باشند؛ permanent می‌شوند (پاک‌سازی نمی‌شوند)."""
        for size in rules.PAPER_SIZES:
            fid = layouts[size]["header"].get("logo_file_id")
            if not fid:
                continue
            f = await self.db.get(OaFile, fid)
            if f is None or f.purpose != "template" or f.status != "clean":
                raise OaLetterError("لوگوی انتخاب‌شده معتبر نیست؛ دوباره بارگذاری کنید")
            f.state = "permanent"

    async def save_template(self, *, template_id: int | None, name: str, default_paper_size: str,
                            is_active: bool, layouts: dict, user: User, ip: str | None = None) -> dict:
        """ایجاد یا ویرایش قالب؛ هر ذخیره یک نسخه‌ی تازه می‌سازد (نسخه‌های قبلی و نامه‌های متصل دست نمی‌خورند)."""
        name = (name or "").strip()[:120]
        if not name:
            raise OaLetterError("نام قالب الزامی است")
        if default_paper_size not in rules.PAPER_SIZES:
            raise OaLetterError("اندازه‌ی کاغذ نامعتبر است")
        try:
            clean = rules.validate_layouts(layouts)
        except rules.LetterRulesError as e:
            raise OaLetterError(str(e)) from None
        if template_id is None:
            t = OaTemplate(name=name, default_paper_size=default_paper_size, is_active=is_active,
                           created_by=user.id)
            self.db.add(t)
            await self.db.flush()
            next_no = 1
        else:
            t = await self.get_template(template_id)
            t.name, t.default_paper_size, t.is_active = name, default_paper_size, is_active
            next_no = (await self.db.execute(
                select(func.coalesce(func.max(OaTemplateVersion.version_no), 0)).where(OaTemplateVersion.template_id == t.id)
            )).scalar_one() + 1
        await self._activate_logos(clean)
        v = OaTemplateVersion(template_id=t.id, version_no=next_no, layouts=clean, created_by=user.id)
        self.db.add(v)
        await self.db.flush()
        t.current_version_id = v.id
        self.files.audit("template.save", user, entity="template", entity_id=t.id,
                         details={"version_no": next_no, "name": name}, ip=ip)
        await self.db.commit()
        await self.db.refresh(t, ["updated_at"])  # مقدار دیتابیس؛ خواندن تنبل در async ممکن نیست
        return next(x for x in await self.list_templates() if x["id"] == t.id)

    async def template_versions(self, template_id: int) -> list[dict]:
        rows = (await self.db.execute(
            select(OaTemplateVersion).where(OaTemplateVersion.template_id == template_id)
            .order_by(OaTemplateVersion.version_no.desc())
        )).scalars().all()
        return [{"id": v.id, "version_no": v.version_no, "created_at": v.created_at} for v in rows]

    async def logo_file(self, file_id: int) -> OaFile:
        f = await self.db.get(OaFile, file_id)
        if f is None or f.purpose != "template" or f.status != "clean" or not f.storage_key:
            raise OaLetterError("فایل یافت نشد", 404)
        return f

    # ================= پیش‌نویس =================

    async def _own_letter(self, letter_id: int, user: User) -> OaLetter:
        letter = await self.db.get(OaLetter, letter_id)
        if letter is None or letter.discarded_at is not None or letter.created_by != user.id:
            raise OaLetterError("پیش‌نویس یافت نشد", 404)
        return letter

    async def _template_version_for(self, template_id: int | None) -> OaTemplateVersion | None:
        if not template_id:
            return None
        t = await self.db.get(OaTemplate, template_id)
        if t is None or not t.is_active or not t.current_version_id:
            raise OaLetterError("قالب انتخاب‌شده در دسترس نیست")
        return await self.db.get(OaTemplateVersion, t.current_version_id)

    async def create_draft(self, *, paper_size: str | None, template_id: int | None, user: User) -> dict:
        """
        نامه‌ی تازه متعلق به سایت خود پرسنل است (تنظیمات پیوست و بعداً دبیرخانه‌ی همان سایت). بدون قالب انتخابی، اولین قالب
        فعال و اندازه‌ی پیش‌فرض آن.
        """
        from app.models.employee import Employee

        emp = await self.db.get(Employee, user.employee_id) if user.employee_id else None
        if emp is None:
            raise OaLetterError("حساب شما به پرسنل وصل نیست؛ نامه‌نگاری فقط برای پرسنل است", 403)
        site_id = emp.site_id
        if template_id is None:
            first = (await self.db.execute(
                select(OaTemplate).where(OaTemplate.is_active.is_(True), OaTemplate.current_version_id.is_not(None))
                .order_by(OaTemplate.id).limit(1)
            )).scalar_one_or_none()
            if first is not None:
                template_id = first.id
                paper_size = paper_size or first.default_paper_size
        paper_size = paper_size or "A4"
        if paper_size not in rules.PAPER_SIZES:
            raise OaLetterError("اندازه‌ی کاغذ نامعتبر است")
        tv = await self._template_version_for(template_id)
        letter = OaLetter(site_id=site_id, created_by=user.id, creator_employee_id=user.employee_id, status="draft")
        self.db.add(letter)
        await self.db.flush()
        v = OaLetterVersion(letter_id=letter.id, version_no=1, paper_size=paper_size,
                            template_version_id=tv.id if tv else None, created_by=user.id)
        v.content_hash = rules.content_hash(subject="", body_html="", paper_size=paper_size,
                                            template_version_id=v.template_version_id)
        self.db.add(v)
        await self.db.flush()
        letter.current_version_id = v.id
        self.files.audit("letter.create", user, entity="letter", entity_id=letter.id, site_id=site_id)
        await self.db.commit()
        return await self.draft_out(letter.id, user)

    async def save_draft(self, letter_id: int, *, subject: str, body_html: str, paper_size: str,
                         template_id: int | None, urgency: str, confidentiality: str, row_version: int,
                         user: User, requires_action: bool = False, action_due_at: datetime | None = None,
                         principal_employee_id: int | None = None, sign_on_send: bool = False) -> dict:
        letter = await self._own_letter(letter_id, user)
        if letter.status != "draft":
            raise OaLetterError("فقط پیش‌نویس قابل ویرایش است", 409)
        if letter.row_version != row_version:
            raise OaLetterError("این پیش‌نویس در جای دیگری (تب یا دستگاه دیگر) تغییر کرده است؛ صفحه را تازه کنید.", 409)
        if paper_size not in rules.PAPER_SIZES:
            raise OaLetterError("اندازه‌ی کاغذ نامعتبر است")
        if urgency not in rules.URGENCIES or confidentiality not in rules.CONFIDENTIALITY:
            raise OaLetterError("فوریت یا محرمانگی نامعتبر است")
        try:
            subject = rules.clean_subject(subject)
            body = sanitize_html(body_html)
        except (rules.LetterRulesError, HtmlTooLarge) as e:
            raise OaLetterError(str(e)) from None
        tv = await self._template_version_for(template_id)
        v = await self.db.get(OaLetterVersion, letter.current_version_id)
        if v is None or v.status != "editing":
            raise OaLetterError("نسخه‌ی قابل ویرایش پیدا نشد", 409)
        v.subject, v.body_html, v.paper_size = subject, body, paper_size
        v.template_version_id = tv.id if tv else None
        v.content_hash = rules.content_hash(subject=subject, body_html=body, paper_size=paper_size,
                                            template_version_id=v.template_version_id)
        letter.subject, letter.urgency, letter.confidentiality = subject, urgency, confidentiality
        letter.requires_action = bool(requires_action)
        letter.action_due_at = action_due_at if requires_action else None
        await self._set_principal(letter, principal_employee_id, user)
        # امضا فقط امضای خود نویسنده؛ نامه‌ای که منشی به نام مدیر می‌فرستد امضا نمی‌شود
        letter.sign_on_send = bool(sign_on_send) and not letter.principal_employee_id
        letter.row_version += 1
        await self.db.commit()
        return await self.draft_out(letter.id, user)

    async def _set_principal(self, letter: OaLetter, principal_employee_id: int | None, user: User) -> None:
        """
        «از طرف»: منشی نامه را به نام مدیر می‌فرستد. نامه متعلق به سایت همان مدیر می‌شود (تنظیمات سایت شخص).
        None یا خود کاربر = نامه‌ی خود شخص.
        """
        from app.models.employee import Employee
        from app.services.oa_secretary_service import OaSecretaryService

        if not principal_employee_id or principal_employee_id == user.employee_id:
            if letter.principal_employee_id is not None:
                me = await self.db.get(Employee, user.employee_id) if user.employee_id else None
                letter.principal_employee_id = None
                if me is not None:
                    letter.site_id = me.site_id
            return
        if principal_employee_id == letter.principal_employee_id:
            return
        if not await OaSecretaryService(self.db).is_secretary(principal_employee_id, user.employee_id):
            raise OaLetterError("شما منشی این شخص نیستید یا دسترسی او به اتوماسیون فعال نیست", 403)
        principal = await self.db.get(Employee, principal_employee_id)
        letter.principal_employee_id = principal.id
        letter.site_id = principal.site_id

    async def _principal_name(self, letter: OaLetter) -> str | None:
        if not letter.principal_employee_id:
            return None
        from app.models.employee import Employee

        e = await self.db.get(Employee, letter.principal_employee_id)
        return f"{e.first_name} {e.last_name}" if e else None

    async def discard_draft(self, letter_id: int, user: User) -> None:
        letter = await self._own_letter(letter_id, user)
        if letter.status != "draft":
            raise OaLetterError("فقط پیش‌نویس قابل حذف است", 409)
        from app.services.oa_cartable_service import OaCartableService

        await OaCartableService(self.db).delete_draft_files(letter)  # پیوست‌های هرگز ارسال‌نشده
        letter.discarded_at = datetime.now(timezone.utc)
        letter.status = "discarded"
        self.files.audit("letter.discard", user, entity="letter", entity_id=letter.id, site_id=letter.site_id)
        await self.db.commit()

    async def my_drafts(self, user: User) -> list[dict]:
        rows = (await self.db.execute(
            select(OaLetter, OaLetterVersion)
            .join(OaLetterVersion, OaLetterVersion.id == OaLetter.current_version_id)
            .where(OaLetter.created_by == user.id, OaLetter.status == "draft", OaLetter.discarded_at.is_(None))
            .order_by(OaLetter.updated_at.desc())
            .limit(200)
        )).all()
        sites = {s.id: s.name for s in (await self.db.execute(select(Site))).scalars()}
        return [
            {
                "id": letter.id, "site_id": letter.site_id, "site_name": sites.get(letter.site_id),
                "subject": letter.subject, "urgency": letter.urgency, "confidentiality": letter.confidentiality,
                "paper_size": v.paper_size, "excerpt": plain_text(v.body_html)[:160], "updated_at": letter.updated_at,
                "principal_name": await self._principal_name(letter),
            }
            for letter, v in rows
        ]

    async def draft_out(self, letter_id: int, user: User) -> dict:
        letter = await self._own_letter(letter_id, user)
        # updated_at را دیتابیس پر می‌کند و بعد از INSERT/UPDATE منقضی است؛ خواندن تنبل در async ممکن نیست (MissingGreenlet)
        await self.db.refresh(letter, ["updated_at"])
        v = await self.db.get(OaLetterVersion, letter.current_version_id)
        tv = await self.db.get(OaTemplateVersion, v.template_version_id) if v.template_version_id else None
        template_id = tv.template_id if tv else None
        template = await self.db.get(OaTemplate, template_id) if template_id else None
        site = await self.db.get(Site, letter.site_id)
        layout = (tv.layouts if tv else rules.default_layouts())[v.paper_size]
        return {
            "id": letter.id, "site_id": letter.site_id, "site_name": site.name if site else None,
            "status": letter.status, "urgency": letter.urgency, "confidentiality": letter.confidentiality,
            "row_version": letter.row_version, "version_no": v.version_no, "subject": v.subject,
            "body_html": v.body_html, "paper_size": v.paper_size, "content_hash": v.content_hash,
            "template_id": template_id, "template_name": template.name if template else None,
            "template_version_no": tv.version_no if tv else None,
            "template_outdated": bool(template and template.current_version_id != (tv.id if tv else None)),
            "layout": layout, "body_area_mm": rules.body_area_mm(v.paper_size, layout),
            "paper_mm": rules.PAPER_SIZES[v.paper_size], "updated_at": letter.updated_at,
            "requires_action": letter.requires_action, "action_due_at": letter.action_due_at,
            "principal_employee_id": letter.principal_employee_id, "principal_name": await self._principal_name(letter),
            **await self._signature_info(letter, user),
        }

    async def _signature_info(self, letter: OaLetter, user: User) -> dict:
        """چک‌باکس «امضا شود»: فقط اگر نویسنده امضای فعال دارد و نامه به نام خودش است."""
        from app.models.employee import Employee
        from app.services.oa_signature_service import OaSignatureService

        active = await OaSignatureService(self.db).active_for(user.employee_id) if user.employee_id else None
        me = await self.db.get(Employee, user.employee_id) if user.employee_id else None
        return {
            "sign_on_send": letter.sign_on_send,
            "has_signature": active is not None,
            "can_sign": active is not None and not letter.principal_employee_id,
            "signer_name": f"{me.first_name} {me.last_name}" if me else None,
            "signer_title": me.position_title if me else None,
        }
