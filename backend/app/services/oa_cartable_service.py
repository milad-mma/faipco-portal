"""
اتوماسیون اداری فاز ۳الف: گیرندگان، پیوست، ارسال نامه‌ی داخلی، کارتابل، مشاهده، ارجاع، انجام مسئولیت، هامش و محرمانه کردن
(docs/office-automation.md؛ سند مرجع بخش ۳.۲–۳.۴، ۵، ۶.۱، ۶.۳، ۱۳).

- هر دسترسی محتوایی از oa_letter_access و core/oa_access_rules.can() — بدون استثنا برای ادمین یا مجوز ماژول.
- همه‌چیز فردمحور است (employee_id)؛ نام/سمت/واحد لحظه‌ای در رکوردها ذخیره می‌شود.
- ارسال داخلی در فاز ۳الف بدون شماره است (شماره و تثبیت رسمی از فاز ۳ب).
- اعلان فقط Push (بدون «اطلاعیه»)؛ برای نامه‌ی محرمانه متن کلی. ارسال بعد از commit در پس‌زمینه (send_pushes).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select, true, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import oa_letter_rules as rules
from app.core.oa_access_rules import (
    can,
    delivery_grants,
    push_text_key,
    referral_grants,
)
from app.core.permission_grants import grants_subquery
from app.models.employee import Department, Employee
from app.models.office_automation import (
    OaAttachment,
    OaFile,
    OaLetter,
    OaLetterAccess,
    OaLetterVersion,
    OaNote,
    OaLetterRelation,
    OaNotificationLog,
    OaNotificationPref,
    OaRecipient,
    OaTask,
    OaTemplateVersion,
)
from app.models.site import Site
from app.models.user import User
from app.services.oa_file_service import OaFileService, file_out

logger = logging.getLogger("faipco.automation")

PAGE_SIZE = 20
# رویدادهای اعلان که هر کس می‌تواند برای خودش خاموش کند (تنظیمات اعلان شخصی)
PUSH_EVENTS = {"new_letter": "نامه‌ی جدید (گیرنده‌ی اصلی)", "cc": "رونوشت نامه", "referral": "ارجاع نامه به من"}
RELATION_TYPES = {"reply": "پاسخ"}  # عطف و پیرو به تصمیم کاربر حذف شد (۱۴۰۵/۰۸/۱۱)
MAX_RECIPIENTS = 200
MAX_NOTE = 4000
MAX_INSTRUCTION = 2000


class OaCartableError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _full_name(e: Employee) -> str:
    return f"{e.first_name} {e.last_name}".strip()


def eligible_users_subquery():
    """کاربران فعال دارای automation.access (هر سایت) یا ادمین کل — فقط این‌ها گیرنده/ارجاع‌گیرنده می‌شوند."""
    g = grants_subquery()
    return (
        select(User.employee_id)
        .where(User.is_active.is_(True), User.employee_id.is_not(None))
        .where(or_(User.is_superuser.is_(True), User.id.in_(select(g.c.user_id).where(g.c.code == "automation.access"))))
    )


async def send_pushes(pushes: list[dict]) -> None:
    """
    پس‌زمینه بعد از commit: برای هر اعلان {key, employee_id, site_id, text_key, values, url} یک بار (oa_notification_log) Push
    به دستگاه‌های کاربرِ آن پرسنل. خطا فقط لاگ می‌شود.
    """
    if not pushes:
        return
    from sqlalchemy.dialects.postgresql import insert

    from app.db.session import AsyncSessionLocal
    from app.services import notification_templates
    from app.services.push_service import PushService

    try:
        async with AsyncSessionLocal() as db:
            for p in pushes:
                inserted = (await db.execute(
                    insert(OaNotificationLog).values(key=p["key"][:200]).on_conflict_do_nothing().returning(OaNotificationLog.id)
                )).scalar_one_or_none()
                await db.commit()
                if inserted is None:
                    continue  # قبلاً فرستاده شده
                pref = await db.get(OaNotificationPref, p["employee_id"])
                if pref is not None and p.get("event") in (pref.disabled_events or []):
                    continue  # خود شخص این رویداد را خاموش کرده است
                user_ids = set((await db.execute(
                    select(User.id).where(User.employee_id == p["employee_id"], User.is_active.is_(True))
                )).scalars().all())
                if not user_ids:
                    continue
                body = await notification_templates.render(db, p["site_id"], p["text_key"], **p.get("values", {}))
                await asyncio.wait_for(
                    PushService(db).notify_users(user_ids, url=p["url"], priority=p.get("priority", "normal"), body=body),
                    timeout=60,
                )
    except Exception:
        logger.exception("ارسال اعلان اتوماسیون ناموفق بود")


class OaCartableService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.files = OaFileService(db)
        self.pushes: list[dict] = []  # بعد از commit با send_pushes فرستاده می‌شوند

    # ================= کمکی =================

    async def _me(self, user: User) -> Employee:
        if not user.employee_id:
            raise OaCartableError("حساب شما به پرسنل وصل نیست؛ اتوماسیون اداری فقط برای پرسنل است", 403)
        e = await self.db.get(Employee, user.employee_id)
        if e is None:
            raise OaCartableError("پرسنل حساب شما پیدا نشد", 403)
        return e

    async def _snapshot(self, employee_id: int) -> dict:
        row = (await self.db.execute(
            select(Employee, Department.name).outerjoin(Department, Department.id == Employee.department_id)
            .where(Employee.id == employee_id)
        )).first()
        if row is None:
            raise OaCartableError("پرسنل انتخاب‌شده پیدا نشد")
        e, dept = row
        return {"employee_id": e.id, "name": _full_name(e), "title": e.position_title, "department": dept}

    async def _allowed_sites(self, user: User) -> set[int] | None:
        """
        سایت‌هایی که کاربر می‌تواند به پرسنلشان نامه بفرستد یا ارجاع دهد: سایت خودش + هر سایتی که automation.access آن را
        دارد. None = همه (دسترسی سراسری یا ادمین کل).
        """
        from app.core.site_access import get_sites_with_permission

        sites = await get_sites_with_permission(self.db, user, "automation.access")
        if sites is None:
            return None
        me = await self._me(user)
        return set(sites) | {me.site_id}

    async def _eligible(self, employee_ids: set[int], user: User) -> set[int]:
        """از employee_ids، کسانی که فعال‌اند، دسترسی اتوماسیون دارند و در سایت مجاز فرستنده‌اند."""
        if not employee_ids:
            return set()
        stmt = select(Employee.id).where(
            Employee.id.in_(employee_ids), Employee.is_active.is_(True), Employee.is_enabled.is_(True),
            Employee.id.in_(eligible_users_subquery()),
        )
        allowed = await self._allowed_sites(user)
        if allowed is not None:
            stmt = stmt.where(Employee.site_id.in_(allowed))
        return set((await self.db.execute(stmt)).scalars().all())

    async def _rows(self, letter_id: int, employee_id: int) -> list[dict]:
        rows = (await self.db.execute(
            select(OaLetterAccess).where(OaLetterAccess.letter_id == letter_id, OaLetterAccess.employee_id == employee_id)
        )).scalars().all()
        return [{"source": r.source, "can_act": r.can_act, "can_refer": r.can_refer, "revoked_at": r.revoked_at,
                 "obj": r} for r in rows]

    async def _open_tasks(self, letter_id: int, employee_id: int) -> list[OaTask]:
        return list((await self.db.execute(
            select(OaTask).where(OaTask.letter_id == letter_id, OaTask.assignee_employee_id == employee_id,
                                 OaTask.status == "open").order_by(OaTask.id)
        )).scalars().all())

    async def _letter_for(self, letter_id: int, user: User, action: str, *, lock: bool = False):
        """نامه + ردیف‌های دسترسی کاربر؛ بدون دسترسی → 404 (وجود نامه هم فاش نمی‌شود)."""
        me = await self._me(user)
        stmt = select(OaLetter).where(OaLetter.id == letter_id)
        if lock:
            stmt = stmt.with_for_update()
        letter = (await self.db.execute(stmt)).scalar_one_or_none()
        if letter is None or letter.discarded_at is not None:
            raise OaCartableError("نامه یافت نشد", 404)
        rows = await self._rows(letter.id, me.id)
        tasks = await self._open_tasks(letter.id, me.id)
        info = {"status": letter.status, "confidentiality": letter.confidentiality}
        if not can("view", letter=info, rows=rows):
            raise OaCartableError("نامه یافت نشد", 404)
        if not can(action, letter=info, rows=rows, open_task=bool(tasks)):
            raise OaCartableError("اجازه‌ی این کار روی این نامه را ندارید", 403)
        return letter, me, rows, tasks

    async def _own_draft(self, letter_id: int, user: User, *, lock: bool = False) -> OaLetter:
        stmt = select(OaLetter).where(OaLetter.id == letter_id)
        if lock:
            stmt = stmt.with_for_update()
        letter = (await self.db.execute(stmt)).scalar_one_or_none()
        if letter is None or letter.discarded_at is not None or letter.created_by != user.id:
            raise OaCartableError("پیش‌نویس یافت نشد", 404)
        if letter.status != "draft":
            raise OaCartableError("این نامه دیگر پیش‌نویس نیست", 409)
        return letter

    def _push(self, *, event: str, letter: OaLetter, employee_id: int, values: dict, extra: str = "") -> None:
        confidential = letter.confidentiality == "confidential"
        self.pushes.append({
            "key": f"{event}:{letter.id}:{employee_id}:{extra}",
            "event": event,
            "employee_id": employee_id,
            "site_id": letter.site_id,
            "text_key": push_text_key(event, confidential),
            "values": {} if confidential else values,
            "url": f"/automation/letters/{letter.id}",
            "priority": "high" if letter.urgency in ("urgent", "immediate") else "normal",
        })

    # ================= انتخاب گیرنده (فردمحور) =================

    async def picker(self, user: User, *, q: str = "", department_id: int | None = None, title: str = "",
                     limit: int = 50) -> dict:
        """
        پرسنل قابل انتخاب (فعال + دسترسی اتوماسیون). فقط نام، سمت و واحد — کد پرسنلی/ملی هرگز برنمی‌گردد.
        فیلتر واحد/عنوان فقط برای پیدا کردن اشخاص است (گیرنده همیشه شخص است).
        """
        await self._me(user)
        stmt = (
            select(Employee, Department.name)
            .outerjoin(Department, Department.id == Employee.department_id)
            .where(Employee.is_active.is_(True), Employee.is_enabled.is_(True), Employee.id.in_(eligible_users_subquery()))
        )
        allowed = await self._allowed_sites(user)
        if allowed is not None:
            stmt = stmt.where(Employee.site_id.in_(allowed))
        for word in (q or "").split()[:4]:
            like = f"%{word}%"
            stmt = stmt.where(or_(Employee.first_name.ilike(like), Employee.last_name.ilike(like),
                                  Employee.position_title.ilike(like), Department.name.ilike(like)))
        if department_id:
            stmt = stmt.where(Employee.department_id == department_id)
        if title.strip():
            stmt = stmt.where(Employee.position_title.ilike(f"%{title.strip()}%"))
        rows = (await self.db.execute(stmt.order_by(Employee.last_name, Employee.first_name).limit(min(limit, 200)))).all()
        depts = (await self.db.execute(
            select(Department.id, Department.name, Site.name)
            .join(Site, Site.id == Department.site_id)
            .where(Department.id.in_(
                select(Employee.department_id).where(Employee.id.in_(eligible_users_subquery()), Employee.is_active.is_(True))
            ))
            .where(true() if allowed is None else Department.site_id.in_(allowed))
            .order_by(Site.name, Department.name)
        )).all()
        return {
            "people": [{"employee_id": e.id, "name": _full_name(e), "title": e.position_title, "department": d}
                       for e, d in rows],
            "departments": [{"id": i, "name": n, "site": s} for i, n, s in depts],
        }

    # ================= پیش‌نویس: گیرندگان و پیوست =================

    async def draft_extras(self, letter: OaLetter) -> dict:
        recipients = (await self.db.execute(
            select(OaRecipient).where(OaRecipient.letter_id == letter.id).order_by(OaRecipient.role.desc(), OaRecipient.sort_order)
        )).scalars().all()
        return {
            "recipients": [{"employee_id": r.employee_id, "role": r.role, "name": r.name_snapshot,
                            "title": r.title_snapshot, "department": r.department_snapshot} for r in recipients],
            "attachments": await self._attachments(letter.current_version_id),
            "attachment_limits": await self._attachment_limits(letter.site_id),
            "relations": await self.relations_for(letter.id, letter.creator_employee_id),
        }

    async def _attachment_limits(self, site_id: int) -> dict:
        """سقف پیوست نامه از تنظیمات سایت فرستنده (برای انتخاب چند فایل در رابط؛ سرور دوباره بررسی می‌کند)."""
        from app.services import server_upload_limit

        st = await self.files.site_settings(site_id)
        return {
            "max_files": st["letter_max_files"],
            "max_file_mb": min(st["letter_max_file_mb"], await server_upload_limit.portal_max_file_mb(self.db)),
            "max_total_mb": st["letter_max_total_mb"],
        }

    async def set_recipients(self, letter_id: int, user: User, items: list[dict]) -> dict:
        letter = await self._own_draft(letter_id, user, lock=True)
        clean: dict[int, dict] = {}
        for i, it in enumerate(items[:MAX_RECIPIENTS + 1]):
            role = it.get("role")
            if role not in ("to", "cc"):
                raise OaCartableError("نقش گیرنده نامعتبر است")
            eid = int(it.get("employee_id") or 0)
            if eid in clean:
                continue  # یک نفر یک بار (اولی می‌ماند)
            clean[eid] = {"role": role, "via": it.get("selected_via") if it.get("selected_via") in ("direct", "department", "title") else "direct", "order": i}
        if len(clean) > MAX_RECIPIENTS:
            raise OaCartableError(f"حداکثر {MAX_RECIPIENTS} گیرنده")
        ok = await self._eligible(set(clean), user)
        bad = set(clean) - ok
        if bad:
            raise OaCartableError(
                "یک یا چند نفر از گیرندگان مجاز نیستند (غیرفعال، بدون دسترسی اتوماسیون، یا در سایتی که شما به آن دسترسی ندارید)"
            )
        old = {r.employee_id: r for r in (await self.db.execute(
            select(OaRecipient).where(OaRecipient.letter_id == letter.id))).scalars()}
        for eid, r in old.items():
            if eid not in clean:
                await self.db.delete(r)
        for eid, c in clean.items():
            r = old.get(eid)
            if r is None:
                snap = await self._snapshot(eid)
                r = OaRecipient(letter_id=letter.id, employee_id=eid, name_snapshot=snap["name"],
                                title_snapshot=snap["title"], department_snapshot=snap["department"])
                self.db.add(r)
            r.role, r.selected_via, r.sort_order = c["role"], c["via"], c["order"]
        # row_version فقط برای متن پیش‌نویس است (ذخیره‌ی خودکار ویرایشگر)؛ گیرنده و پیوست جدا ذخیره می‌شوند
        await self.db.commit()
        return await self.draft_extras(letter)

    async def _attachments(self, version_id: int | None) -> list[dict]:
        if not version_id:
            return []
        rows = (await self.db.execute(
            select(OaAttachment, OaFile).join(OaFile, OaFile.id == OaAttachment.file_id)
            .where(OaAttachment.letter_version_id == version_id).order_by(OaAttachment.sort_order, OaAttachment.id)
        )).all()
        return [{"id": a.id, "description": a.description, "file": file_out(f)} for a, f in rows]

    async def add_attachment(self, letter_id: int, user: User, *, filename: str, chunks, ip: str | None) -> dict:
        from app.core import oa_file_rules as frules
        from app.services.oa_file_service import OaFileError

        letter = await self._own_draft(letter_id, user)
        settings = await self.files.site_settings(letter.site_id)
        existing = (await self.db.execute(
            select(OaFile.size).join(OaAttachment, OaAttachment.file_id == OaFile.id)
            .where(OaAttachment.letter_version_id == letter.current_version_id)
        )).scalars().all()
        if len(existing) >= settings["letter_max_files"]:
            raise OaCartableError(f"حداکثر {settings['letter_max_files']} پیوست برای هر نامه مجاز است")
        try:
            row = await self.files.upload(site_id=letter.site_id, filename=filename, chunks=chunks, user=user,
                                          context="letter", purpose="attachment", ip=ip)
        except OaFileError as e:
            raise OaCartableError(str(e), e.status_code) from None
        try:
            frules.check_quota(list(existing), row.size, settings["letter_max_files"], settings["letter_max_total_mb"])
        except frules.FileRejected as e:
            self.files.storage.delete(row.storage_key)
            await self.db.delete(row)
            await self.db.commit()
            raise OaCartableError(str(e)) from None
        row.state = "permanent"  # به پیش‌نویس وصل است؛ پاک‌سازی فایل‌های موقت به آن دست نمی‌زند
        self.db.add(OaAttachment(letter_version_id=letter.current_version_id, file_id=row.id,
                                 sort_order=len(existing), added_by=user.id))
        await self.db.commit()
        return {"attachments": await self._attachments(letter.current_version_id)}

    async def remove_attachment(self, letter_id: int, attachment_id: int, user: User) -> dict:
        letter = await self._own_draft(letter_id, user)
        a = await self.db.get(OaAttachment, attachment_id)
        if a is None or a.letter_version_id != letter.current_version_id:
            raise OaCartableError("پیوست یافت نشد", 404)
        f = await self.db.get(OaFile, a.file_id)
        await self.db.delete(a)
        await self.db.flush()
        if f is not None:
            if f.storage_key:
                self.files.storage.delete(f.storage_key)
            await self.db.delete(f)
        await self.db.commit()
        return {"attachments": await self._attachments(letter.current_version_id)}

    async def delete_draft_files(self, letter: OaLetter) -> None:
        """حذف پیش‌نویس: پیوست‌هایش هرگز به کسی نرسیده‌اند و پاک می‌شوند (فراخواننده commit می‌کند)."""
        rows = (await self.db.execute(
            select(OaAttachment, OaFile).join(OaFile, OaFile.id == OaAttachment.file_id)
            .join(OaLetterVersion, OaLetterVersion.id == OaAttachment.letter_version_id)
            .where(OaLetterVersion.letter_id == letter.id)
        )).all()
        for a, f in rows:
            await self.db.delete(a)
            await self.db.flush()
            if f.storage_key:
                self.files.storage.delete(f.storage_key)
            await self.db.delete(f)

    # ================= ارسال =================

    async def send(self, letter_id: int, user: User, row_version: int) -> int:
        """
        ارسال نامه‌ی داخلی (یک تراکنش با قفل ردیف): نسخه تثبیت، دسترسی فرستنده/گیرندگان/رونوشت، مسئولیت اقدام برای هر
        گیرنده‌ی اصلی، فایل‌ها دائم، Push. کلیک دوباره روی نامه‌ی ارسال‌شده همان نامه را برمی‌گرداند (بدون ارسال دوباره).
        """
        letter = (await self.db.execute(select(OaLetter).where(OaLetter.id == letter_id).with_for_update())).scalar_one_or_none()
        if letter is None or letter.discarded_at is not None or letter.created_by != user.id:
            raise OaCartableError("پیش‌نویس یافت نشد", 404)
        if letter.status != "draft":
            if letter.sent_at:
                return letter.id  # تکرار درخواست ارسال (دوبار کلیک/تلاش دوباره)
            raise OaCartableError("این نامه قابل ارسال نیست", 409)
        if letter.row_version != row_version:
            raise OaCartableError("پیش‌نویس در جای دیگری تغییر کرده است؛ صفحه را تازه کنید.", 409)
        me = await self._me(user)
        v = await self.db.get(OaLetterVersion, letter.current_version_id)
        if not (v.subject or "").strip():
            raise OaCartableError("موضوع نامه را بنویسید")
        if not (v.body_html or "").strip():
            raise OaCartableError("متن نامه خالی است")
        recipients = list((await self.db.execute(
            select(OaRecipient).where(OaRecipient.letter_id == letter.id).order_by(OaRecipient.sort_order)
        )).scalars().all())
        if not any(r.role == "to" for r in recipients):
            raise OaCartableError("حداقل یک گیرنده‌ی اصلی انتخاب کنید")
        ids = {r.employee_id for r in recipients if r.employee_id}
        if me.id in ids:
            raise OaCartableError("نمی‌توانید خودتان را گیرنده‌ی نامه‌ی خودتان کنید")
        if (ids - await self._eligible(ids, user)) or len(ids) != len(recipients):
            raise OaCartableError("یک یا چند گیرنده دیگر فعال یا مجاز نیستند؛ فهرست گیرندگان را بررسی کنید")
        att_files = (await self.db.execute(
            select(OaFile).join(OaAttachment, OaAttachment.file_id == OaFile.id)
            .where(OaAttachment.letter_version_id == v.id).order_by(OaAttachment.sort_order, OaAttachment.id)
        )).scalars().all()
        if any(f.status != "clean" for f in att_files):
            raise OaCartableError("بعضی پیوست‌ها هنوز بررسی (اسکن) نشده‌اند یا سالم نیستند؛ کمی بعد دوباره امتحان کنید")

        now = _now()
        snap = await self._snapshot(me.id)
        v.status, v.frozen_at = "frozen", now
        v.content_hash = rules.content_hash(
            subject=v.subject, body_html=v.body_html, paper_size=v.paper_size, template_version_id=v.template_version_id,
            recipients=[f"{r.role}:{r.employee_id}" for r in recipients], attachments=[f.sha256 for f in att_files],
        )
        letter.status, letter.sent_at = "dispatched", now
        letter.sender_employee_id = me.id
        letter.sender_name_snapshot, letter.sender_title_snapshot = snap["name"], snap["title"]
        letter.row_version += 1
        self.db.add(OaLetterAccess(letter_id=letter.id, employee_id=me.id, source="creator",
                                   granted_by_user_id=user.id, read_at=now))
        self.db.add(OaLetterAccess(letter_id=letter.id, employee_id=me.id, source="sender", can_refer=True,
                                   granted_by_user_id=user.id, read_at=now))
        for r in recipients:
            g = delivery_grants(r.role)
            r.delivered_at = now
            self.db.add(OaLetterAccess(letter_id=letter.id, employee_id=r.employee_id, source=g["source"],
                                       can_act=g["can_act"], can_refer=g["can_refer"],
                                       granted_by_employee_id=me.id, granted_by_user_id=user.id))
            # مسئولیت فقط وقتی سازنده «نیاز به اقدام گیرنده» را زده باشد؛ وگرنه گیرنده فقط می‌خواند
            if g["task_kind"] and letter.requires_action:
                self.db.add(OaTask(letter_id=letter.id, kind=g["task_kind"], origin="delivery", due_at=letter.action_due_at,
                                   assignee_employee_id=r.employee_id, assignee_name_snapshot=r.name_snapshot,
                                   assignee_title_snapshot=r.title_snapshot, created_by_employee_id=me.id,
                                   created_by_name_snapshot=snap["name"]))
            self._push(event="new_letter" if r.role == "to" else "cc", letter=letter, employee_id=r.employee_id,
                       values={"sender": snap["name"], "subject": v.subject})
        for f in att_files:
            f.state = "permanent"
        self.files.audit("letter.send", user, entity="letter", entity_id=letter.id, site_id=letter.site_id,
                         details={"to": sum(r.role == "to" for r in recipients), "cc": sum(r.role == "cc" for r in recipients),
                                  "attachments": len(att_files)})
        await self.db.commit()
        return letter.id

    # ================= مشاهده =================

    async def letter_detail(self, letter_id: int, user: User, ip: str | None = None) -> dict:
        letter, me, rows, my_tasks = await self._letter_for(letter_id, user, "view")
        now = _now()
        changed = False
        for r in rows:
            if r["obj"].read_at is None and not r["revoked_at"]:
                r["obj"].read_at = now
                changed = True
        await self.db.execute(
            update(OaRecipient).where(OaRecipient.letter_id == letter.id, OaRecipient.employee_id == me.id,
                                      OaRecipient.read_at.is_(None)).values(read_at=now)
        )
        if changed:
            self.files.audit("letter.view", user, entity="letter", entity_id=letter.id, site_id=letter.site_id, ip=ip)
        await self.db.commit()

        v = await self.db.get(OaLetterVersion, letter.current_version_id)
        tv = await self.db.get(OaTemplateVersion, v.template_version_id) if v.template_version_id else None
        layout = (tv.layouts if tv else rules.default_layouts())[v.paper_size]
        site = await self.db.get(Site, letter.site_id)
        sources = {r["source"] for r in rows if not r["revoked_at"]}
        info = {"status": letter.status, "confidentiality": letter.confidentiality}
        recipients = (await self.db.execute(
            select(OaRecipient).where(OaRecipient.letter_id == letter.id).order_by(OaRecipient.role.desc(), OaRecipient.sort_order)
        )).scalars().all()
        tasks = (await self.db.execute(select(OaTask).where(OaTask.letter_id == letter.id).order_by(OaTask.id))).scalars().all()
        notes = (await self.db.execute(select(OaNote).where(OaNote.letter_id == letter.id).order_by(OaNote.id))).scalars().all()
        read_by = {
            eid: at for eid, at in (await self.db.execute(
                select(OaLetterAccess.employee_id, func.min(OaLetterAccess.read_at))
                .where(OaLetterAccess.letter_id == letter.id, OaLetterAccess.revoked_at.is_(None))
                .group_by(OaLetterAccess.employee_id)
            )).all()
        }
        return {
            "id": letter.id, "status": letter.status, "subject": v.subject, "body_html": v.body_html,
            "paper_size": v.paper_size, "layout": layout, "site_name": site.name if site else None,
            "urgency": letter.urgency, "confidentiality": letter.confidentiality,
            "sender": {"name": letter.sender_name_snapshot, "title": letter.sender_title_snapshot},
            "sent_at": letter.sent_at, "my_roles": sorted(sources),
            "recipients": [
                {"role": r.role, "name": r.name_snapshot, "title": r.title_snapshot, "department": r.department_snapshot,
                 "read_at": r.read_at, "delivered_at": r.delivered_at}
                for r in recipients
            ],
            "attachments": await self._attachments(v.id),
            "flow": self._flow(letter, recipients, tasks, read_by),
            "relations": await self.relations_for(letter.id, me.id),
            "requires_action": letter.requires_action, "action_due_at": letter.action_due_at,
            "tasks": [
                {"id": t.id, "parent_id": t.parent_task_id, "kind": t.kind, "origin": t.origin, "status": t.status,
                 "assignee": t.assignee_name_snapshot, "assignee_title": t.assignee_title_snapshot,
                 "created_by": t.created_by_name_snapshot, "instruction": t.instruction, "due_at": t.due_at,
                 "result_note": t.result_note, "done_at": t.done_at, "created_at": t.created_at,
                 "mine": t.assignee_employee_id == me.id}
                for t in tasks
            ],
            "notes": [{"id": n.id, "author": n.author_name_snapshot, "text": n.text, "created_at": n.created_at,
                       "mine": n.author_employee_id == me.id} for n in notes],
            "permissions": {
                "refer": can("refer", letter=info, rows=rows),
                "note": can("note", letter=info, rows=rows),
                "make_confidential": can("make_confidential", letter=info, rows=rows),
            },
            "my_open_tasks": [{"id": t.id, "kind": t.kind, "instruction": t.instruction} for t in my_tasks],
        }

    @staticmethod
    def _flow(letter: OaLetter, recipients, tasks, read_by: dict) -> list[dict]:
        """
        مراحل گردش برای نمایش (مثل گردش درخواست وام): ارسال، هر گیرنده/رونوشت با وضعیت خوانده‌شدن یا اقدام، سپس ارجاع‌ها.
        state: done (اقدام/رؤیت ثبت شد) | current (در انتظار اقدام) | read (خوانده شد) | unread | cancelled.
        """
        def state(task, emp_id):
            if task is not None:
                if task.status == "done":
                    return "done"
                if task.status != "open":
                    return "cancelled"
                return "current"
            return "read" if read_by.get(emp_id) else "unread"

        delivery = {t.assignee_employee_id: t for t in tasks if t.origin == "delivery"}
        now = _now()
        steps = [{"key": "sent", "label": "ارسال", "person": letter.sender_name_snapshot, "title": letter.sender_title_snapshot,
                  "state": "done", "at": letter.sent_at}]
        for r in recipients:
            t = delivery.get(r.employee_id)
            steps.append({
                "key": f"r{r.id}", "label": ("گیرنده" if r.role == "to" else "رونوشت") + (" — اقدام" if t else ""),
                "person": r.name_snapshot, "title": r.title_snapshot, "state": state(t, r.employee_id),
                "read_at": read_by.get(r.employee_id), "at": (t.done_at if t and t.done_at else r.delivered_at),
                "note": t.result_note if t else None, "due_at": t.due_at if t else None,
                "overdue": bool(t and t.status == "open" and t.due_at and t.due_at < now),
            })
        for t in tasks:
            if t.origin != "referral":
                continue
            steps.append({
                "key": f"t{t.id}", "label": f"ارجاع — {'اقدام' if t.kind == 'action' else 'اطلاع'}",
                "person": t.assignee_name_snapshot, "title": t.assignee_title_snapshot,
                "state": state(t, t.assignee_employee_id), "read_at": read_by.get(t.assignee_employee_id),
                "at": t.done_at or t.created_at, "created_at": t.created_at, "from": t.created_by_name_snapshot,
                "instruction": t.instruction,
                "note": t.result_note, "due_at": t.due_at,
                "overdue": bool(t.status == "open" and t.due_at and t.due_at < now),
            })
        return steps

    async def attachment_for_download(self, letter_id: int, attachment_id: int, user: User, ip: str | None):
        letter, me, rows, _ = await self._letter_for(letter_id, user, "download")
        row = (await self.db.execute(
            select(OaAttachment, OaFile).join(OaFile, OaFile.id == OaAttachment.file_id)
            .join(OaLetterVersion, OaLetterVersion.id == OaAttachment.letter_version_id)
            .where(OaAttachment.id == attachment_id, OaLetterVersion.letter_id == letter.id)
        )).first()
        if row is None:
            raise OaCartableError("پیوست یافت نشد", 404)
        _, f = row
        from app.core import oa_file_rules as frules

        if not frules.can_download(f.status) or not f.storage_key or not self.files.storage.exists(f.storage_key):
            raise OaCartableError("این فایل قابل دانلود نیست", 409)
        self.files.audit("file.download", user, entity="file", entity_id=f.id, site_id=letter.site_id,
                         details={"letter_id": letter.id}, ip=ip)
        await self.db.commit()
        fmt = frules.FORMAT_BY_CODE.get(f.detected_format or "")
        return f, frules.safe_download_name(f.original_name, fmt)

    async def draft_attachment_for_download(self, letter_id: int, attachment_id: int, user: User):
        letter = await self._own_draft(letter_id, user)
        a = await self.db.get(OaAttachment, attachment_id)
        if a is None or a.letter_version_id != letter.current_version_id:
            raise OaCartableError("پیوست یافت نشد", 404)
        f = await self.db.get(OaFile, a.file_id)
        from app.core import oa_file_rules as frules

        if f is None or not frules.can_download(f.status) or not f.storage_key:
            raise OaCartableError("این فایل قابل دانلود نیست", 409)
        return f, frules.safe_download_name(f.original_name, frules.FORMAT_BY_CODE.get(f.detected_format or ""))

    # ================= ارجاع، انجام، هامش، محرمانه =================

    async def refer(self, letter_id: int, user: User, *, assignees: list[int], kind: str, instruction: str,
                    allow_refer: bool, due_at: datetime | None) -> None:
        letter, me, rows, my_tasks = await self._letter_for(letter_id, user, "refer", lock=True)
        try:
            g = referral_grants(kind, allow_refer)
        except ValueError as e:
            raise OaCartableError(str(e)) from None
        ids = {int(a) for a in assignees if a}
        if not ids:
            raise OaCartableError("حداقل یک نفر را برای ارجاع انتخاب کنید")
        if len(ids) > 50:
            raise OaCartableError("حداکثر ۵۰ نفر در هر ارجاع")
        if me.id in ids:
            raise OaCartableError("ارجاع به خودتان ممکن نیست")
        if ids - await self._eligible(ids, user):
            raise OaCartableError(
                "یک یا چند نفر مجاز نیستند (غیرفعال، بدون دسترسی اتوماسیون، یا در سایتی که شما به آن دسترسی ندارید)"
            )
        instruction = (instruction or "").strip()[:MAX_INSTRUCTION]
        busy = set((await self.db.execute(
            select(OaTask.assignee_employee_id).where(OaTask.letter_id == letter.id, OaTask.status == "open",
                                                      OaTask.assignee_employee_id.in_(ids))
        )).scalars().all())
        if busy:
            raise OaCartableError("بعضی از افراد انتخاب‌شده همین حالا مسئولیت باز روی این نامه دارند")
        snap_me = await self._snapshot(me.id)
        parent = my_tasks[-1].id if my_tasks else None
        subject = (await self.db.get(OaLetterVersion, letter.current_version_id)).subject
        for eid in ids:
            snap = await self._snapshot(eid)
            self.db.add(OaLetterAccess(letter_id=letter.id, employee_id=eid, source="referral", can_act=g["can_act"],
                                       can_refer=g["can_refer"], granted_by_employee_id=me.id, granted_by_user_id=user.id))
            task = OaTask(letter_id=letter.id, parent_task_id=parent, kind=g["task_kind"], origin="referral",
                          assignee_employee_id=eid, assignee_name_snapshot=snap["name"], assignee_title_snapshot=snap["title"],
                          instruction=instruction or None, due_at=due_at, created_by_employee_id=me.id,
                          created_by_name_snapshot=snap_me["name"])
            self.db.add(task)
            await self.db.flush()
            self._push(event="referral", letter=letter, employee_id=eid,
                       values={"sender": snap_me["name"], "subject": subject}, extra=str(task.id))
        self.files.audit("letter.refer", user, entity="letter", entity_id=letter.id, site_id=letter.site_id,
                         details={"count": len(ids), "kind": kind, "allow_refer": bool(allow_refer)})
        await self.db.commit()

    async def complete_task(self, task_id: int, user: User, note: str) -> None:
        me = await self._me(user)
        task = (await self.db.execute(select(OaTask).where(OaTask.id == task_id).with_for_update())).scalar_one_or_none()
        if task is None or task.assignee_employee_id != me.id:
            raise OaCartableError("مسئولیت یافت نشد", 404)
        # دسترسی به نامه هنوز برقرار باشد (لغو دسترسی → اقدام هم ممکن نیست)
        await self._letter_for(task.letter_id, user, "act")
        if task.status != "open":
            raise OaCartableError("این مسئولیت قبلاً بسته شده است", 409)
        note = (note or "").strip()[:MAX_NOTE]
        if task.kind == "action" and not note:
            raise OaCartableError("نتیجه‌ی اقدام را بنویسید")
        task.status, task.result_note, task.done_at, task.acted_by_user_id = "done", note or None, _now(), user.id
        self.files.audit("task.done", user, entity="task", entity_id=task.id, details={"letter_id": task.letter_id})
        await self.db.commit()

    async def add_note(self, letter_id: int, user: User, text: str) -> None:
        letter, me, _, my_tasks = await self._letter_for(letter_id, user, "note")
        text = (text or "").strip()
        if not text:
            raise OaCartableError("متن هامش خالی است")
        if len(text) > MAX_NOTE:
            raise OaCartableError(f"هامش حداکثر {MAX_NOTE} نویسه است")
        snap = await self._snapshot(me.id)
        self.db.add(OaNote(letter_id=letter.id, task_id=my_tasks[-1].id if my_tasks else None,
                           author_employee_id=me.id, author_name_snapshot=snap["name"], text=text))
        await self.db.commit()

    async def make_confidential(self, letter_id: int, user: User, reason: str | None) -> None:
        letter, *_ = await self._letter_for(letter_id, user, "make_confidential", lock=True)
        letter.confidentiality = "confidential"  # تغییر غیرمؤثر: نسخه‌ی جدید نمی‌سازد
        self.files.audit("letter.make_confidential", user, entity="letter", entity_id=letter.id, site_id=letter.site_id,
                         details={"reason": (reason or "")[:300]})
        await self.db.commit()

    # ================= کارتابل =================

    def _letter_cols(self):
        att_count = (
            select(func.count(OaAttachment.id)).where(OaAttachment.letter_version_id == OaLetter.current_version_id)
            .correlate(OaLetter).scalar_subquery()
        )
        return [OaLetter.id, OaLetter.subject, OaLetter.urgency, OaLetter.confidentiality, OaLetter.sender_name_snapshot,
                OaLetter.sent_at, OaLetter.status, att_count.label("attachments")]

    @staticmethod
    def _row(r, extra: dict | None = None) -> dict:
        out = {"letter_id": r.id, "subject": r.subject, "urgency": r.urgency, "confidentiality": r.confidentiality,
               "sender": r.sender_name_snapshot, "sent_at": r.sent_at, "attachments": r.attachments}
        out.update(extra or {})
        return out

    async def cartable(self, user: User, *, box: str, q: str = "", page: int = 1) -> dict:
        me = await self._me(user)
        page = max(1, page)
        cols = self._letter_cols()
        if box == "inbox":
            acc = (
                select(OaLetterAccess.letter_id.label("lid"),
                       func.bool_or(OaLetterAccess.read_at.is_(None)).label("unread"),
                       func.max(OaLetterAccess.granted_at).label("at"))
                .where(OaLetterAccess.employee_id == me.id, OaLetterAccess.revoked_at.is_(None),
                       OaLetterAccess.source.in_(("recipient", "cc", "referral")))
                .group_by(OaLetterAccess.letter_id).subquery()
            )
            roles = (
                select(func.string_agg(OaLetterAccess.source, ","))
                .where(OaLetterAccess.letter_id == OaLetter.id, OaLetterAccess.employee_id == me.id,
                       OaLetterAccess.revoked_at.is_(None)).correlate(OaLetter).scalar_subquery()
            )
            stmt = (select(*cols, acc.c.unread, acc.c.at, roles.label("roles")).select_from(OaLetter)
                    .join(acc, acc.c.lid == OaLetter.id))
            order = acc.c.at.desc()
        elif box in ("pending", "done"):
            stmt = select(*cols, OaTask.id.label("task_id"), OaTask.kind, OaTask.instruction, OaTask.due_at,
                          OaTask.created_by_name_snapshot.label("task_from"), OaTask.created_at.label("at"),
                          OaTask.done_at, OaTask.result_note).select_from(OaLetter).join(
                OaTask, OaTask.letter_id == OaLetter.id).where(
                OaTask.assignee_employee_id == me.id, OaTask.status == ("open" if box == "pending" else "done"))
            order = OaTask.created_at.desc() if box == "pending" else OaTask.done_at.desc()
        elif box == "sent":
            stmt = select(*cols).where(OaLetter.sender_employee_id == me.id)
            order = OaLetter.sent_at.desc()
        else:
            raise OaCartableError("کارتابل نامعتبر است")
        stmt = stmt.where(OaLetter.status.in_(("dispatched", "closed")), OaLetter.discarded_at.is_(None))
        for word in (q or "").split()[:5]:
            like = f"%{word}%"
            stmt = stmt.where(or_(OaLetter.subject.ilike(like), OaLetter.sender_name_snapshot.ilike(like)))
        total = (await self.db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (await self.db.execute(stmt.order_by(order, OaLetter.id.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE))).all()
        now = _now()
        items = []
        for r in rows:
            if box == "inbox":
                items.append(self._row(r, {"unread": bool(r.unread), "at": r.at, "roles": sorted(set((r.roles or "").split(",")) - {""})}))
            elif box in ("pending", "done"):
                items.append(self._row(r, {
                    "task_id": r.task_id, "kind": r.kind, "instruction": r.instruction, "due_at": r.due_at,
                    "overdue": bool(box == "pending" and r.due_at and r.due_at < now), "task_from": r.task_from,
                    "at": r.at, "done_at": r.done_at, "result_note": r.result_note,
                }))
            else:
                items.append(self._row(r, {"at": r.sent_at}))
        return {"items": items, "total": total, "page": page, "page_size": PAGE_SIZE}

    async def counters(self, employee_id: int) -> dict:
        """شمارنده‌ها فقط از نامه‌هایی که خود شخص به آن‌ها دسترسی دارد."""
        unread = (await self.db.execute(
            select(func.count(func.distinct(OaLetterAccess.letter_id)))
            .select_from(OaLetterAccess)
            .join(OaLetter, OaLetter.id == OaLetterAccess.letter_id)
            .where(OaLetterAccess.employee_id == employee_id, OaLetterAccess.revoked_at.is_(None),
                   OaLetterAccess.read_at.is_(None), OaLetterAccess.source.in_(("recipient", "cc", "referral")),
                   OaLetter.status.in_(("dispatched", "closed")))
        )).scalar_one()
        now = _now()
        pending, overdue = (await self.db.execute(
            select(func.count(OaTask.id), func.count(OaTask.id).filter(and_(OaTask.due_at.is_not(None), OaTask.due_at < now)))
            .select_from(OaTask)
            .join(OaLetter, OaLetter.id == OaTask.letter_id)
            .where(OaTask.assignee_employee_id == employee_id, OaTask.status == "open",
                   OaLetter.status.in_(("dispatched", "closed")))
        )).one()
        return {"unread": unread, "pending": pending, "overdue": overdue}

    # ================= تنظیمات اعلان شخصی =================

    async def get_prefs(self, user: User) -> dict:
        me = await self._me(user)
        pref = await self.db.get(OaNotificationPref, me.id)
        disabled = set(pref.disabled_events or []) if pref else set()
        return {"events": [{"key": k, "label": v, "enabled": k not in disabled} for k, v in PUSH_EVENTS.items()]}

    async def set_prefs(self, user: User, enabled: dict[str, bool]) -> dict:
        me = await self._me(user)
        disabled = sorted(k for k in PUSH_EVENTS if enabled.get(k) is False)
        pref = await self.db.get(OaNotificationPref, me.id)
        if pref is None:
            pref = OaNotificationPref(employee_id=me.id, disabled_events=disabled)
            self.db.add(pref)
        else:
            pref.disabled_events = disabled
            pref.updated_at = _now()
        await self.db.commit()
        return await self.get_prefs(user)

    # ================= پاسخ =================

    async def create_related_draft(self, letter_id: int, user: User, rel_type: str) -> int:
        """
        پیش‌نویس پاسخ به نامه‌ای که کاربر به آن دسترسی دارد: گیرنده = فرستنده‌ی نامه (اگر مجاز باشد)، موضوع
        «پاسخ: …». نامه‌ی محرمانه → پیش‌نویس هم محرمانه. رابطه هیچ دسترسی‌ای به نامه‌ی مرجع نمی‌دهد.
        """
        from app.services.oa_letter_service import OaLetterError, OaLetterService

        if rel_type not in RELATION_TYPES:
            raise OaCartableError("نوع ارتباط نامعتبر است")
        letter, me, _, _ = await self._letter_for(letter_id, user, "view")
        src = await self.db.get(OaLetterVersion, letter.current_version_id)
        try:
            draft = await OaLetterService(self.db).create_draft(paper_size=src.paper_size, template_id=None, user=user)
        except OaLetterError as e:
            raise OaCartableError(str(e), e.status_code) from None
        new = await self.db.get(OaLetter, draft["id"])
        v = await self.db.get(OaLetterVersion, new.current_version_id)
        prefix = "پاسخ: "
        subject = (prefix + (src.subject or ""))[:300]
        v.subject = new.subject = subject
        new.confidentiality = letter.confidentiality
        self.db.add(OaLetterRelation(from_letter_id=new.id, to_letter_id=letter.id, type=rel_type, created_by=user.id))
        if rel_type == "reply" and letter.sender_employee_id and letter.sender_employee_id != me.id:
            if letter.sender_employee_id in await self._eligible({letter.sender_employee_id}, user):
                snap = await self._snapshot(letter.sender_employee_id)
                self.db.add(OaRecipient(letter_id=new.id, role="to", employee_id=snap["employee_id"], name_snapshot=snap["name"],
                                        title_snapshot=snap["title"], department_snapshot=snap["department"]))
        new.row_version += 1
        self.files.audit("letter.relate", user, entity="letter", entity_id=new.id, site_id=new.site_id,
                         details={"to": letter.id, "type": rel_type})
        await self.db.commit()
        return new.id

    async def relations_for(self, letter_id: int, employee_id: int | None) -> list[dict]:
        """
        نامه‌های مرتبط (هر دو جهت). موضوع و پیوند فقط وقتی برمی‌گردد که بیننده خودش به آن نامه دسترسی دارد؛ وگرنه فقط نوع
        رابطه (بدون موضوع). پیش‌نویس‌های دیگران نمایش داده نمی‌شوند.
        """
        rows = (await self.db.execute(
            select(OaLetterRelation).where(or_(OaLetterRelation.from_letter_id == letter_id,
                                               OaLetterRelation.to_letter_id == letter_id))
        )).scalars().all()
        out = []
        for r in rows:
            outgoing = r.from_letter_id == letter_id
            other_id = r.to_letter_id if outgoing else r.from_letter_id
            other = await self.db.get(OaLetter, other_id)
            if other is None or other.discarded_at is not None or other.status not in ("dispatched", "closed"):
                continue
            visible = bool(employee_id) and bool((await self.db.execute(
                select(OaLetterAccess.id).where(OaLetterAccess.letter_id == other_id, OaLetterAccess.employee_id == employee_id,
                                                OaLetterAccess.revoked_at.is_(None)).limit(1)
            )).scalar_one_or_none())
            label = RELATION_TYPES.get(r.type, r.type)
            out.append({
                "direction": "outgoing" if outgoing else "incoming",
                "type": r.type,
                "label": (f"این نامه {label} به" if outgoing else f"{label} این نامه"),
                "letter_id": other_id if visible else None,
                "subject": other.subject if visible else None,
                "sent_at": other.sent_at,
            })
        return out

