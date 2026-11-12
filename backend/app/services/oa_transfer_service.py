"""
انتقال کارهای باز افراد ترک‌کار/جابه‌جا (فاز ۳ب، سند مرجع ۴.۳؛ مجوز automation.reassign، سایت‌محور روی سایت فرد قبلی):
- همه‌ی taskهای open فرد قبلی (اقدام، اطلاع، پاراف/تأیید/امضای گردش تأیید) reassigned و task جدید برای جایگزین؛
  دسترسی source=transfer فقط به همان نامه‌ها. مرحله‌ی فعال گردش تأیید به نام جایگزین می‌شود.
- محرمانه بدون افشا: گزارش و فهرست فقط غیرمحرمانه؛ جایگزینِ خودِ انجام‌دهنده محرمانه‌ی بدون دسترسی قبلی را نمی‌گیرد.
- در هر نامه یک یادداشت سامانه (فرد قبلی، جایگزین، انجام‌دهنده، دلیل) برای مشارکت‌کنندگان همان نامه ثبت می‌شود.
- این اختیار مجوز خواندن محتوای محرمانه به انجام‌دهنده نمی‌دهد (ردیف دسترسی برای انجام‌دهنده ساخته نمی‌شود).
"""
from __future__ import annotations

from sqlalchemy import func, or_, select

from app.core import oa_transfer_rules as trules
from app.models.employee import Department, Employee
from app.models.office_automation import (
    OaApprovalStep,
    OaLetter,
    OaLetterAccess,
    OaNote,
    OaTask,
    OaTaskTransfer,
)
from app.models.user import User
from app.services.oa_cartable_service import (
    TASK_LETTER_STATUSES,
    OaCartableError,
    OaCartableService,
    _full_name,
    _now,
    eligible_users_subquery,
)


