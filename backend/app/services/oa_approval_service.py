"""
گردش تأیید ترتیبی نامه (فاز ۳ب؛ سند مرجع ۶.۱ و ۶.۴؛ تصمیم ۱۴۰۵/۰۸/۱۲ «امضای مدیر از راه گردش تأیید»):

draft ──ارسال برای تأیید──► in_approval ──(تأیید همه‌ی مراحل به ترتیب)──► dispatched (شماره + تحویل خودکار)
   ▲                              │
   └──── برگشت برای اصلاح / پس گرفتن ────┘   (نامه دوباره پیش‌نویس می‌شود؛ مسیر برای دور بعد کپی می‌شود)

- هر مرحله: یک شخص و یک نوع (پاراف / تأیید / امضا). فقط مرحله‌ی فعال task و دسترسی (source=approver) می‌گیرد.
- «امضا» فقط با امضای فعال خود تأییدکننده؛ هیچ‌کس به نام دیگری امضا نمی‌کند.
- نامه‌ی «از طرف» مدیر (منشی): مرحله‌ی آخر خودکار «امضا»ی خود مدیر است.
- در طول تأیید نسخه قفل است (submitted) و هر تأیید با content_hash همان نسخه ثبت می‌شود.
"""
from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import oa_approval_rules as arules
from app.core import oa_letter_rules as rules
from app.core.oa_version_snapshots import snapshot_recipients, snapshot_approval_plan
from app.models.employee import Employee
from app.models.office_automation import (
    OaApprovalStep,
    OaAttachment,
    OaLetter,
    OaLetterAccess,
    OaLetterVersion,
    OaTask,
)
from app.models.user import User
from app.services.oa_cartable_service import OaCartableError, OaCartableService, _now, eligible_users_subquery


async def has_plan(db: AsyncSession, letter_id: int, round_no: int) -> bool:
    return bool((await db.execute(
        select(OaApprovalStep.id).where(OaApprovalStep.letter_id == letter_id, OaApprovalStep.round == round_no,
                                        OaApprovalStep.status == "planned").limit(1)
    )).scalar_one_or_none())


def _step_out(s: OaApprovalStep, me_id: int | None = None) -> dict:
    return {
        "id": s.id, "round": s.round, "step_no": s.step_no, "kind": s.kind, "kind_label": arules.KINDS.get(s.kind, s.kind),
        "employee_id": s.approver_employee_id, "name": s.approver_name_snapshot, "title": s.approver_title_snapshot,
        "status": s.status, "required": s.required, "note": s.note, "acted_at": s.acted_at, "activated_at": s.activated_at,
        "signed": bool(s.signature_version_id), "mine": bool(me_id and s.approver_employee_id == me_id),
    }


