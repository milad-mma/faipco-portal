"""
سرویس ماژول «درخواست مساعده» (Migration 114؛ docs/advances.md).

جریان: پرسنل در بازه‌ی مجاز ماه درخواست می‌دهد (مبلغ ثابت از پله‌ی سابقه‌اش) ← مدیر واحد (تأییدکننده‌ی مرخصی) ←
مدیر سایت مساعده (تنظیمات) ← واحد مالی (advances.finance) تأیید ← مالی «ثبت پرداخت». هر مرحله می‌تواند رد کند (با دلیل).
تصمیم‌ها گروهی هم ممکن است (فهرست شناسه‌ها؛ هر درخواست جدا بررسی می‌شود و نتیجه‌ی هر کدام برمی‌گردد).

سابقه و مدیر واحد از همان قواعد وام (LoanService.service_info / resolve_unit_manager) خوانده می‌شود تا یک تعریف
در کل پرتال باشد. اعلان‌ها بعد از commit و با متن قابل‌ویرایش هر سایت (notification_templates، ماژول «advance») فرستاده می‌شود.
"""
from __future__ import annotations

import logging

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import advance_rules as R
from app.core.persian_date import get_current_jalali_date
from app.models.advance import AdvanceGroupMember, AdvanceRequest, AdvanceRequestEvent, AdvanceSettings, AdvanceTier
from app.models.employee import Employee
from app.models.site import Site
from app.models.user import User
from app.services import kara_substitute, notification_templates
from app.services.loan_service import (
    LoanService,
    _clean,
    _now,
    _schedule_push,
    _strip_codes,
    _today,
    employee_label,
)

logger = logging.getLogger(__name__)

INBOX_URL = "/advances?tab=inbox"
MINE_URL = "/advances?tab=mine"


class AdvanceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class AdvanceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._pushes: list[tuple[set, str, int, str, dict]] = []
        self._loans = LoanService(db)

    # ---------- کمکی ----------

    def _push(self, employee_ids, url: str, site_id: int, key: str, **values) -> None:
        self._pushes.append((set(employee_ids), url, site_id, key, values))

    async def _commit(self) -> None:
        await self.db.commit()
        pushes, self._pushes = self._pushes, []
        for ids, url, site_id, key, values in pushes:
            _schedule_push(ids, url, await notification_templates.render(self.db, site_id, key, **values))

    def _event(self, req: AdvanceRequest, action: str, actor: str | None, user_id: int | None = None, note=None) -> None:
        req.events.append(
            AdvanceRequestEvent(action=action, actor_label=actor, actor_user_id=user_id, note=_clean(note), created_at=_now())
        )

    async def settings(self, site_id: int, *, create: bool = False) -> AdvanceSettings | None:
        row = (await self.db.execute(select(AdvanceSettings).where(AdvanceSettings.site_id == site_id))).scalar_one_or_none()
        if row is None and create:
            row = AdvanceSettings(site_id=site_id, is_enabled=False, window_from_day=1, window_to_day=31, max_per_month=1)
            self.db.add(row)
            await self.db.flush()
        return row

    async def is_site_enabled(self, site_id: int) -> bool:
        st = await self.settings(site_id)
        return bool(st and st.is_enabled)

    async def tiers(self, site_id: int) -> list[dict]:
        rows = (
            await self.db.execute(
                select(AdvanceTier).where(AdvanceTier.site_id == site_id).order_by(AdvanceTier.group, AdvanceTier.min_months)
            )
        ).scalars().all()
        return [
            {"id": t.id, "group": t.group, "min_months": t.min_months, "amount": t.amount, "min_amount": t.min_amount}
            for t in rows
        ]

    async def members(self, site_id: int) -> list[dict]:
        """تعیین‌های دستی گروه (مدیر / سرپرست) این سایت با نام پرسنل."""
        rows = (
            await self.db.execute(select(AdvanceGroupMember).where(AdvanceGroupMember.site_id == site_id))
        ).scalars().all()
        people = await self._names([m.employee_id for m in rows])
        out = [
            {"employee_id": m.employee_id, "group": m.group, "label": employee_label(people.get(m.employee_id))}
            for m in rows
        ]
        return sorted(out, key=lambda m: (m["group"], m["label"] or ""))

    async def employee_group(self, employee: Employee) -> str:
        """
        گروه مساعده‌ی یک پرسنل: تعیین دستی (مدیر/سرپرست) مقدم است؛ وگرنه اگر سرپرست دست‌کم یک واحد باشد (همان
        تأییدکننده‌ی مرخصی) «سرپرستان»؛ وگرنه «پرسنل».
        """
        from app.services.my_staff_service import is_supervisor

        manual = (
            await self.db.execute(
                select(AdvanceGroupMember.group).where(AdvanceGroupMember.employee_id == employee.id)
            )
        ).scalar_one_or_none()
        if manual in R.GROUPS:
            return manual
        try:
            if await is_supervisor(self.db, employee):
                return R.GROUP_SUPERVISOR
        except Exception:  # noqa: BLE001 - خطای کاراوب نباید ثبت درخواست را از کار بیندازد
            logger.exception("تشخیص سرپرست برای مساعده ناموفق بود")
        return R.GROUP_STAFF

    async def _load(self, request_id: int, *, lock: bool = False) -> AdvanceRequest:
        stmt = select(AdvanceRequest).options(selectinload(AdvanceRequest.events)).where(AdvanceRequest.id == request_id)
        if lock:
            stmt = stmt.with_for_update(of=AdvanceRequest).execution_options(populate_existing=True)
        req = (await self.db.execute(stmt)).scalar_one_or_none()
        if req is None:
            raise AdvanceError("درخواست مساعده پیدا نشد", 404)
        return req

    @staticmethod
    def current_step(req: AdvanceRequest) -> str | None:
        if req.status not in (R.STATUS_IN_REVIEW, R.STATUS_WAITING_FINANCE):
            return None
        steps = req.steps or [R.STEP_FINANCE]
        return steps[min(req.step_index, len(steps) - 1)]

    async def _enter_step(self, req: AdvanceRequest) -> None:
        """درخواست را در مرحله‌ی step_index قرار می‌دهد و اعلان مرحله را صف می‌کند."""
        step = (req.steps or [R.STEP_FINANCE])[min(req.step_index, len(req.steps or [1]) - 1)]
        if step == R.STEP_FINANCE:
            req.status = R.STATUS_WAITING_FINANCE
            req.current_approver_employee_id = None
            self._push([req.employee_id], MINE_URL, req.site_id, "advance.to_finance")
            return
        req.status = R.STATUS_IN_REVIEW
        approver = req.unit_manager_employee_id if step == R.STEP_UNIT_MANAGER else req.site_manager_employee_id
        approver = await self._usable_approver(req, step, approver)
        req.current_approver_employee_id = approver
        # جانشین فعال او در کاراوب هم (اگر برای سایت روشن است)
        substitute = await kara_substitute.substitute_of(self.db, AdvanceSettings, req.site_id, approver)
        targets = [approver] + ([substitute] if substitute and substitute != req.employee_id else [])
        self._push(targets, INBOX_URL, req.site_id, "advance.approver_pending")

    async def _approval_condition(self, employee: Employee):
        """مثل LoanService._approval_condition: خودش یا مدیری که جانشین فعال اوست (سایت‌های روشن)، به‌جز درخواست خودش."""
        scope = await kara_substitute.substitute_scope(self.db, AdvanceSettings, employee.id)
        conditions = [AdvanceRequest.current_approver_employee_id == employee.id]
        for site_id, managers in scope.items():
            conditions.append(
                (AdvanceRequest.site_id == site_id)
                & AdvanceRequest.current_approver_employee_id.in_(managers)
                & (AdvanceRequest.employee_id != employee.id)
            )
        return or_(*conditions), scope

    # ---------- نمایش ----------

    async def serialize_many(self, reqs: list[AdvanceRequest], *, public: bool) -> list[dict]:
        """چند درخواست را با یک بار بارگذاری نام‌ها تبدیل می‌کند. public=True: بدون کد پرسنلی همکاران."""
        ids = set()
        for r in reqs:
            ids.update(
                [r.employee_id, r.unit_manager_employee_id, r.site_manager_employee_id, r.current_approver_employee_id]
            )
        people = await self._names(ids)
        return [self._to_dict(r, people, public) for r in reqs]

    async def _names(self, ids) -> dict[int, Employee]:
        """پرسنل با واحدشان (برای نمایش نام/واحد بدون بارگذاری تنبل)."""
        ids = {i for i in ids if i}
        if not ids:
            return {}
        rows = (
            await self.db.execute(
                select(Employee).options(selectinload(Employee.department)).where(Employee.id.in_(ids))
            )
        ).scalars().all()
        return {e.id: e for e in rows}

    async def serialize(self, req: AdvanceRequest, *, public: bool) -> dict:
        return (await self.serialize_many([req], public=public))[0]

    def _to_dict(self, req: AdvanceRequest, people: dict, public: bool) -> dict:
        def label(emp):
            return employee_label(emp, code=not public)

        step = self.current_step(req)
        emp = people.get(req.employee_id)
        person_of = {R.STEP_UNIT_MANAGER: req.unit_manager_employee_id, R.STEP_SITE_MANAGER: req.site_manager_employee_id}
        return {
            "id": req.id,
            "site_id": req.site_id,
            "employee_id": req.employee_id,
            "employee": label(emp),
            "department": emp.department.name if emp is not None and emp.department else None,
            "amount": req.amount,
            "employee_group": req.employee_group,
            "group_label": R.GROUP_LABELS.get(req.employee_group, req.employee_group),
            "service_months": req.service_months,
            "reason": req.reason,
            "request_month": req.request_month,
            "status": req.status,
            "status_label": R.status_label(req.status, step),
            "current_step": step,
            "current_approver": label(people.get(req.current_approver_employee_id)),
            "steps": [
                {
                    "key": key,
                    "label": R.STEP_LABELS.get(key, key),
                    "state": (
                        "done"
                        if i < req.step_index or req.status in (R.STATUS_APPROVED, R.STATUS_PAID)
                        else ("current" if i == req.step_index and req.status in R.OPEN_STATUSES else "todo")
                    ),
                    "person": label(people.get(person_of.get(key))),
                }
                for i, key in enumerate(req.steps or [])
            ],
            "paid_date": req.paid_date,
            "paid_note": req.paid_note,
            "created_at": req.created_at.isoformat() if req.created_at else None,
            "decided_at": req.decided_at.isoformat() if req.decided_at else None,
            "events": [  # همان شکل تاریخچه‌ی وام تا LoanHistory فرانت مشترک باشد
                {
                    "action": e.action,
                    "actor": _strip_codes(e.actor_label) if public else e.actor_label,
                    "note": _strip_codes(e.note) if public else e.note,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in (req.events or [])
            ],
        }

    # ---------- پرسنل ----------

    async def _month_count(self, employee_id: int, month: str) -> int:
        return (
            await self.db.execute(
                select(func.count(AdvanceRequest.id)).where(
                    AdvanceRequest.employee_id == employee_id,
                    AdvanceRequest.request_month == month,
                    AdvanceRequest.status.in_(R.COUNTED_STATUSES),
                )
            )
        ).scalar_one()

    async def my_overview(self, employee: Employee) -> dict:
        """وضعیت فعلی برای صفحه‌ی پرسنل: فعال بودن، بازه، مبلغ قابل درخواست، امکان ثبت الان و درخواست‌های من."""
        st = await self.settings(employee.site_id)
        enabled = bool(st and st.is_enabled)
        service = await self._loans.service_info(employee)
        group = await self.employee_group(employee) if enabled else R.GROUP_STAFF
        tiers = R.group_tiers(await self.tiers(employee.site_id), group) if enabled else []
        tier = R.tier_for(service["months"], tiers)
        amount = int(tier["amount"]) if tier else None
        amount_mode = st.amount_mode if st and st.amount_mode in R.AMOUNT_MODES else R.AMOUNT_FIXED
        amount_step = st.amount_step if st else None
        bounds = R.amount_range(tier, amount_step) if tier and amount_mode == R.AMOUNT_RANGE else None
        y, m, d = get_current_jalali_date()
        month = R.request_month((y, m, d), st.window_from_day, st.window_to_day) if st else R.month_key((y, m, d))
        reasons: list[str] = []
        if not enabled:
            reasons.append("درخواست مساعده برای سایت شما فعال نیست.")
        else:
            if not R.in_window(d, st.window_from_day, st.window_to_day):
                reasons.append(f"ثبت درخواست فقط {R.window_label(st.window_from_day, st.window_to_day)} ممکن است.")
            if amount is None:
                reasons.append("با سابقه‌ی فعلی شما هنوز مبلغی برای مساعده تعریف نشده است.")
            elif amount_mode == R.AMOUNT_RANGE and bounds is None:
                reasons.append("محدوده‌ی مبلغ برای سابقه‌ی شما درست تعریف نشده است؛ با واحد مالی هماهنگ کنید.")
            # شروع به کار در همین ماه: از ابتدای ماه بعد (تاریخ استخدام دوره‌ی فعلی، نه سابقه‌ی اصلاح‌شده)
            hire_block = R.hire_month_block(employee.hire_date_jalali, (y, m, d))
            if hire_block:
                reasons.append(hire_block)
            used = await self._month_count(employee.id, month)
            if used >= st.max_per_month:
                reasons.append(
                    "در این ماه به سقف تعداد درخواست رسیده‌اید."
                    if st.max_per_month > 1
                    else "در این ماه قبلاً درخواست مساعده ثبت کرده‌اید."
                )
            open_req = (
                await self.db.execute(
                    select(AdvanceRequest.id).where(
                        AdvanceRequest.employee_id == employee.id, AdvanceRequest.status.in_(R.OPEN_STATUSES)
                    )
                )
            ).first()
            if open_req:
                reasons.append("یک درخواست باز دارید؛ تا تعیین تکلیف آن درخواست جدید ممکن نیست.")
        mine = (
            await self.db.execute(
                select(AdvanceRequest)
                .options(selectinload(AdvanceRequest.events))
                .where(AdvanceRequest.employee_id == employee.id)
                .order_by(AdvanceRequest.id.desc())
                .limit(24)
            )
        ).scalars().all()
        return {
            "enabled": enabled,
            "window_label": R.window_label(st.window_from_day, st.window_to_day) if st else None,
            "max_per_month": st.max_per_month if st else None,
            "rules_text": st.rules_text if st else None,
            "service": service,
            "group": group,
            "group_label": R.GROUP_LABELS[group],
            "amount": amount,
            "amount_mode": amount_mode,
            "amount_min": bounds[0] if bounds else None,
            "amount_max": bounds[1] if bounds else None,
            "amount_step": amount_step,
            "tiers": tiers,
            "current_month": month,
            "can_submit": enabled and not reasons,
            "block_reasons": reasons,
            "requests": await self.serialize_many(list(mine), public=True),
        }

    async def submit(self, employee: Employee, user: User, reason: str | None, amount: int | None = None) -> dict:
        if not (employee.is_active and employee.is_enabled):
            raise AdvanceError("حساب پرسنلی شما فعال نیست", 403)
        # قفل ردیف پرسنل تا دو ثبت هم‌زمان (دو کلیک/دو تب) هر دو از بررسی «درخواست باز/دفعات ماه» رد نشوند
        await self.db.execute(select(Employee.id).where(Employee.id == employee.id).with_for_update())
        overview = await self.my_overview(employee)
        if not overview["can_submit"]:
            raise AdvanceError(" ".join(overview["block_reasons"]) or "ثبت درخواست ممکن نیست")
        st = await self.settings(employee.site_id)
        final_amount = overview["amount"]
        if overview["amount_mode"] == R.AMOUNT_RANGE:
            tier = R.tier_for(overview["service"]["months"], overview["tiers"])
            try:
                final_amount = R.validate_requested_amount(amount, tier, overview["amount_step"])
            except R.AdvanceRuleError as e:
                raise AdvanceError(str(e)) from e
        unit_manager_id = await self._loans.resolve_unit_manager(employee)
        if unit_manager_id is None:
            raise AdvanceError("مدیر واحد شما پیدا نشد (همان تأییدکننده‌ی مرخصی)؛ با منابع انسانی هماهنگ کنید")
        site_manager_id = st.site_manager_employee_id
        if site_manager_id is None:
            raise AdvanceError("مدیر سایت برای تأیید مساعده تعیین نشده است؛ با واحد مالی هماهنگ کنید")
        req = AdvanceRequest(
            site_id=employee.site_id,
            employee_id=employee.id,
            amount=final_amount,
            employee_group=overview["group"],
            service_months=overview["service"]["months"],
            reason=_clean(reason),
            request_month=overview["current_month"],
            status=R.STATUS_IN_REVIEW,
            steps=R.effective_steps(
                requester_id=employee.id, unit_manager_id=unit_manager_id, site_manager_id=site_manager_id
            ),
            step_index=0,
            unit_manager_employee_id=unit_manager_id,
            site_manager_employee_id=site_manager_id,
            events=[],
        )
        self.db.add(req)
        self._event(req, "submitted", employee_label(employee), user.id)
        await self.db.flush()
        await self._enter_step(req)
        await self._commit()
        return await self.serialize(await self._load(req.id), public=True)

    async def cancel(self, employee: Employee, user: User, request_id: int) -> dict:
        req = await self._load(request_id, lock=True)
        if req.employee_id != employee.id:
            raise AdvanceError("این درخواست متعلق به شما نیست", 403)
        if req.status not in (R.STATUS_IN_REVIEW, R.STATUS_WAITING_FINANCE):
            raise AdvanceError("فقط درخواست در انتظار تأیید قابل لغو است")
        req.status = R.STATUS_CANCELLED
        req.current_approver_employee_id = None
        req.decided_at = _now()
        self._event(req, "cancelled", employee_label(employee), user.id)
        await self._commit()
        return await self.serialize(req, public=True)

    # ---------- کارتابل مدیر واحد / مدیر سایت ----------

    async def inbox(self, employee: Employee) -> list[dict]:
        condition, scope = await self._approval_condition(employee)
        rows = list(
            (
                await self.db.execute(
                    select(AdvanceRequest)
                    .options(selectinload(AdvanceRequest.events))
                    .where(condition, AdvanceRequest.status == R.STATUS_IN_REVIEW)
                    .order_by(AdvanceRequest.id)
                )
            ).scalars().all()
        )
        items = await self.serialize_many(rows, public=True)
        if scope:
            people = await self._names({r.current_approver_employee_id for r in rows})
            for req, item in zip(rows, items):
                if req.current_approver_employee_id != employee.id:
                    item["as_substitute_for"] = employee_label(people.get(req.current_approver_employee_id), code=False)
        return items

    async def inbox_count(self, employee: Employee) -> int:
        condition, _ = await self._approval_condition(employee)
        return (
            await self.db.execute(
                select(func.count(AdvanceRequest.id)).where(condition, AdvanceRequest.status == R.STATUS_IN_REVIEW)
            )
        ).scalar_one()

    async def approver_decide(
        self, employee: Employee, user: User, request_ids: list[int], approve: bool, note
    ) -> dict:
        """
        تصمیم (گروهی) مدیر واحد / مدیر سایت روی درخواست‌هایی که الان در انتظار اوست.
        هر درخواست جدا بررسی می‌شود؛ خروجی: {"done": [id...], "failed": [{"id", "error"}]}.
        """
        if not (employee.is_active and employee.is_enabled):
            raise AdvanceError("حساب پرسنلی شما فعال نیست", 403)
        if not approve and not _clean(note):
            raise AdvanceError("دلیل رد را بنویسید")
        done, failed = [], []
        for rid in dict.fromkeys(request_ids):
            try:
                req = await self._load(rid, lock=True)
                step = self.current_step(req)
                person_step = step in (R.STEP_UNIT_MANAGER, R.STEP_SITE_MANAGER)
                as_substitute = (
                    person_step
                    and req.current_approver_employee_id != employee.id
                    and req.employee_id != employee.id
                    and await kara_substitute.substitute_of(
                        self.db, AdvanceSettings, req.site_id, req.current_approver_employee_id
                    )
                    == employee.id
                )
                if not person_step or (req.current_approver_employee_id != employee.id and not as_substitute):
                    raise AdvanceError("این درخواست در انتظار تصمیم شما نیست", 403)
                label = f"{employee_label(employee)} — {R.STEP_LABELS[step]}"
                if as_substitute:
                    manager = (await self._names([req.current_approver_employee_id])).get(req.current_approver_employee_id)
                    label += f" (جانشین {employee_label(manager)})"
                if approve:
                    self._event(req, "approved", label, user.id, note)
                    req.step_index += 1
                    await self._enter_step(req)
                else:
                    self._event(req, "rejected", label, user.id, note)
                    req.status = R.STATUS_REJECTED
                    req.current_approver_employee_id = None
                    req.decided_at = _now()
                    self._push([req.employee_id], MINE_URL, req.site_id, "advance.rejected")
                done.append(rid)
            except AdvanceError as e:
                failed.append({"id": rid, "error": str(e)})
        await self._commit()
        return {"done": done, "failed": failed}

    # ---------- مدیریت ----------

    async def admin_sites(self, site_ids: set[int] | None) -> list[dict]:
        stmt = select(Site).order_by(Site.id)
        if site_ids is not None:
            stmt = stmt.where(Site.id.in_(site_ids or {-1}))
        sites = (await self.db.execute(stmt)).scalars().all()
        settings = {s.site_id: s for s in (await self.db.execute(select(AdvanceSettings))).scalars().all()}
        managers = await self._names([s.site_manager_employee_id for s in settings.values()])
        out = []
        for site in sites:
            st = settings.get(site.id)
            mid = st.site_manager_employee_id if st else None
            out.append(
                {
                    "site_id": site.id,
                    "site_name": site.name,
                    "is_enabled": bool(st and st.is_enabled),
                    "site_manager_employee_id": mid,
                    "site_manager": employee_label(managers.get(mid)),
                    "window_from_day": st.window_from_day if st else 1,
                    "window_to_day": st.window_to_day if st else 31,
                    "max_per_month": st.max_per_month if st else 1,
                    "rules_text": st.rules_text if st else None,
                    "amount_mode": st.amount_mode if st else R.AMOUNT_FIXED,
                    "amount_step": st.amount_step if st else None,
                    "allow_kara_substitute": bool(st and st.allow_kara_substitute),
                    "tiers": await self.tiers(site.id),
                    "members": await self.members(site.id),
                    "stuck_count": await self.stuck_count(site.id),
                }
            )
        return out

    # ---------- انتقال تأییدکننده‌ها (ترک کار / تغییر تنظیمات؛ services/approver_reassign.py) ----------

    async def on_employees_left(self, employee_ids: list[int]) -> int:
        """ترک کار (Sync): مساعده‌های پرداخت‌نشده‌ی خود این پرسنل خودکار لغو می‌شوند (سابقه می‌ماند). بدون commit."""
        if not employee_ids:
            return 0
        rows = (
            await self.db.execute(
                select(AdvanceRequest)
                .options(selectinload(AdvanceRequest.events))
                .where(AdvanceRequest.employee_id.in_(employee_ids), AdvanceRequest.status.in_(R.OPEN_STATUSES))
            )
        ).scalars().all()
        for req in rows:
            req.status = R.STATUS_CANCELLED
            req.current_approver_employee_id = None
            self._event(req, "cancelled", "سامانه", None, "لغو خودکار — ترک کار درخواست‌دهنده")
        await self.db.flush()
        return len(rows)

    async def _usable_approver(self, req: AdvanceRequest, step: str, approver: int | None) -> int | None:
        """
        رسیدن به یک مرحله: اگر تأییدکننده‌ی ذخیره‌شده دیگر نمی‌تواند تأیید کند (ترک کار) یا مدیر سایت در تنظیمات عوض شده،
        همان لحظه به تأییدکننده‌ی امروز منتقل می‌شود (اعلان را خود _enter_step می‌فرستد).
        """
        from app.services.approver_reassign import ApproverChecker, reassign_requests

        changed_setting = step == R.STEP_SITE_MANAGER and (await self._site_approvers(req.site_id)).get(
            "site_manager"
        ) not in (None, approver)
        if not changed_setting and await ApproverChecker(self.db).ok(approver):
            return approver
        await reassign_requests(
            self.db,
            [req],
            site_approvers=self._site_approvers,
            resolve_unit_manager=self._loans.resolve_unit_manager,
            refresh_unit_manager=False,
            current_step=lambda _r: None,
            event=self._event,
            push=lambda *a, **k: None,
            push_url=INBOX_URL,
            push_key="advance.approver_pending",
            reason="تأییدکننده‌ی قبلی در دسترس نبود",
        )
        return req.unit_manager_employee_id if step == R.STEP_UNIT_MANAGER else req.site_manager_employee_id

    async def _site_approvers(self, site_id: int) -> dict:
        st = await self.settings(site_id)
        return {"site_manager": st.site_manager_employee_id if st else None}

    async def reassign_approvers(
        self,
        *,
        site_id: int | None = None,
        approver_ids: list[int] | None = None,
        refresh_unit_manager: bool = False,
        reason: str,
    ) -> dict:
        """مثل LoanService.reassign_approvers برای مساعده (مدیر واحد و مدیر سایت). بدون commit."""
        from app.services.approver_reassign import reassign_requests

        q = (
            select(AdvanceRequest)
            .options(selectinload(AdvanceRequest.events))
            .where(AdvanceRequest.status == R.STATUS_IN_REVIEW)
        )
        if site_id is not None:
            q = q.where(AdvanceRequest.site_id == site_id)
        if approver_ids:
            q = q.where(
                AdvanceRequest.unit_manager_employee_id.in_(approver_ids)
                | AdvanceRequest.site_manager_employee_id.in_(approver_ids)
            )
        requests = list((await self.db.execute(q)).scalars().all())
        if not requests:
            return {"changed": 0, "unresolved": 0}
        return await reassign_requests(
            self.db,
            requests,
            site_approvers=self._site_approvers,
            resolve_unit_manager=self._loans.resolve_unit_manager,
            refresh_unit_manager=refresh_unit_manager,
            current_step=self.current_step,
            event=self._event,
            push=self._push,
            push_url=INBOX_URL,
            push_key="advance.approver_pending",
            reason=reason,
        )

    async def stuck_count(self, site_id: int) -> int:
        from app.services.approver_reassign import stuck_count

        rows = (
            await self.db.execute(
                select(AdvanceRequest).where(
                    AdvanceRequest.site_id == site_id, AdvanceRequest.status == R.STATUS_IN_REVIEW
                )
            )
        ).scalars().all()
        return await stuck_count(self.db, list(rows), self.current_step)

    async def update_settings(self, site_id: int, data: dict) -> dict:
        if (await self.db.get(Site, site_id)) is None:
            raise AdvanceError("سایت پیدا نشد", 404)
        manager_id = data.get("site_manager_employee_id")
        if manager_id is not None:
            manager = await self.db.get(Employee, manager_id)
            if manager is None or manager.site_id != site_id:
                raise AdvanceError("مدیر سایت باید از پرسنل همین سایت باشد")
            if not (manager.is_active and manager.is_enabled):
                raise AdvanceError("پرسنل انتخاب‌شده برای مدیر سایت فعال نیست")
            has_user = (await self.db.execute(select(User.id).where(User.employee_id == manager.id).limit(1))).first()
            if not has_user:
                raise AdvanceError("مدیر سایت باید حساب کاربری پرتال داشته باشد تا بتواند تأیید کند")
        try:
            f, t, n = R.validate_window(data.get("window_from_day"), data.get("window_to_day"), data.get("max_per_month"))
            tiers = R.validate_tiers(data.get("tiers") or [])
            amount_mode, amount_step = R.validate_amount_settings(data.get("amount_mode"), data.get("amount_step"))
        except R.AdvanceRuleError as e:
            raise AdvanceError(str(e)) from e
        st = await self.settings(site_id, create=True)
        st.is_enabled = bool(data.get("is_enabled"))
        st.site_manager_employee_id = manager_id
        st.window_from_day, st.window_to_day, st.max_per_month = f, t, n
        st.rules_text = _clean(data.get("rules_text"), 4000)
        st.amount_mode, st.amount_step = amount_mode, amount_step
        if data.get("allow_kara_substitute") is not None:
            st.allow_kara_substitute = bool(data["allow_kara_substitute"])
        # پله‌ها: جایگزینی کامل (فهرست کوچک است)
        for row in (await self.db.execute(select(AdvanceTier).where(AdvanceTier.site_id == site_id))).scalars().all():
            await self.db.delete(row)
        await self.db.flush()
        for tier in tiers:
            self.db.add(
                AdvanceTier(
                    site_id=site_id,
                    group=tier["group"],
                    min_months=tier["min_months"],
                    amount=tier["amount"],
                    # حداقل فقط در حالت دلخواه معنی دارد؛ در حالت ثابت هم نگه داشته می‌شود تا با برگشتن به دلخواه گم نشود
                    min_amount=tier.get("min_amount"),
                )
            )
        # تعیین دستی گروه‌ها: جایگزینی کامل؛ هر پرسنل فقط یک گروه، فقط پرسنل همین سایت
        members: dict[int, str] = {}
        for m in data.get("members") or []:
            try:
                emp_id, group = int(m.get("employee_id")), str(m.get("group"))
            except (AttributeError, TypeError, ValueError) as e:
                raise AdvanceError("فهرست مدیران/سرپرستان نامعتبر است") from e
            if group not in (R.GROUP_SUPERVISOR, R.GROUP_MANAGER):
                raise AdvanceError("گروه تعیین‌شده نامعتبر است (فقط سرپرست یا مدیر)")
            members[emp_id] = group
        if members:
            found = (
                await self.db.execute(
                    select(Employee.id).where(Employee.id.in_(members), Employee.site_id == site_id)
                )
            ).scalars().all()
            if len(found) != len(members):
                raise AdvanceError("همه‌ی مدیران/سرپرستان باید از پرسنل همین سایت باشند")
        for row in (
            await self.db.execute(select(AdvanceGroupMember).where(AdvanceGroupMember.site_id == site_id))
        ).scalars().all():
            await self.db.delete(row)
        await self.db.flush()
        for emp_id, group in members.items():
            self.db.add(AdvanceGroupMember(site_id=site_id, employee_id=emp_id, group=group))
        await self.db.flush()
        # درخواست‌های باز این سایت به مدیر سایت جدید منتقل می‌شوند (بدون ثبت مجدد)
        result = await self.reassign_approvers(site_id=site_id, reason="تغییر مدیر سایت در تنظیمات مساعده")
        await self._commit()
        return result

    async def list_requests(
        self, site_id: int, status: str | None, month: str | None, q: str | None, page: int, page_size: int
    ) -> dict:
        stmt = self._requests_stmt(site_id, status, month, q)
        total = (await self.db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one()
        rows = (
            await self.db.execute(stmt.order_by(AdvanceRequest.id.desc()).offset((page - 1) * page_size).limit(page_size))
        ).scalars().all()
        return {"items": await self.serialize_many(list(rows), public=False), "total": total}

    def _requests_stmt(self, site_id: int, status: str | None, month: str | None, q: str | None):
        """فیلترهای مشترک فهرست درخواست‌های پنل و خروجی Excel."""
        stmt = select(AdvanceRequest).options(selectinload(AdvanceRequest.events)).where(AdvanceRequest.site_id == site_id)
        if status == "open":
            stmt = stmt.where(AdvanceRequest.status.in_(R.OPEN_STATUSES))
        elif status:
            stmt = stmt.where(AdvanceRequest.status == status)
        if month:
            stmt = stmt.where(AdvanceRequest.request_month == month)
        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.join(Employee, Employee.id == AdvanceRequest.employee_id).where(
                (Employee.first_name.ilike(like)) | (Employee.last_name.ilike(like)) | (Employee.personnel_code.ilike(like))
            )
        return stmt

    async def export_xlsx(self, site_id: int, status: str | None, month: str | None, q: str | None) -> bytes:
        """
        خروجی Excel درخواست‌های مساعده با همان فیلترهای فهرست پنل؛ برای هر بانک فعال سایت ستون‌های اطلاعات بانکی پرسنل
        (شماره حساب/شبا/کارت، فیلدهای مخفی حذف) — برای پرداخت توسط واحد مالی (docs/advances.md).
        """
        import io
        from zoneinfo import ZoneInfo

        import jdatetime
        from openpyxl import Workbook

        from app.core.bank_rules import FIELDS as BANK_FIELDS
        from app.models.bank_account import EmployeeBankAccount
        from app.models.employee import Department
        from app.services.bank_account_service import BankAccountService

        rows = (
            await self.db.execute(self._requests_stmt(site_id, status, month, q).order_by(AdvanceRequest.id.desc()))
        ).scalars().all()
        emp_ids = list({r.employee_id for r in rows})
        emps: dict[int, tuple] = {}
        if emp_ids:
            res = await self.db.execute(
                select(Employee, Department.name)
                .outerjoin(Department, Department.id == Employee.department_id)
                .where(Employee.id.in_(emp_ids))
            )
            emps = {e.id: (e, dept) for e, dept in res.all()}
        banks = await BankAccountService(self.db).list_banks(site_id, active_only=True)
        accounts: dict[tuple[int, int], EmployeeBankAccount] = {}
        if emp_ids and banks:
            res = await self.db.execute(select(EmployeeBankAccount).where(EmployeeBankAccount.employee_id.in_(emp_ids)))
            accounts = {(a.employee_id, a.bank_id): a for a in res.scalars().all()}
        bank_cols = [
            (bank.id, field, f"{bank.name} - {label}")
            for bank in banks
            for field, label in BANK_FIELDS.items()
            if bank.modes[field] != "hidden"
        ]
        tehran = ZoneInfo("Asia/Tehran")

        def jalali_dt(value) -> str:
            if not value:
                return ""
            return jdatetime.datetime.fromgregorian(datetime=value.astimezone(tehran)).strftime("%Y/%m/%d %H:%M")

        wb = Workbook()
        ws = wb.active
        ws.title = "مساعده"
        ws.sheet_view.rightToLeft = True
        header = [
            "شماره", "کد پرسنلی", "نام", "نام خانوادگی", "واحد", "گروه", "سابقه (ماه)", "ماه درخواست", "مبلغ (ریال)",
            "وضعیت", "زمان ثبت", "تاریخ پرداخت", "توضیح پرسنل", "توضیح پرداخت",
        ]  # fmt: skip
        ws.append(header + [c[2] for c in bank_cols])
        for req in rows:
            emp, dept = emps.get(req.employee_id, (None, None))
            row = [
                req.id, emp.personnel_code if emp else "", emp.first_name if emp else "", emp.last_name if emp else "",
                dept or "", R.GROUP_LABELS.get(req.employee_group, req.employee_group or ""), req.service_months,
                req.request_month, req.amount, R.status_label(req.status, self.current_step(req)),
                jalali_dt(req.created_at), req.paid_date or "", req.reason or "", req.paid_note or "",
            ]  # fmt: skip
            for bank_id, field, _ in bank_cols:
                acc = accounts.get((req.employee_id, bank_id))
                row.append(getattr(acc, field, None) or "" if acc else "")
            ws.append(row)
        # مبلغ با جداکننده‌ی هزارگان؛ شماره‌های بانکی متن (صفرهای ابتدا و نمایش علمی)
        first_bank_col = len(header) + 1
        for row_cells in ws.iter_rows(min_row=2):
            row_cells[8].number_format = "#,##0"
            for cell in row_cells[first_bank_col - 1 :]:
                cell.number_format = "@"
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    async def finance_decide(self, site_id: int, user: User, request_ids: list[int], approve: bool, note) -> dict:
        """تأیید/رد گروهی واحد مالی روی درخواست‌های «در انتظار تأیید واحد مالی» همین سایت."""
        if not approve and not _clean(note):
            raise AdvanceError("دلیل رد را بنویسید")
        actor = f"{await self._loans._actor(user)} — واحد مالی"
        done, failed = [], []
        for rid in dict.fromkeys(request_ids):
            try:
                req = await self._load(rid, lock=True)
                if req.site_id != site_id:
                    raise AdvanceError("درخواست متعلق به این سایت نیست", 403)
                if req.status != R.STATUS_WAITING_FINANCE:
                    raise AdvanceError("این درخواست در انتظار تأیید واحد مالی نیست")
                if approve:
                    self._event(req, "approved", actor, user.id, note)
                    req.status = R.STATUS_APPROVED
                    req.step_index = len(req.steps or [])
                    self._push([req.employee_id], MINE_URL, req.site_id, "advance.approved")
                else:
                    self._event(req, "rejected", actor, user.id, note)
                    req.status = R.STATUS_REJECTED
                    self._push([req.employee_id], MINE_URL, req.site_id, "advance.rejected")
                req.decided_at = _now()
                done.append(rid)
            except AdvanceError as e:
                failed.append({"id": rid, "error": str(e)})
        await self._commit()
        return {"done": done, "failed": failed}

    async def finance_pay(self, site_id: int, user: User, request_ids: list[int], paid_date: str | None, note) -> dict:
        """ثبت پرداخت گروهی روی درخواست‌های تأییدشده؛ paid_date شمسی (پیش‌فرض امروز)."""
        from app.core.loan_rules import normalize_date

        date = normalize_date(paid_date) if paid_date else _today()
        if date is None:
            raise AdvanceError("تاریخ پرداخت نامعتبر است")
        actor = f"{await self._loans._actor(user)} — واحد مالی"
        done, failed = [], []
        for rid in dict.fromkeys(request_ids):
            try:
                req = await self._load(rid, lock=True)
                if req.site_id != site_id:
                    raise AdvanceError("درخواست متعلق به این سایت نیست", 403)
                if req.status != R.STATUS_APPROVED:
                    raise AdvanceError("فقط درخواست تأییدشده قابل ثبت پرداخت است")
                req.status = R.STATUS_PAID
                req.paid_date = date
                req.paid_note = _clean(note, 500)
                self._event(req, "paid", actor, user.id, f"تاریخ پرداخت: {date}" + (f" — {_clean(note, 500)}" if _clean(note) else ""))
                self._push([req.employee_id], MINE_URL, req.site_id, "advance.paid", amount=f"{req.amount:,}")
                done.append(rid)
            except AdvanceError as e:
                failed.append({"id": rid, "error": str(e)})
        await self._commit()
        return {"done": done, "failed": failed}