class OaTransferService(OaCartableService):
    async def _open_tasks_of(self, employee_id: int) -> list[tuple[OaTask, OaLetter]]:
        return list((await self.db.execute(
            select(OaTask, OaLetter).join(OaLetter, OaLetter.id == OaTask.letter_id)
            .where(OaTask.assignee_employee_id == employee_id, OaTask.status == "open",
                   OaLetter.status.in_(TASK_LETTER_STATUSES), OaLetter.discarded_at.is_(None))
            .order_by(OaTask.id)
        )).all())

    async def candidates_from(self, sites: set[int] | None, q: str = "") -> list[dict]:
        """افرادی (فعال یا غیرفعال) در سایت‌های مجاز که کار باز دارند؛ تعداد فقط کارهای غیرمحرمانه."""
        normal = func.count(OaTask.id).filter(OaLetter.confidentiality != "confidential")
        stmt = (
            select(Employee, Department.name, normal.label("normal"))
            .join(OaTask, OaTask.assignee_employee_id == Employee.id)
            .join(OaLetter, OaLetter.id == OaTask.letter_id)
            .outerjoin(Department, Department.id == Employee.department_id)
            .where(OaTask.status == "open", OaLetter.status.in_(TASK_LETTER_STATUSES), OaLetter.discarded_at.is_(None))
            .group_by(Employee.id, Department.name)
            .order_by(Employee.is_active, Employee.last_name, Employee.first_name)
            .limit(200)
        )
        if sites is not None:
            stmt = stmt.where(Employee.site_id.in_(sites or {-1}))
        for word in (q or "").split()[:4]:
            like = f"%{word}%"
            stmt = stmt.where(or_(Employee.first_name.ilike(like), Employee.last_name.ilike(like), Department.name.ilike(like)))
        return [{"employee_id": e.id, "name": _full_name(e), "title": e.position_title, "department": d,
                 "active": bool(e.is_active and e.is_enabled), "normal_open": int(n or 0)}
                for e, d, n in (await self.db.execute(stmt)).all()]

    async def candidates_to(self, sites: set[int] | None, q: str = "") -> list[dict]:
        """جایگزین: فعال + دسترسی اتوماسیون، در سایت‌های مجاز."""
        stmt = (
            select(Employee, Department.name).outerjoin(Department, Department.id == Employee.department_id)
            .where(Employee.is_active.is_(True), Employee.is_enabled.is_(True), Employee.id.in_(eligible_users_subquery()))
            .order_by(Employee.last_name, Employee.first_name).limit(100)
        )
        if sites is not None:
            stmt = stmt.where(Employee.site_id.in_(sites or {-1}))
        for word in (q or "").split()[:4]:
            like = f"%{word}%"
            stmt = stmt.where(or_(Employee.first_name.ilike(like), Employee.last_name.ilike(like),
                                  Employee.position_title.ilike(like), Department.name.ilike(like)))
        return [{"employee_id": e.id, "name": _full_name(e), "title": e.position_title, "department": d}
                for e, d in (await self.db.execute(stmt)).all()]

    async def preview(self, sites: set[int] | None, from_id: int) -> dict:
        person = await self._in_sites(from_id, sites)
        items = await self._open_tasks_of(person.id)
        return {
            "person": {"employee_id": person.id, "name": _full_name(person), "active": bool(person.is_active and person.is_enabled)},
            "items": [{"letter_id": letter.id, "subject": letter.subject, "number": letter.official_number,
                       "kind": t.kind, "due_at": t.due_at, "created_at": t.created_at}
                      for t, letter in items if letter.confidentiality != "confidential"],
            "note": trules.CONFIDENTIAL_MOVED_NOTE,
        }

    async def _in_sites(self, employee_id: int, sites: set[int] | None) -> Employee:
        e = await self.db.get(Employee, employee_id)
        if e is None or (sites is not None and e.site_id not in sites):
            raise OaCartableError("پرسنل یافت نشد یا خارج از سایت‌های مجاز شماست", 404)
        return e

    async def transfer(self, user: User, sites: set[int] | None, from_id: int, to_id: int, reason: str) -> dict:
        try:
            reason = trules.check_request(from_id, to_id, reason)
        except trules.TransferRulesError as e:
            raise OaCartableError(str(e)) from None
        src = await self._in_sites(from_id, sites)
        dst = await self._in_sites(to_id, sites)
        ok = (await self.db.execute(
            select(Employee.id).where(Employee.id == dst.id, Employee.is_active.is_(True), Employee.is_enabled.is_(True),
                                      Employee.id.in_(eligible_users_subquery()))
        )).scalar_one_or_none()
        if not ok:
            raise OaCartableError("جایگزین باید فعال و دارای دسترسی اتوماسیون اداری باشد")
        performer_id = user.employee_id
        items = await self._open_tasks_of(src.id)
        prior = set()
        if performer_id:
            prior = set((await self.db.execute(
                select(OaLetterAccess.letter_id).where(OaLetterAccess.employee_id == performer_id,
                                                       OaLetterAccess.revoked_at.is_(None))
            )).scalars().all())
        decision = trules.plan(
            [{"id": t.id, "letter_id": letter.id, "confidential": letter.confidentiality == "confidential",
              "subject": letter.subject, "number": letter.official_number, "kind": t.kind} for t, letter in items],
            performer_id=performer_id, to_id=dst.id, prior_access=prior,
        )
        move = set(decision["move"])
        now = _now()
        performer_name = None
        if performer_id:
            pe = await self.db.get(Employee, performer_id)
            performer_name = _full_name(pe) if pe else None
        performer_name = performer_name or user.username
        dst_snap = await self._snapshot(dst.id)
        record = OaTaskTransfer(from_employee_id=src.id, from_name_snapshot=_full_name(src), to_employee_id=dst.id,
                                to_name_snapshot=dst_snap["name"], site_id=src.site_id, performed_by_user_id=user.id,
                                performed_by_name=performer_name, reason=reason, visible_summary=decision["visible"])
        self.db.add(record)
        await self.db.flush()
        noted: set[int] = set()
        for t, letter in items:
            if t.id not in move:
                continue
            old_rows = (await self.db.execute(
                select(OaLetterAccess).where(OaLetterAccess.letter_id == letter.id, OaLetterAccess.employee_id == src.id,
                                             OaLetterAccess.revoked_at.is_(None))
            )).scalars().all()
            new = OaTask(letter_id=letter.id, parent_task_id=t.parent_task_id, kind=t.kind, origin=t.origin,
                         assignee_employee_id=dst.id, assignee_name_snapshot=dst_snap["name"],
                         assignee_title_snapshot=dst_snap["title"], instruction=t.instruction, due_at=t.due_at,
                         created_by_employee_id=t.created_by_employee_id, created_by_name_snapshot=t.created_by_name_snapshot,
                         transfer_id=record.id)
            self.db.add(new)
            await self.db.flush()
            t.status, t.reassigned_to_task_id, t.transfer_id = "reassigned", new.id, record.id
            t.result_note = f"منتقل شد به {dst_snap['name']}"
            self.db.add(OaLetterAccess(letter_id=letter.id, employee_id=dst.id, source="transfer", can_act=True,
                                       can_refer=any(r.can_refer for r in old_rows), granted_by_user_id=user.id,
                                       reason=f"انتقال کارهای باز از {record.from_name_snapshot}"))
            # مرحله‌ی فعال گردش تأیید به نام جایگزین
            await self._move_approval_step(t, new, dst_snap)
            if letter.id not in noted:
                noted.add(letter.id)
                self.db.add(OaNote(letter_id=letter.id, task_id=new.id, author_employee_id=None, author_name_snapshot="سامانه",
                                   text=f"انتقال کار باز: از {record.from_name_snapshot} به {dst_snap['name']} — "
                                        f"توسط {performer_name} — دلیل: {reason}"))
                self._push(event="transfer", letter=letter, employee_id=dst.id,
                           values={"from": record.from_name_snapshot, "subject": letter.subject}, extra=str(record.id))
        self.files.audit("task.transfer", user, entity="employee", entity_id=src.id, site_id=src.site_id,
                         details={"to": dst.id, "transfer_id": record.id, "visible_count": len(decision["visible"])})
        await self._commit()
        return {"transfer_id": record.id, "moved": decision["visible"], "note": decision["note"], "at": now}

    async def _move_approval_step(self, old: OaTask, new: OaTask, snap: dict) -> None:
        if old.origin != "approval":
            return
        step = (await self.db.execute(select(OaApprovalStep).where(OaApprovalStep.task_id == old.id))).scalar_one_or_none()
        if step is not None and step.status == "active":
            step.approver_employee_id, step.task_id = snap["employee_id"], new.id
            step.approver_name_snapshot, step.approver_title_snapshot = snap["name"], snap["title"]

    async def history(self, sites: set[int] | None) -> list[dict]:
        stmt = select(OaTaskTransfer).order_by(OaTaskTransfer.created_at.desc()).limit(100)
        if sites is not None:
            stmt = stmt.where(OaTaskTransfer.site_id.in_(sites or {-1}))
        return [{"id": r.id, "from": r.from_name_snapshot, "to": r.to_name_snapshot, "by": r.performed_by_name,
                 "reason": r.reason, "at": r.created_at, "visible": r.visible_summary or []}
                for r in (await self.db.execute(stmt)).scalars().all()]