class OaApprovalService(OaCartableService):
    # ---------- مسیر پیش‌نویس ----------

    async def _planned(self, letter: OaLetter) -> list[OaApprovalStep]:
        return list((await self.db.execute(
            select(OaApprovalStep).where(OaApprovalStep.letter_id == letter.id,
                                         OaApprovalStep.round == letter.approval_round + 1,
                                         OaApprovalStep.status == "planned")
            .order_by(OaApprovalStep.step_no)
        )).scalars().all())

    async def plan_out(self, letter: OaLetter) -> dict:
        """مسیر دور بعد برای ویرایشگر + مرحله‌ی خودکار امضای مدیر (نمایشی) + سابقه‌ی دورهای قبل."""
        explicit = [_step_out(s) for s in await self._planned(letter)]
        auto = None
        if letter.principal_employee_id:
            snap = await self._snapshot(letter.principal_employee_id)
            auto = {"employee_id": snap["employee_id"], "name": snap["name"], "title": snap["title"], "kind": "sign",
                    "kind_label": arules.KINDS["sign"], "required": True}
        return {"steps": explicit, "auto_final": auto, "history": await self._history(letter, None)}

    async def _history(self, letter: OaLetter, me_id: int | None) -> list[dict]:
        rows = (await self.db.execute(
            select(OaApprovalStep).where(OaApprovalStep.letter_id == letter.id, OaApprovalStep.status != "planned")
            .order_by(OaApprovalStep.round, OaApprovalStep.step_no)
        )).scalars().all()
        return [_step_out(s, me_id) for s in rows]

    async def set_plan(self, letter_id: int, user: User, steps: list[dict]) -> dict:
        letter = await self._own_draft(letter_id, user, lock=True)
        me = await self._me(user)
        try:
            plan = arules.clean_plan(steps, author_id=me.id, principal_id=letter.principal_employee_id)
        except arules.ApprovalRulesError as e:
            raise OaCartableError(str(e)) from None
        ids = {s["employee_id"] for s in plan}
        if ids - await self._eligible(ids, user):
            raise OaCartableError("یک یا چند نفر از مسیر تأیید مجاز نیستند (غیرفعال، بدون دسترسی اتوماسیون یا خارج از سایت‌های شما)")
        await self.db.execute(delete(OaApprovalStep).where(
            OaApprovalStep.letter_id == letter.id, OaApprovalStep.round == letter.approval_round + 1,
            OaApprovalStep.status == "planned"))
        for i, s in enumerate(plan, start=1):
            snap = await self._snapshot(s["employee_id"])
            self.db.add(OaApprovalStep(letter_id=letter.id, round=letter.approval_round + 1, step_no=i, kind=s["kind"],
                                       approver_employee_id=s["employee_id"], approver_name_snapshot=snap["name"],
                                       approver_title_snapshot=snap["title"], status="planned"))
        await self._commit()
        return await self.plan_out(letter)

    async def _copy_plan_to_next_round(self, letter: OaLetter, steps: list[OaApprovalStep]) -> None:
        """بعد از برگشت/پس گرفتن: مسیر همین دور (بدون مرحله‌ی خودکار مدیر) برای دور بعد آماده می‌شود."""
        for i, s in enumerate([x for x in steps if not x.required], start=1):
            self.db.add(OaApprovalStep(letter_id=letter.id, round=letter.approval_round + 1, step_no=i, kind=s.kind,
                                       approver_employee_id=s.approver_employee_id, approver_name_snapshot=s.approver_name_snapshot,
                                       approver_title_snapshot=s.approver_title_snapshot, status="planned"))

    # ---------- ارسال برای تأیید ----------

    async def submit(self, letter_id: int, user: User, row_version: int) -> int:
        letter = (await self.db.execute(select(OaLetter).where(OaLetter.id == letter_id).with_for_update())).scalar_one_or_none()
        if letter is None or letter.discarded_at is not None or letter.created_by != user.id:
            raise OaCartableError("پیش‌نویس یافت نشد", 404)
        if letter.status == "in_approval":
            return letter.id  # کلیک دوباره
        if letter.status != "draft":
            raise OaCartableError("این نامه قابل ارسال برای تأیید نیست", 409)
            planned.remove(s)
        for i, s in enumerate(planned, start=1):
            s.step_no = i
        plan = arules.effective_plan([{"employee_id": s.approver_employee_id, "kind": s.kind} for s in planned],
                                     letter.principal_employee_id)
        if not plan:
            raise OaCartableError("مسیر تأیید خالی است؛ برای ارسال مستقیم از «ارسال» استفاده کنید")
        ctx = await self._validate_for_send(letter, user)
        error = await self._numbering_error(letter.site_id)
        if error:
            raise OaCartableError(error, 409)
        ids = {p["employee_id"] for p in plan}
        active_ok = set((await self.db.execute(
            select(Employee.id).where(Employee.id.in_(ids), Employee.is_active.is_(True), Employee.is_enabled.is_(True),
                                      Employee.id.in_(eligible_users_subquery()))
        )).scalars().all())
        if ids - active_ok:
            raise OaCartableError("یکی از افراد مسیر تأیید دیگر فعال یا دارای دسترسی اتوماسیون نیست؛ مسیر را اصلاح کنید")

        now = _now()
        v, recipients, att_files = ctx["v"], ctx["recipients"], ctx["att_files"]
        v.status = "submitted"
        v.content_hash = rules.content_hash(
            subject=v.subject, body_html=v.body_html, paper_size=v.paper_size, template_version_id=v.template_version_id,
            recipients=[f"{r.role}:{r.employee_id}" for r in recipients], attachments=[f.sha256 for f in att_files],
        )
        # Capture exactly what the approvers will review, before freezing the submitted round.
        v.recipients_snapshot = snapshot_recipients(recipients)
        v.approval_plan_snapshot = snapshot_approval_plan(planned)
        if letter.principal_employee_id:
            principal = await self._snapshot(letter.principal_employee_id)
            v.approval_plan_snapshot.append({
                "step_no": len(planned) + 1,
                "employee_id": principal["employee_id"],
                "name": principal["name"], "title": principal["title"],
                "kind": "sign", "required": True,
            })
        letter.approval_round += 1
        letter.status, letter.submitted_at = "in_approval", now
        letter.row_version += 1
        # مراحل صریح این دور planned → pending؛ امضای خودکار مدیر اضافه می‌شود
        for s in planned:
            s.status = "pending"
        if letter.principal_employee_id:
            snap = await self._snapshot(letter.principal_employee_id)
            self.db.add(OaApprovalStep(letter_id=letter.id, round=letter.approval_round, step_no=len(planned) + 1,
                                       kind="sign", approver_employee_id=snap["employee_id"], approver_name_snapshot=snap["name"],
                                       approver_title_snapshot=snap["title"], status="pending", required=True))
        await self.db.flush()
        me = ctx["me"]
        exists = (await self.db.execute(
            select(OaLetterAccess.id).where(OaLetterAccess.letter_id == letter.id, OaLetterAccess.employee_id == me.id,
                                            OaLetterAccess.source == "creator").limit(1)
        )).scalar_one_or_none()
        if not exists:
            self.db.add(OaLetterAccess(letter_id=letter.id, employee_id=me.id, source="creator",
                                       granted_by_user_id=user.id, read_at=now))
        for f in att_files:
            f.state = "permanent"
        steps = await self._round_steps(letter)
        await self._activate(letter, steps[0], me)
        self.files.audit("letter.submit", user, entity="letter", entity_id=letter.id, site_id=letter.site_id,
                         details={"round": letter.approval_round, "steps": len(steps)})
        await self._commit()
        return letter.id

    async def _round_steps(self, letter: OaLetter) -> list[OaApprovalStep]:
        return list((await self.db.execute(
            select(OaApprovalStep).where(OaApprovalStep.letter_id == letter.id, OaApprovalStep.round == letter.approval_round)
            .order_by(OaApprovalStep.step_no)
        )).scalars().all())

    async def _activate(self, letter: OaLetter, step: OaApprovalStep, author: Employee) -> None:
        now = _now()
        step.status, step.activated_at = "active", now
        has_row = (await self.db.execute(
            select(OaLetterAccess.id).where(OaLetterAccess.letter_id == letter.id,
                                            OaLetterAccess.employee_id == step.approver_employee_id,
                                            OaLetterAccess.source == "approver", OaLetterAccess.revoked_at.is_(None)).limit(1)
        )).scalar_one_or_none()
        if not has_row:
            self.db.add(OaLetterAccess(letter_id=letter.id, employee_id=step.approver_employee_id, source="approver",
                                       can_act=True, granted_by_employee_id=author.id))
        task = OaTask(letter_id=letter.id, kind=step.kind, origin="approval", assignee_employee_id=step.approver_employee_id,
                      assignee_name_snapshot=step.approver_name_snapshot, assignee_title_snapshot=step.approver_title_snapshot,
                      instruction=f"{arules.ACTION_LABELS[step.kind]} نامه", created_by_employee_id=author.id,
                      created_by_name_snapshot=f"{author.first_name} {author.last_name}")
        self.db.add(task)
        await self.db.flush()
        step.task_id = task.id
        subject = (await self.db.get(OaLetterVersion, letter.current_version_id)).subject
        self._push(event="approval", letter=letter, employee_id=step.approver_employee_id,
                   values={"sender": task.created_by_name_snapshot, "subject": subject,
                           "action": arules.ACTION_LABELS[step.kind]}, extra=f"{letter.approval_round}:{step.step_no}")

    # ---------- اقدام تأییدکننده ----------

    async def _my_active_step(self, step_id: int, user: User) -> tuple[OaApprovalStep, OaLetter, Employee]:
        me = await self._me(user)
        step = await self.db.get(OaApprovalStep, step_id)
        if step is None or step.approver_employee_id != me.id:
            raise OaCartableError("مرحله‌ی تأیید یافت نشد", 404)
        letter = (await self.db.execute(select(OaLetter).where(OaLetter.id == step.letter_id).with_for_update())).scalar_one()
        await self.db.refresh(step)
        if letter.status != "in_approval" or step.round != letter.approval_round or step.status != "active":
            raise OaCartableError("این مرحله دیگر در نوبت شما نیست (ممکن است نامه پس گرفته یا قبلاً تأیید شده باشد)", 409)
        return step, letter, me

    async def _close_task(self, step: OaApprovalStep, user: User, note: str | None) -> None:
        if step.task_id:
            task = await self.db.get(OaTask, step.task_id)
            if task is not None and task.status == "open":
                task.status, task.result_note, task.done_at, task.acted_by_user_id = "done", note, _now(), user.id

    async def approve(self, step_id: int, user: User, note: str | None) -> dict:
        step, letter, me = await self._my_active_step(step_id, user)
        v = await self.db.get(OaLetterVersion, letter.current_version_id)
        note = (note or "").strip()[:2000] or None
        if step.kind == "sign":
            from app.services.oa_signature_service import OaSignatureService

            sig = await OaSignatureService(self.db).active_for(me.id)
            if sig is None:
                raise OaCartableError("امضای فعال ندارید؛ اول از پنل کاربری ← امضای من امضا ثبت کنید")
            step.signature_version_id = sig.id
            snap = await self._snapshot(me.id)
            step.approver_name_snapshot, step.approver_title_snapshot = snap["name"], snap["title"]  # نام و سمت لحظه‌ی امضا
        step.status, step.acted_at, step.note, step.acted_by_user_id = "approved", _now(), note, user.id
        step.content_hash = v.content_hash
        await self._close_task(step, user, note)
        self.files.audit(f"approval.{step.kind}", user, entity="letter", entity_id=letter.id, site_id=letter.site_id,
                         details={"round": step.round, "step": step.step_no, "content_hash": v.content_hash})
        steps = await self._round_steps(letter)
        idx = arules.next_index([s.status for s in steps])
        author = await self.db.get(Employee, letter.creator_employee_id)
        if idx is not None:
            await self._activate(letter, steps[idx], author)
            await self._commit()
            return {"letter_id": letter.id, "dispatched": False}
        # آخرین مرحله: ثبت و ارسال خودکار به نام نویسنده (یا مدیر، در نامه‌ی «از طرف»)
        letter.status = "approved"
        creator = await self.db.get(User, letter.created_by)
        if creator is None:
            raise OaCartableError("حساب نویسنده‌ی نامه دیگر وجود ندارد؛ ارسال خودکار ممکن نیست", 409)
        ctx = await self._validate_for_send(letter, creator)
        await self._dispatch(letter, creator, ctx)
        return {"letter_id": letter.id, "dispatched": True}

    async def return_for_changes(self, step_id: int, user: User, note: str) -> dict:
        try:
            note = arules.check_return_note(note)
        except arules.ApprovalRulesError as e:
            raise OaCartableError(str(e)) from None
        step, letter, me = await self._my_active_step(step_id, user)
        step.status, step.acted_at, step.note, step.acted_by_user_id = "returned", _now(), note, user.id
        await self._close_task(step, user, note)
        steps = await self._round_steps(letter)
        await self._back_to_draft(letter, steps)
        subject = (await self.db.get(OaLetterVersion, letter.current_version_id)).subject
        self._push(event="returned", letter=letter, employee_id=letter.creator_employee_id,
                   values={"by": step.approver_name_snapshot, "subject": subject}, extra=f"{letter.approval_round}")
        self.files.audit("approval.return", user, entity="letter", entity_id=letter.id, site_id=letter.site_id,
                         details={"round": step.round, "step": step.step_no})
        await self._commit()
        return {"letter_id": letter.id}

    async def _back_to_draft(self, letter: OaLetter, steps: list[OaApprovalStep]) -> None:
        for s in steps:
            if s.status in ("pending", "active"):
                s.status = "cancelled"
                if s.task_id:
                    await self.db.execute(update(OaTask).where(OaTask.id == s.task_id, OaTask.status == "open")
                                          .values(status="cancelled"))
        # Never unlock the version which an approver signed/reviewed.  Create an editable
        # successor; the original content hash, status and attachment rows remain immutable.
        previous = await self.db.get(OaLetterVersion, letter.current_version_id)
        if previous is None or previous.status != "submitted":
            raise OaCartableError("نسخه‌ی ارسال‌شده برای تأیید پیدا نشد", 409)
        version = OaLetterVersion(
            letter_id=letter.id, version_no=previous.version_no + 1,
            subject=previous.subject, body_html=previous.body_html,
            paper_size=previous.paper_size, template_version_id=previous.template_version_id,
            content_hash=previous.content_hash, status="editing", created_by=letter.created_by,
        )
        self.db.add(version)
        await self.db.flush()
        prior_files = (await self.db.execute(
            select(OaAttachment).where(OaAttachment.letter_version_id == previous.id)
            .order_by(OaAttachment.sort_order, OaAttachment.id)
        )).scalars().all()
        for a in prior_files:
            self.db.add(OaAttachment(
                letter_version_id=version.id, file_id=a.file_id,
                sort_order=a.sort_order, description=a.description, added_by=a.added_by,
            ))
        letter.current_version_id = version.id
        letter.status = "draft"
        letter.row_version += 1
        await self._copy_plan_to_next_round(letter, steps)

    async def withdraw(self, letter_id: int, user: User) -> dict:
        letter = (await self.db.execute(select(OaLetter).where(OaLetter.id == letter_id).with_for_update())).scalar_one_or_none()
        if letter is None or letter.created_by != user.id:
            raise OaCartableError("نامه یافت نشد", 404)
        if letter.status != "in_approval":
            raise OaCartableError("فقط نامه‌ای که در انتظار تأیید است پس گرفته می‌شود", 409)
        await self._back_to_draft(letter, await self._round_steps(letter))
        self.files.audit("approval.withdraw", user, entity="letter", entity_id=letter.id, site_id=letter.site_id,
                         details={"round": letter.approval_round})
        await self._commit()
        return {"letter_id": letter.id}

    # ---------- نمایش در صفحه‌ی نامه ----------

    async def letter_approval(self, letter: OaLetter, me_id: int, user: User) -> dict | None:
        if letter.approval_round == 0:
            return None
        current = [s for s in await self._history(letter, me_id) if s["round"] == letter.approval_round]
        mine = next((s for s in current if s["mine"] and s["status"] == "active"), None)
        my_has_signature = False
        if mine and mine["kind"] == "sign":
            from app.services.oa_signature_service import OaSignatureService

            my_has_signature = await OaSignatureService(self.db).active_for(me_id) is not None
        return {
            "round": letter.approval_round,
            "steps": current,
            "history": [s for s in await self._history(letter, me_id) if s["round"] < letter.approval_round],
            "my_step": mine,
            "my_has_signature": my_has_signature,
            "can_withdraw": letter.status == "in_approval" and letter.created_by == user.id,
        }

    async def approval_signatures(self, letter: OaLetter) -> list[OaApprovalStep]:
        """امضاهای مراحل «امضا»ی تأییدشده‌ی دور آخر (برای چاپ روی نامه)."""
        return list((await self.db.execute(
            select(OaApprovalStep).where(OaApprovalStep.letter_id == letter.id, OaApprovalStep.round == letter.approval_round,
                                         OaApprovalStep.status == "approved", OaApprovalStep.signature_version_id.is_not(None))
            .order_by(OaApprovalStep.step_no)
        )).scalars().all())

