"""
سرویس ماژول «درخواست وام» (docs/loans.md).

جریان: پرسنل نوع وام، مبلغ و ضامن‌ها را انتخاب می‌کند ← هر ضامن «قبول/رد» ← مدیر واحد (همان تأییدکننده‌ی
مرخصی: زنجیره‌ی بخش کاراوب، و اگر نبود تأییدکننده‌ی دستی واحد) ← مدیر سایت ← صف پرداخت واحد مالی ← مالی مبلغ
نهایی و اقساط را ثبت می‌کند ← اقساط تیک می‌خورند ← «تسویه شد».
مقررات (انواع، سقف، سابقه، ضامن، مسیر تأیید) برای هر سایت از LoanPolicy جاری خوانده می‌شود؛ درخواست ثبت‌شده
snapshot خودش را دارد و تغییر بعدی مقررات رویش اثر ندارد.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import loan_rules as R
from app.core.persian_date import get_current_jalali_date
from app.models.employee import Employee
from app.models.loan import (
    LoanInstallment,
    LoanPolicy,
    LoanRequest,
    LoanRequestEvent,
    LoanRequestGuarantor,
    LoanServiceOverride,
    LoanSiteSettings,
    LoanType,
)
from app.models.site import Site
from app.models.user import User

logger = logging.getLogger(__name__)

MAX_NOTE = 2000


class LoanError(Exception):
    """خطای قابل نمایش (متن فارسی)؛ status_code برای Endpoint."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> str:
    y, m, d = get_current_jalali_date()
    return f"{y:04d}/{m:02d}/{d:02d}"


def _clean(text, limit: int = MAX_NOTE) -> str | None:
    value = (text or "").strip()
    return value[:limit] or None


def employee_label(emp: Employee | None) -> str | None:
    if emp is None:
        return None
    return f"{emp.first_name} {emp.last_name} ({emp.personnel_code})"


# ---------- اعلان Push (پس‌زمینه، Session جدا؛ مثل درخواست مرخصی) ----------

_background_tasks: set = set()


def _schedule_push(employee_ids, url: str, body: str) -> None:
    ids = {i for i in employee_ids if i}
    if not ids:
        return
    try:
        task = asyncio.get_running_loop().create_task(_send_push(ids, url, body))
    except RuntimeError:
        return
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _send_push(employee_ids: set[int], url: str, body: str) -> None:
    from app.db.session import AsyncSessionLocal
    from app.services.push_service import PushService

    try:
        async with AsyncSessionLocal() as db:
            user_ids = set(
                (await db.execute(select(User.id).where(User.employee_id.in_(employee_ids)))).scalars().all()
            )
            if user_ids:
                await asyncio.wait_for(
                    PushService(db).notify_users(user_ids, url=url, priority="normal", body=body), timeout=60
                )
    except Exception:
        logger.exception("ارسال Push درخواست وام با خطا مواجه شد")


_SUFFIX = "\nجهت مشاهده روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید."


class LoanService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._pushes: list[tuple[set, str, str]] = []

    # ---------- کمکی ----------

    def _push(self, employee_ids, url: str, body: str) -> None:
        self._pushes.append((set(employee_ids), url, body + _SUFFIX))

    async def _commit(self) -> None:
        await self.db.commit()
        for ids, url, body in self._pushes:
            _schedule_push(ids, url, body)
        self._pushes.clear()

    async def _actor(self, user: User) -> str:
        """نام نمایشی کاربر برای تاریخچه: نام پرسنل متصل، وگرنه نام کاربری."""
        if user.employee_id:
            emp = await self.db.get(Employee, user.employee_id)
            if emp is not None:
                return employee_label(emp)
        return user.username

    async def site_settings(self, site_id: int, *, create: bool = False, lock: bool = False) -> LoanSiteSettings | None:
        """
        تنظیمات وام سایت. create: اگر نیست ساخته شود (INSERT ... ON CONFLICT تا دو درخواست هم‌زمان خطای یکتایی ندهند).
        lock: قفل ردیف و خواندن تازه از دیتابیس (populate_existing؛ نسخه‌ی قدیمی داخل Session معتبر نیست).
        """
        if create:
            await self.db.execute(
                pg_insert(LoanSiteSettings)
                .values(site_id=site_id, is_enabled=False, last_queue_seq=0)
                .on_conflict_do_nothing(index_elements=["site_id"])
            )
        stmt = select(LoanSiteSettings).where(LoanSiteSettings.site_id == site_id)
        if lock or create:
            stmt = stmt.execution_options(populate_existing=True)
        if lock:
            stmt = stmt.with_for_update()
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def is_site_enabled(self, site_id: int | None) -> bool:
        if site_id is None:
            return False
        row = await self.site_settings(site_id)
        return bool(row and row.is_enabled)

    async def current_policy(self, site_id: int) -> LoanPolicy | None:
        """نسخه‌ی جاری مقررات: آخرین effective_from که امروز یا پیش از آن است."""
        stmt = (
            select(LoanPolicy)
            .options(selectinload(LoanPolicy.types))
            .where(LoanPolicy.site_id == site_id, LoanPolicy.effective_from <= _today())
            .order_by(LoanPolicy.effective_from.desc(), LoanPolicy.id.desc())
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def service_info(self, employee: Employee) -> dict:
        """سابقه برای وام: از تاریخ استخدام دوره‌ی فعلی، یا تاریخ اصلاح‌شده‌ی مالی."""
        override = (
            await self.db.execute(select(LoanServiceOverride).where(LoanServiceOverride.employee_id == employee.id))
        ).scalar_one_or_none()
        start = override.start_date if override else R.normalize_date(employee.hire_date_jalali)
        months = R.months_between(start, _today()) if start else None
        return {
            "months": months,
            "label": R.format_service(months),
            "start_date": start,
            "overridden": override is not None,
            "override_note": override.note if override else None,
        }

    async def _names(self, ids) -> dict[int, Employee]:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        rows = (await self.db.execute(select(Employee).where(Employee.id.in_(ids)))).scalars().all()
        return {e.id: e for e in rows}

    async def _queue_positions(self, site_id: int) -> dict[int, int]:
        rows = (
            await self.db.execute(
                select(LoanRequest.id)
                .where(
                    LoanRequest.site_id == site_id,
                    LoanRequest.status == R.STATUS_WAITING_FINANCE,
                    LoanRequest.out_of_queue.is_(False),
                )
                .order_by(LoanRequest.queue_seq.asc().nulls_last(), LoanRequest.id)
            )
        ).scalars().all()
        return {rid: i for i, rid in enumerate(rows, start=1)}

    async def _load_request(self, request_id: int, *, lock: bool = False) -> LoanRequest:
        stmt = (
            select(LoanRequest)
            .options(
                selectinload(LoanRequest.guarantors),
                selectinload(LoanRequest.events),
                selectinload(LoanRequest.installments),
            )
            .where(LoanRequest.id == request_id)
        )
        if lock:
            # خواندن تازه بعد از گرفتن قفل؛ نسخه‌ی کش‌شده‌ی Session ممکن است قبل از تغییر Worker دیگر باشد
            stmt = stmt.with_for_update(of=LoanRequest).execution_options(populate_existing=True)
        req = (await self.db.execute(stmt)).scalar_one_or_none()
        if req is None:
            raise LoanError("درخواست وام پیدا نشد", 404)
        return req

    def _event(self, req: LoanRequest, action: str, actor: str | None, user_id: int | None = None, note=None) -> None:
        req.events.append(
            LoanRequestEvent(action=action, actor_label=actor, actor_user_id=user_id, note=_clean(note), created_at=_now())
        )

    @staticmethod
    def current_step(req: LoanRequest) -> str | None:
        if req.status != R.STATUS_IN_REVIEW:
            return None
        steps = req.steps or []
        return steps[req.step_index] if 0 <= req.step_index < len(steps) else None

    async def _next_queue_seq(self, site_id: int) -> int:
        """شماره‌ی نوبت بعدی سایت به‌صورت اتمی (UPDATE ... RETURNING؛ دو Worker هم‌زمان شماره‌ی تکراری نمی‌گیرند)."""
        await self.site_settings(site_id, create=True)
        result = await self.db.execute(
            update(LoanSiteSettings)
            .where(LoanSiteSettings.site_id == site_id)
            .values(last_queue_seq=LoanSiteSettings.last_queue_seq + 1)
            .returning(LoanSiteSettings.last_queue_seq)
            .execution_options(synchronize_session=False)
        )
        return int(result.scalar_one())

    async def _bump_queue_seq(self, site_id: int, seq: int) -> None:
        """شماره‌ی نوبت دستی: شمارنده‌ی سایت حداقل به این عدد برسد (نوبت‌های بعدی بعد از آن)."""
        await self.site_settings(site_id, create=True)
        await self.db.execute(
            update(LoanSiteSettings)
            .where(LoanSiteSettings.site_id == site_id, LoanSiteSettings.last_queue_seq < seq)
            .values(last_queue_seq=seq)
            .execution_options(synchronize_session=False)
        )

    async def _enter_step(self, req: LoanRequest) -> None:
        """درخواست را در مرحله‌ی step_index قرار می‌دهد (وضعیت، تأییدکننده‌ی جاری، نوبت) و اعلان می‌فرستد."""
        steps = req.steps or [R.STEP_FINANCE]
        step = steps[min(req.step_index, len(steps) - 1)]
        if step == R.STEP_FINANCE:
            req.status = R.STATUS_WAITING_FINANCE
            req.current_approver_employee_id = None
            if req.queue_seq is None and not req.out_of_queue:
                req.queue_seq = await self._next_queue_seq(req.site_id)
            self._push(
                [req.employee_id],
                "/loans?tab=mine",
                "درخواست وام شما تأیید شد و به صف پرداخت واحد مالی رفت.",
            )
            return
        req.status = R.STATUS_IN_REVIEW
        if step == R.STEP_GUARANTORS:
            req.current_approver_employee_id = None
            pending = [g.employee_id for g in req.guarantors if g.status == "pending"]
            self._push(pending, "/loans?tab=inbox", "یک همکار شما را ضامن درخواست وام خود کرده است.")
            return
        approver = req.unit_manager_employee_id if step == R.STEP_UNIT_MANAGER else req.site_manager_employee_id
        req.current_approver_employee_id = approver
        self._push([approver], "/loans?tab=inbox", "یک درخواست وام در انتظار تصمیم شماست.")

    async def _advance(self, req: LoanRequest) -> None:
        req.step_index += 1
        await self._enter_step(req)

    async def resolve_unit_manager(self, employee: Employee) -> int | None:
        """
        مدیر واحد = تأییدکننده‌ی مرخصی همین پرسنل: زنجیره‌ی بخش کاراوب (Employee.Sec_No ← Sections.ManagerEmp_No)،
        و اگر جواب نداد تأییدکننده‌ی دستی واحد. خروجی: شناسه‌ی پرسنل پورتال یا None.
        """
        from app.services.leave_request_service import LeaveRequestService, _resolve_manager_emp_no_sync

        leave = LeaveRequestService(self.db)
        # ۱) زنجیره‌ی بخش کاراوب؛ کد پرسنلی فقط در همین سایت و سایت‌های هم‌منبع (همان کاراوب) معنی دارد
        try:
            mapping, conn = await leave._get_mapping_and_connection(employee.site_id)
            emp_no = await asyncio.to_thread(_resolve_manager_emp_no_sync, conn, mapping, int(employee.personnel_code))
            if emp_no is not None:
                site_ids = await leave._same_source_site_ids(employee.site_id)
                found = (
                    await self.db.execute(
                        select(Employee.id)
                        .where(
                            Employee.personnel_code == str(emp_no),
                            Employee.site_id.in_(site_ids),
                            Employee.is_active.is_(True),
                            Employee.is_enabled.is_(True),
                        )
                        .order_by((Employee.site_id != employee.site_id).asc(), Employee.id)
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if found is not None:
                    return found
        except Exception:  # noqa: BLE001 - کاراوب در دسترس نیست/تنظیم نشده → تأییدکننده‌ی دستی
            logger.info("زنجیره‌ی مدیر کاراوب برای وام جواب نداد؛ تأییدکننده‌ی دستی واحد بررسی می‌شود", exc_info=True)
        # ۲) تأییدکننده‌ی دستی واحد (همان Fallback مرخصی)
        try:
            approver_id = await leave._get_approver_employee_id(employee.department_id)
        except Exception:  # noqa: BLE001
            return None
        if approver_id is None:
            return None
        approver = await self.db.get(Employee, approver_id)
        return approver_id if approver is not None and approver.is_active and approver.is_enabled else None

    async def _guarantor_problem(self, policy: LoanPolicy, requester: Employee, g: Employee | None) -> str | None:
        """
        چرا این همکار نمی‌تواند ضامن باشد (None = می‌تواند). برای قواعد مقررات (سابقه، تعداد ضمانت، وام فعال) فقط یک
        پیام کلی برمی‌گردد تا وضعیت وام همکاران از روی پیام خطا قابل کشف نباشد.
        """
        if g is None or g.site_id != requester.site_id:
            return "همکار انتخاب‌شده از پرسنل سایت شما نیست"
        name = f"{g.first_name} {g.last_name}"
        generic = f"{name} شرایط ضامن شدن طبق مقررات وام سایت را ندارد؛ همکار دیگری انتخاب کنید"
        if g.id == requester.id:
            return "خودتان نمی‌توانید ضامن خود باشید"
        if not (g.is_active and g.is_enabled):
            return f"{name} پرسنل فعال نیست"
        has_user = (await self.db.execute(select(User.id).where(User.employee_id == g.id).limit(1))).first()
        if not has_user:
            return f"{name} حساب کاربری پرتال ندارد و نمی‌تواند ضمانت را تأیید کند"
        if policy.guarantor_min_service_months:
            info = await self.service_info(g)
            if info["months"] is None or info["months"] < policy.guarantor_min_service_months:
                return generic
        if policy.guarantor_max_active:
            count = (
                await self.db.execute(
                    select(func.count(LoanRequestGuarantor.id))
                    .join(LoanRequest, LoanRequest.id == LoanRequestGuarantor.request_id)
                    .where(
                        LoanRequestGuarantor.employee_id == g.id,
                        LoanRequestGuarantor.status.in_(("pending", "accepted")),
                        LoanRequest.status.in_(R.UNSETTLED_STATUSES),
                    )
                )
            ).scalar_one()
            if count >= policy.guarantor_max_active:
                return generic
        if policy.guarantor_no_active_loan:
            busy = (
                await self.db.execute(
                    select(LoanRequest.id)
                    .where(
                        LoanRequest.employee_id == g.id,
                        LoanRequest.status.in_(R.UNSETTLED_STATUSES),
                    )
                    .limit(1)
                )
            ).first()
            if busy:
                return generic
        return None

    # ---------- نمایش ----------

    async def serialize(self, req: LoanRequest, *, positions: dict | None = None, detail: bool = False) -> dict:
        if positions is None and req.status == R.STATUS_WAITING_FINANCE and not req.out_of_queue:
            positions = await self._queue_positions(req.site_id)
        position = (positions or {}).get(req.id)
        people = await self._names(
            [req.employee_id, req.unit_manager_employee_id, req.site_manager_employee_id, req.current_approver_employee_id]
            + [g.employee_id for g in req.guarantors]
        )
        step = self.current_step(req)
        paid_total = sum(i.amount for i in req.installments if i.paid_at)
        total = sum(i.amount for i in req.installments)
        out = {
            "id": req.id,
            "site_id": req.site_id,
            "employee_id": req.employee_id,
            "employee": employee_label(people.get(req.employee_id)),
            "type_title": req.type_title,
            "out_of_queue": req.out_of_queue,
            "extra_requirement": req.extra_requirement,
            "extra_confirmed": req.extra_confirmed,
            "amount_requested": req.amount_requested,
            "amount_approved": req.amount_approved,
            "reason": req.reason,
            "service_months": req.service_months,
            "status": req.status,
            "status_label": R.status_label(req.status, step, position, req.out_of_queue),
            "current_step": step,
            "steps": [
                {
                    "key": key,
                    "label": R.STEP_LABELS.get(key, key),
                    "state": (
                        "done"
                        if i < req.step_index or req.status in (R.STATUS_ACTIVE, R.STATUS_SETTLED)
                        else ("current" if i == req.step_index and req.status in R.OPEN_STATUSES else "todo")
                    ),
                    "person": employee_label(
                        people.get(
                            req.unit_manager_employee_id
                            if key == R.STEP_UNIT_MANAGER
                            else req.site_manager_employee_id
                            if key == R.STEP_SITE_MANAGER
                            else None
                        )
                    ),
                }
                for i, key in enumerate(req.steps or [])
            ],
            "current_approver": employee_label(people.get(req.current_approver_employee_id)),
            "guarantors": [
                {
                    "id": g.id,
                    "employee_id": g.employee_id,
                    "name": employee_label(people.get(g.employee_id)),
                    "status": g.status,
                    "note": g.note,
                }
                for g in req.guarantors
            ],
            "queue_seq": req.queue_seq,
            "queue_position": position,
            "installments": [
                {"id": i.id, "seq": i.seq, "due_month": i.due_month, "amount": i.amount, "paid": i.paid_at is not None}
                for i in req.installments
            ],
            "installments_total": total,
            "installments_paid": paid_total,
            "remaining": max(total - paid_total, 0) if total else None,
            "finance_note": req.finance_note,
            "is_manual": req.is_manual,
            "created_at": req.created_at,
            "paid_at": req.paid_at,
            "settled_at": req.settled_at,
        }
        if detail:
            out["events"] = [
                {"action": e.action, "actor": e.actor_label, "note": e.note, "created_at": e.created_at}
                for e in req.events
            ]
        return out

    async def _serialize_many(self, rows: list[LoanRequest], detail: bool = False) -> list[dict]:
        cache: dict[int, dict] = {}
        out = []
        for req in rows:
            if req.site_id not in cache:
                cache[req.site_id] = await self._queue_positions(req.site_id)
            out.append(await self.serialize(req, positions=cache[req.site_id], detail=detail))
        return out

    def _requests_query(self):
        return select(LoanRequest).options(
            selectinload(LoanRequest.guarantors),
            selectinload(LoanRequest.events),
            selectinload(LoanRequest.installments),
        )

    @staticmethod
    def policy_dict(policy: LoanPolicy, *, include_inactive: bool = True) -> dict:
        return {
            "id": policy.id,
            "site_id": policy.site_id,
            "title": policy.title,
            "effective_from": policy.effective_from,
            "rules_text": policy.rules_text,
            "block_if_unsettled": policy.block_if_unsettled,
            "approval_steps": R.normalize_steps(policy.approval_steps),
            "guarantor_max_active": policy.guarantor_max_active,
            "guarantor_min_service_months": policy.guarantor_min_service_months,
            "guarantor_no_active_loan": policy.guarantor_no_active_loan,
            "types": [
                {
                    "id": t.id,
                    "title": t.title,
                    "max_amount": t.max_amount,
                    "min_service_months": t.min_service_months,
                    "guarantor_count": t.guarantor_count,
                    "extra_requirement": t.extra_requirement,
                    "out_of_queue": t.out_of_queue,
                    "is_active": t.is_active,
                }
                for t in policy.types
                if include_inactive or t.is_active
            ],
        }

    # ---------- پرسنل ----------

    async def my_overview(self, employee: Employee) -> dict:
        enabled = await self.is_site_enabled(employee.site_id)
        policy = await self.current_policy(employee.site_id) if enabled else None
        service = await self.service_info(employee)
        rows = (
            await self.db.execute(
                self._requests_query()
                .where(LoanRequest.employee_id == employee.id)
                .order_by(LoanRequest.created_at.desc(), LoanRequest.id.desc())
            )
        ).scalars().all()
        requests = await self._serialize_many(list(rows), detail=True)
        block = None
        if any(r.status in R.OPEN_STATUSES for r in rows):
            block = "یک درخواست وام در حال بررسی دارید؛ تا نتیجه‌ی آن مشخص نشده درخواست جدید ممکن نیست."
        elif policy and policy.block_if_unsettled and any(r.status == R.STATUS_ACTIVE for r in rows):
            block = "تا تسویه‌ی کامل وام قبلی، درخواست وام جدید ممکن نیست."
        types = self.policy_dict(policy, include_inactive=False)["types"] if policy else []
        for d in types:
            d["ineligible_reason"] = R.type_ineligibility(d, service["months"])
        return {
            "enabled": enabled,
            "policy": (
                {
                    "id": policy.id,
                    "title": policy.title,
                    "effective_from": policy.effective_from,
                    "rules_text": policy.rules_text,
                    "types": types,
                }
                if policy
                else None
            ),
            "service": service,
            "block_reason": block,
            "requests": requests,
        }

    async def guarantor_candidates(self, employee: Employee, q: str | None) -> list[dict]:
        if not await self.is_site_enabled(employee.site_id):
            return []
        stmt = (
            select(Employee)
            .join(User, User.employee_id == Employee.id)
            .where(
                Employee.site_id == employee.site_id,
                Employee.id != employee.id,
                Employee.is_active.is_(True),
                Employee.is_enabled.is_(True),
            )
        )
        text = (q or "").strip()
        if text:
            like = f"%{text}%"
            stmt = stmt.where(
                or_(
                    (Employee.first_name + " " + Employee.last_name).ilike(like),
                    Employee.personnel_code.ilike(like),
                )
            )
        rows = (await self.db.execute(stmt.order_by(Employee.last_name, Employee.first_name).limit(20))).scalars().all()
        return [{"id": e.id, "label": employee_label(e)} for e in rows]

    async def submit(self, employee: Employee, user: User, payload: dict) -> dict:
        # قفل ردیف پرسنل: دو درخواست هم‌زمان (دو کلیک/دو Worker) هر دو «باز» ثبت نشوند
        await self.db.execute(select(Employee.id).where(Employee.id == employee.id).with_for_update())
        if not await self.is_site_enabled(employee.site_id):
            raise LoanError("درخواست وام برای سایت شما فعال نیست")
        policy = await self.current_policy(employee.site_id)
        if policy is None:
            raise LoanError("مقررات وام برای سایت شما هنوز تعریف نشده است")
        loan_type = next((t for t in policy.types if t.id == payload.get("loan_type_id")), None)
        if loan_type is None:
            raise LoanError("نوع وام انتخاب‌شده معتبر نیست")
        service = await self.service_info(employee)
        problem = R.type_ineligibility(
            {"is_active": loan_type.is_active, "min_service_months": loan_type.min_service_months}, service["months"]
        )
        if problem:
            raise LoanError(problem)
        try:
            amount = R.validate_amount(payload.get("amount"), loan_type.max_amount)
        except R.LoanRuleError as e:
            raise LoanError(str(e)) from e

        statuses = set(
            (await self.db.execute(select(LoanRequest.status).where(LoanRequest.employee_id == employee.id)))
            .scalars()
            .all()
        )
        if statuses & set(R.OPEN_STATUSES):
            raise LoanError("یک درخواست وام در حال بررسی دارید؛ تا نتیجه‌ی آن مشخص نشده درخواست جدید ممکن نیست")
        if policy.block_if_unsettled and R.STATUS_ACTIVE in statuses:
            raise LoanError("تا تسویه‌ی کامل وام قبلی، درخواست وام جدید ممکن نیست")

        guarantor_ids = []
        for gid in payload.get("guarantor_ids") or []:
            if gid not in guarantor_ids:
                guarantor_ids.append(gid)
        need = loan_type.guarantor_count or 0
        if len(guarantor_ids) != need:
            raise LoanError(f"این نوع وام {need} ضامن لازم دارد" if need else "این نوع وام ضامن نمی‌خواهد")
        people = await self._names(guarantor_ids)
        for gid in guarantor_ids:
            problem = await self._guarantor_problem(policy, employee, people.get(gid))
            if problem:
                raise LoanError(problem)

        policy_steps = R.normalize_steps(policy.approval_steps)
        unit_manager_id = site_manager_id = None
        if R.STEP_UNIT_MANAGER in policy_steps:
            unit_manager_id = await self.resolve_unit_manager(employee)
            if unit_manager_id is None:
                raise LoanError("مدیر واحد شما پیدا نشد (همان تأییدکننده‌ی مرخصی)؛ با منابع انسانی هماهنگ کنید")
        if R.STEP_SITE_MANAGER in policy_steps:
            settings = await self.site_settings(employee.site_id)
            site_manager_id = settings.site_manager_employee_id if settings else None
            if site_manager_id is None:
                raise LoanError("مدیر سایت برای تأیید وام تعیین نشده است؛ با واحد مالی یا منابع انسانی هماهنگ کنید")
        steps = R.effective_steps(
            policy_steps,
            guarantor_count=need,
            requester_id=employee.id,
            unit_manager_id=unit_manager_id,
            site_manager_id=site_manager_id,
        )

        req = LoanRequest(
            site_id=employee.site_id,
            employee_id=employee.id,
            policy_id=policy.id,
            loan_type_id=loan_type.id,
            type_title=loan_type.title,
            out_of_queue=loan_type.out_of_queue,
            extra_requirement=loan_type.extra_requirement,
            amount_requested=amount,
            reason=_clean(payload.get("reason")),
            service_months=service["months"],
            steps=steps,
            step_index=0,
            status=R.STATUS_IN_REVIEW,
            unit_manager_employee_id=unit_manager_id,
            site_manager_employee_id=site_manager_id,
            guarantors=[LoanRequestGuarantor(employee_id=gid, status="pending") for gid in guarantor_ids],
            events=[],
            installments=[],
        )
        self.db.add(req)
        self._event(req, "submitted", employee_label(employee), user.id)
        await self.db.flush()
        await self._enter_step(req)
        await self._commit()
        return await self.serialize(await self._load_request(req.id), detail=True)

    async def cancel(self, employee: Employee, user: User, request_id: int) -> dict:
        req = await self._load_request(request_id, lock=True)
        if req.employee_id != employee.id:
            raise LoanError("این درخواست متعلق به شما نیست", 403)
        if req.status not in R.OPEN_STATUSES:
            raise LoanError("فقط درخواستی که هنوز پرداخت نشده قابل لغو است")
        req.status = R.STATUS_CANCELLED
        req.current_approver_employee_id = None
        self._event(req, "cancelled", employee_label(employee), user.id)
        await self._commit()
        return await self.serialize(req, detail=True)

    async def replace_guarantor(
        self, employee: Employee, user: User, request_id: int, guarantor_row_id: int, new_employee_id: int
    ) -> dict:
        req = await self._load_request(request_id, lock=True)
        if req.employee_id != employee.id:
            raise LoanError("این درخواست متعلق به شما نیست", 403)
        if self.current_step(req) != R.STEP_GUARANTORS:
            raise LoanError("ضامن فقط در مرحله‌ی تأیید ضامن‌ها قابل تغییر است")
        row = next((g for g in req.guarantors if g.id == guarantor_row_id), None)
        if row is None or row.status == "accepted":
            raise LoanError("این ضامن قابل تغییر نیست")
        if any(g.employee_id == new_employee_id and g.id != row.id for g in req.guarantors):
            raise LoanError("این همکار قبلاً ضامن همین درخواست است")
        policy = await self.db.get(LoanPolicy, req.policy_id) if req.policy_id else None
        new = await self.db.get(Employee, new_employee_id)
        problem = await self._guarantor_problem(policy or LoanPolicy(), employee, new)
        if problem:
            raise LoanError(problem)
        old = await self.db.get(Employee, row.employee_id)
        row.employee_id = new.id
        row.status = "pending"
        row.note = None
        row.decided_at = None
        self._event(req, "guarantor_replaced", employee_label(employee), user.id, f"{employee_label(old)} ← {employee_label(new)}")
        self._push([new.id], "/loans?tab=inbox", "یک همکار شما را ضامن درخواست وام خود کرده است.")
        await self._commit()
        return await self.serialize(req, detail=True)

    async def inbox(self, employee: Employee) -> dict:
        guarantee_rows = (
            await self.db.execute(
                self._requests_query()
                .join(LoanRequestGuarantor, LoanRequestGuarantor.request_id == LoanRequest.id)
                .where(
                    LoanRequestGuarantor.employee_id == employee.id,
                    LoanRequestGuarantor.status == "pending",
                    LoanRequest.status == R.STATUS_IN_REVIEW,
                )
                .order_by(LoanRequest.created_at)
            )
        ).scalars().all()
        guarantee = [
            r for r in guarantee_rows if self.current_step(r) == R.STEP_GUARANTORS
        ]
        approvals = (
            await self.db.execute(
                self._requests_query()
                .where(
                    LoanRequest.current_approver_employee_id == employee.id,
                    LoanRequest.status == R.STATUS_IN_REVIEW,
                )
                .order_by(LoanRequest.created_at)
            )
        ).scalars().all()
        return {
            "guarantee": await self._serialize_many(list(guarantee)),
            "approvals": await self._serialize_many(list(approvals)),
        }

    async def inbox_count(self, employee: Employee) -> int:
        """شمارنده‌ی کارت «درخواست وام» (بدون ساختن کل کارتابل)."""
        rows = (
            await self.db.execute(
                select(LoanRequest.steps, LoanRequest.step_index)
                .join(LoanRequestGuarantor, LoanRequestGuarantor.request_id == LoanRequest.id)
                .where(
                    LoanRequestGuarantor.employee_id == employee.id,
                    LoanRequestGuarantor.status == "pending",
                    LoanRequest.status == R.STATUS_IN_REVIEW,
                )
            )
        ).all()
        guarantee = sum(
            1 for steps, idx in rows if 0 <= idx < len(steps or []) and steps[idx] == R.STEP_GUARANTORS
        )
        approvals = (
            await self.db.execute(
                select(func.count(LoanRequest.id)).where(
                    LoanRequest.current_approver_employee_id == employee.id,
                    LoanRequest.status == R.STATUS_IN_REVIEW,
                )
            )
        ).scalar_one()
        return guarantee + int(approvals)

    async def guarantee_decide(self, employee: Employee, user: User, request_id: int, accept: bool, note) -> dict:
        if not (employee.is_active and employee.is_enabled):
            raise LoanError("حساب پرسنلی شما فعال نیست", 403)
        req = await self._load_request(request_id, lock=True)
        if self.current_step(req) != R.STEP_GUARANTORS:
            raise LoanError("این درخواست دیگر در مرحله‌ی تأیید ضامن‌ها نیست")
        row = next((g for g in req.guarantors if g.employee_id == employee.id and g.status == "pending"), None)
        if row is None:
            raise LoanError("ضمانتی در انتظار تصمیم شما برای این درخواست نیست", 403)
        row.status = "accepted" if accept else "rejected"
        row.note = _clean(note)
        row.decided_at = _now()
        self._event(req, "guarantee_accepted" if accept else "guarantee_rejected", employee_label(employee), user.id, note)
        if accept and all(g.status == "accepted" for g in req.guarantors):
            await self._advance(req)
        elif not accept:
            self._push(
                [req.employee_id],
                "/loans?tab=mine",
                f"{employee.first_name} {employee.last_name} ضمانت وام شما را نپذیرفت؛ ضامن دیگری انتخاب کنید.",
            )
        await self._commit()
        return await self.serialize(req)

    async def approver_decide(self, employee: Employee, user: User, request_id: int, approve: bool, note) -> dict:
        if not (employee.is_active and employee.is_enabled):
            raise LoanError("حساب پرسنلی شما فعال نیست", 403)
        req = await self._load_request(request_id, lock=True)
        step = self.current_step(req)
        if step not in (R.STEP_UNIT_MANAGER, R.STEP_SITE_MANAGER) or req.current_approver_employee_id != employee.id:
            raise LoanError("این درخواست در انتظار تصمیم شما نیست", 403)
        if not approve and not _clean(note):
            raise LoanError("دلیل رد را بنویسید")
        label = f"{employee_label(employee)} — {R.STEP_LABELS[step]}"
        if approve:
            self._event(req, "approved", label, user.id, note)
            await self._advance(req)
        else:
            self._event(req, "rejected", label, user.id, note)
            req.status = R.STATUS_REJECTED
            req.current_approver_employee_id = None
            self._push([req.employee_id], "/loans?tab=mine", "درخواست وام شما رد شد.")
        await self._commit()
        return await self.serialize(req)

    # ---------- مدیریت: سایت و مقررات ----------

    async def admin_sites(self, site_ids: set[int] | None) -> list[dict]:
        stmt = select(Site).order_by(Site.id)
        if site_ids is not None:
            stmt = stmt.where(Site.id.in_(site_ids or {-1}))
        sites = (await self.db.execute(stmt)).scalars().all()
        settings = {
            s.site_id: s
            for s in (await self.db.execute(select(LoanSiteSettings))).scalars().all()
        }
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
                }
            )
        return out

    async def update_site_settings(self, site_id: int, is_enabled: bool, site_manager_employee_id: int | None) -> None:
        if (await self.db.get(Site, site_id)) is None:
            raise LoanError("سایت پیدا نشد", 404)
        if site_manager_employee_id is not None:
            manager = await self.db.get(Employee, site_manager_employee_id)
            if manager is None or manager.site_id != site_id:
                raise LoanError("مدیر سایت باید از پرسنل همین سایت باشد")
            if not (manager.is_active and manager.is_enabled):
                raise LoanError("پرسنل انتخاب‌شده برای مدیر سایت فعال نیست")
            has_user = (await self.db.execute(select(User.id).where(User.employee_id == manager.id).limit(1))).first()
            if not has_user:
                raise LoanError("مدیر سایت باید حساب کاربری پرتال داشته باشد تا بتواند تأیید کند")
        settings = await self.site_settings(site_id, create=True)
        settings.is_enabled = bool(is_enabled)
        settings.site_manager_employee_id = site_manager_employee_id
        await self.db.commit()

    async def list_policies(self, site_id: int) -> list[dict]:
        rows = (
            await self.db.execute(
                select(LoanPolicy)
                .options(selectinload(LoanPolicy.types))
                .where(LoanPolicy.site_id == site_id)
                .order_by(LoanPolicy.effective_from.desc(), LoanPolicy.id.desc())
            )
        ).scalars().all()
        current = await self.current_policy(site_id)
        today = _today()
        out = []
        for p in rows:
            d = self.policy_dict(p)
            d["is_current"] = current is not None and p.id == current.id
            d["is_future"] = p.effective_from > today
            out.append(d)
        return out

    async def get_policy(self, policy_id: int) -> LoanPolicy:
        policy = (
            await self.db.execute(
                select(LoanPolicy).options(selectinload(LoanPolicy.types)).where(LoanPolicy.id == policy_id)
            )
        ).scalar_one_or_none()
        if policy is None:
            raise LoanError("مقررات پیدا نشد", 404)
        return policy

    def _apply_policy(self, policy: LoanPolicy, data: dict) -> None:
        title = _clean(data.get("title"), 200)
        if not title:
            raise LoanError("عنوان مقررات را وارد کنید")
        effective = R.normalize_date(data.get("effective_from"))
        if not effective:
            raise LoanError("تاریخ اجرا نامعتبر است (مثال: 1405/07/15)")
        policy.title = title
        policy.effective_from = effective
        policy.rules_text = _clean(data.get("rules_text"), 20000)
        policy.block_if_unsettled = bool(data.get("block_if_unsettled", True))
        policy.approval_steps = R.normalize_steps(data.get("approval_steps"))

        def _opt_int(key):
            value = data.get(key)
            if value in (None, "", 0):
                return None
            try:
                value = int(value)
            except (TypeError, ValueError) as e:
                raise LoanError("مقدار قواعد ضامن نامعتبر است") from e
            if value < 0 or value > 1000:
                raise LoanError("مقدار قواعد ضامن نامعتبر است")
            return value

        policy.guarantor_max_active = _opt_int("guarantor_max_active")
        policy.guarantor_min_service_months = _opt_int("guarantor_min_service_months")
        policy.guarantor_no_active_loan = bool(data.get("guarantor_no_active_loan"))

        incoming = data.get("types") or []
        if not incoming:
            raise LoanError("حداقل یک نوع وام تعریف کنید")
        existing = {t.id: t for t in policy.types}
        keep: list[LoanType] = []
        for order, item in enumerate(incoming):
            t_title = _clean(item.get("title"), 200)
            if not t_title:
                raise LoanError("عنوان همه‌ی انواع وام را وارد کنید")
            try:
                max_amount = int(item.get("max_amount") or 0)
                min_months = int(item.get("min_service_months") or 0)
                g_count = int(item.get("guarantor_count") or 0)
            except (TypeError, ValueError) as e:
                raise LoanError(f"مقادیر عددی «{t_title}» نامعتبر است") from e
            if not (0 < max_amount <= R.MAX_AMOUNT):
                raise LoanError(f"سقف مبلغ «{t_title}» را وارد کنید")
            if not (0 <= min_months <= 600) or not (0 <= g_count <= 10):
                raise LoanError(f"مقادیر «{t_title}» نامعتبر است")
            t = existing.get(item.get("id")) or LoanType()
            t.title = t_title
            t.max_amount = max_amount
            t.min_service_months = min_months
            t.guarantor_count = g_count
            t.extra_requirement = _clean(item.get("extra_requirement"), 500)
            t.out_of_queue = bool(item.get("out_of_queue"))
            t.is_active = bool(item.get("is_active", True))
            t.sort_order = order
            keep.append(t)
        needs_guarantor = [t.title for t in keep if t.is_active and t.guarantor_count > 0]
        if needs_guarantor and R.STEP_GUARANTORS not in policy.approval_steps:
            raise LoanError(
                f"نوع «{needs_guarantor[0]}» ضامن می‌خواهد؛ مرحله‌ی «ضامن‌ها» را به مسیر تأیید اضافه کنید یا تعداد ضامن را صفر کنید"
            )
        policy.types[:] = keep

    async def create_policy(self, site_id: int, data: dict, copy_from: LoanPolicy | None = None) -> dict:
        """
        نسخه‌ی تازه‌ی مقررات. copy_from (همین سایت یا سایت دیگر): اگر انواع وام فرستاده نشده، انواع مبدأ کپی
        می‌شوند. بقیه‌ی فیلدها همان است که فرم فرستاده (فرم از مبدأ پر می‌شود).
        """
        if (await self.db.get(Site, site_id)) is None:
            raise LoanError("سایت پیدا نشد", 404)
        policy = LoanPolicy(site_id=site_id, types=[])
        if copy_from is not None:
            if not data.get("types"):
                data["types"] = [
                    {k: v for k, v in t.items() if k != "id"} for t in self.policy_dict(copy_from)["types"]
                ]
        self._apply_policy(policy, data)
        self.db.add(policy)
        await self.db.commit()
        return self.policy_dict(await self.get_policy(policy.id))

    async def update_policy(self, policy: LoanPolicy, data: dict) -> dict:
        self._apply_policy(policy, data)
        await self.db.commit()
        return self.policy_dict(await self.get_policy(policy.id))

    async def delete_policy(self, policy: LoanPolicy) -> None:
        used = (
            await self.db.execute(select(func.count(LoanRequest.id)).where(LoanRequest.policy_id == policy.id))
        ).scalar_one()
        if used:
            raise LoanError(
                f"این مقررات در {used} درخواست استفاده شده و قابل حذف نیست؛ برای تغییر، نسخه‌ی جدید با تاریخ اجرای تازه بسازید"
            )
        await self.db.delete(policy)
        await self.db.commit()

    # ---------- مدیریت: درخواست‌ها (مالی) ----------

    async def admin_list(self, site_id: int, status_filter: str | None) -> list[dict]:
        stmt = self._requests_query().where(LoanRequest.site_id == site_id)
        if status_filter == "open":
            stmt = stmt.where(LoanRequest.status.in_(R.OPEN_STATUSES))
        elif status_filter:
            stmt = stmt.where(LoanRequest.status == status_filter)
        rows = (await self.db.execute(stmt.order_by(LoanRequest.created_at.desc(), LoanRequest.id.desc()))).scalars().all()
        return await self._serialize_many(list(rows))

    async def admin_detail(self, request_id: int) -> tuple[LoanRequest, dict]:
        req = await self._load_request(request_id)
        return req, await self.serialize(req, detail=True)

    async def finance_pay(self, req: LoanRequest, user: User, data: dict) -> dict:
        if req.status != R.STATUS_WAITING_FINANCE:
            raise LoanError("فقط درخواستی که در صف پرداخت است قابل پرداخت است")
        if req.extra_requirement and not data.get("extra_confirmed"):
            raise LoanError(f"ابتدا دریافت «{req.extra_requirement}» را تأیید کنید")
        try:
            amount = R.validate_amount(data.get("amount_approved"), None)
            schedule = R.build_installments(
                amount,
                count=data.get("installment_count") or None,
                per_amount=data.get("installment_amount") or None,
                first_month=data.get("first_month"),
            )
        except R.LoanRuleError as e:
            raise LoanError(str(e)) from e
        req.amount_approved = amount
        req.extra_confirmed = bool(data.get("extra_confirmed"))
        req.finance_note = _clean(data.get("note"))
        req.installments[:] = [LoanInstallment(**row) for row in schedule]
        req.status = R.STATUS_ACTIVE
        req.paid_at = _now()
        self._event(
            req,
            "paid",
            await self._actor(user),
            user.id,
            f"مبلغ {amount:,} ریال در {len(schedule)} قسط از {schedule[0]['due_month']}"
            + (f" — {req.finance_note}" if req.finance_note else ""),
        )
        self._push(
            [req.employee_id],
            "/loans?tab=mine",
            f"وام شما به مبلغ {amount:,} ریال پرداخت شد؛ جدول اقساط در پرتال است.",
        )
        await self._commit()
        return await self.serialize(req, detail=True)

    async def finance_reject(self, req: LoanRequest, user: User, note) -> dict:
        if req.status not in R.OPEN_STATUSES:
            raise LoanError("فقط درخواست باز (پرداخت‌نشده) قابل رد است")
        if not _clean(note):
            raise LoanError("دلیل رد را بنویسید")
        req.status = R.STATUS_REJECTED
        req.current_approver_employee_id = None
        self._event(req, "rejected", f"{await self._actor(user)} — واحد مالی", user.id, note)
        self._push([req.employee_id], "/loans?tab=mine", "درخواست وام شما رد شد.")
        await self._commit()
        return await self.serialize(req, detail=True)

    async def finance_set_queue(self, req: LoanRequest, user: User, queue_seq: int) -> dict:
        if req.status != R.STATUS_WAITING_FINANCE or req.out_of_queue:
            raise LoanError("نوبت فقط برای درخواست‌های داخل صف قابل تغییر است")
        if not (1 <= int(queue_seq) <= 1_000_000):
            raise LoanError("شماره‌ی نوبت نامعتبر است")
        old = req.queue_seq
        req.queue_seq = int(queue_seq)
        await self._bump_queue_seq(req.site_id, req.queue_seq)
        self._event(req, "queue_changed", await self._actor(user), user.id, f"{old or '-'} ← {req.queue_seq}")
        await self._commit()
        return await self.serialize(req, detail=True)

    async def finance_toggle_installment(self, installment_id: int, user: User, site_ids: set[int] | None) -> dict:
        request_id = (
            await self.db.execute(select(LoanInstallment.request_id).where(LoanInstallment.id == installment_id))
        ).scalar_one_or_none()
        if request_id is None:
            raise LoanError("قسط پیدا نشد", 404)
        req = await self._load_request(request_id, lock=True)
        if site_ids is not None and req.site_id not in site_ids:
            raise LoanError("دسترسی لازم برای این عملیات را ندارید", 403)
        if req.status not in (R.STATUS_ACTIVE, R.STATUS_SETTLED):
            raise LoanError("اقساط این درخواست قابل تغییر نیست")
        inst = next(i for i in req.installments if i.id == installment_id)
        inst.paid_at = None if inst.paid_at else _now()
        self._event(
            req, "installment_paid" if inst.paid_at else "installment_unpaid", await self._actor(user), user.id, f"قسط {inst.seq} ({inst.due_month})"
        )
        if all(i.paid_at for i in req.installments):
            if req.status != R.STATUS_SETTLED:
                req.status = R.STATUS_SETTLED
                req.settled_at = _now()
                self._event(req, "settled", await self._actor(user), user.id, "همه‌ی اقساط پرداخت شد")
                self._push([req.employee_id], "/loans?tab=mine", "وام شما تسویه شد.")
        elif req.status == R.STATUS_SETTLED:
            req.status = R.STATUS_ACTIVE
            req.settled_at = None
            self._event(req, "unsettled", await self._actor(user), user.id, "یک قسط پرداخت‌نشده شد؛ وام دوباره باز است")
        await self._commit()
        return await self.serialize(req, detail=True)

    async def finance_settle(self, req: LoanRequest, user: User, note) -> dict:
        if req.status != R.STATUS_ACTIVE:
            raise LoanError("فقط وام در حال بازپرداخت قابل تسویه است")
        now = _now()
        for inst in req.installments:
            if not inst.paid_at:
                inst.paid_at = now
        req.status = R.STATUS_SETTLED
        req.settled_at = now
        self._event(req, "settled", await self._actor(user), user.id, note or "تسویه‌ی یکجا")
        self._push([req.employee_id], "/loans?tab=mine", "وام شما تسویه شد.")
        await self._commit()
        return await self.serialize(req, detail=True)

    async def finance_manual(self, site_id: int, user: User, data: dict) -> dict:
        """ثبت دستی مالی (نوبت‌های قبلی، بند «نوبت‌های قبلی حفظ می‌شود»): مستقیم در صف پرداخت، بدون مسیر تأیید."""
        employee = await self.db.get(Employee, data.get("employee_id"))
        if employee is None or employee.site_id != site_id:
            raise LoanError("پرسنل انتخاب‌شده از این سایت نیست")
        # همان قفل ثبت درخواست پرسنل تا هم‌زمانی دو درخواست باز نسازد
        await self.db.execute(select(Employee.id).where(Employee.id == employee.id).with_for_update())
        open_exists = (
            await self.db.execute(
                select(LoanRequest.id)
                .where(LoanRequest.employee_id == employee.id, LoanRequest.status.in_(R.OPEN_STATUSES))
                .limit(1)
            )
        ).first()
        if open_exists:
            raise LoanError("این پرسنل یک درخواست وام باز دارد")
        policy = await self.current_policy(site_id)
        loan_type = next((t for t in (policy.types if policy else []) if t.id == data.get("loan_type_id")), None)
        title = loan_type.title if loan_type else _clean(data.get("type_title"), 200)
        if not title:
            raise LoanError("نوع وام را انتخاب کنید")
        try:
            amount = R.validate_amount(data.get("amount"), None)
        except R.LoanRuleError as e:
            raise LoanError(str(e)) from e
        out_of_queue = bool(loan_type.out_of_queue) if loan_type else bool(data.get("out_of_queue"))
        req = LoanRequest(
            site_id=site_id,
            employee_id=employee.id,
            policy_id=policy.id if policy and loan_type else None,
            loan_type_id=loan_type.id if loan_type else None,
            type_title=title,
            out_of_queue=out_of_queue,
            extra_requirement=loan_type.extra_requirement if loan_type else None,
            amount_requested=amount,
            reason=_clean(data.get("note")),
            service_months=(await self.service_info(employee))["months"],
            steps=[R.STEP_FINANCE],
            step_index=0,
            status=R.STATUS_WAITING_FINANCE,
            is_manual=True,
            guarantors=[],
            events=[],
            installments=[],
        )
        seq = data.get("queue_seq")
        if seq and not out_of_queue:
            req.queue_seq = int(seq)
            await self._bump_queue_seq(site_id, req.queue_seq)
        elif not out_of_queue:
            req.queue_seq = await self._next_queue_seq(site_id)
        self.db.add(req)
        self._event(req, "manual", await self._actor(user), user.id, data.get("note"))
        await self.db.flush()
        await self._commit()
        return await self.serialize(await self._load_request(req.id), detail=True)

    async def list_overrides(self, site_id: int) -> list[dict]:
        rows = (
            await self.db.execute(
                select(LoanServiceOverride, Employee)
                .join(Employee, Employee.id == LoanServiceOverride.employee_id)
                .where(Employee.site_id == site_id)
                .order_by(Employee.last_name)
            )
        ).all()
        out = []
        for ov, emp in rows:
            out.append(
                {
                    "employee_id": emp.id,
                    "employee": employee_label(emp),
                    "hire_date": R.normalize_date(emp.hire_date_jalali),
                    "start_date": ov.start_date,
                    "note": ov.note,
                }
            )
        return out

    async def set_override(self, employee: Employee, user: User, start_date, note) -> None:
        start = R.normalize_date(start_date)
        if not start:
            raise LoanError("تاریخ شروع سابقه نامعتبر است (مثال: 1398/01/15)")
        if not _clean(note):
            raise LoanError("دلیل اصلاح سابقه را بنویسید")
        row = (
            await self.db.execute(select(LoanServiceOverride).where(LoanServiceOverride.employee_id == employee.id))
        ).scalar_one_or_none()
        if row is None:
            row = LoanServiceOverride(employee_id=employee.id)
            self.db.add(row)
        row.start_date = start
        row.note = _clean(note)
        row.set_by_user_id = user.id
        await self.db.commit()

    async def delete_override(self, employee_id: int) -> None:
        row = (
            await self.db.execute(select(LoanServiceOverride).where(LoanServiceOverride.employee_id == employee_id))
        ).scalar_one_or_none()
        if row is not None:
            await self.db.delete(row)
            await self.db.commit()

    async def search_site_employees(self, site_id: int, q: str | None) -> list[dict]:
        stmt = select(Employee).where(Employee.site_id == site_id, Employee.is_active.is_(True))
        text = (q or "").strip()
        if text:
            like = f"%{text}%"
            stmt = stmt.where(
                or_((Employee.first_name + " " + Employee.last_name).ilike(like), Employee.personnel_code.ilike(like))
            )
        rows = (await self.db.execute(stmt.order_by(Employee.last_name, Employee.first_name).limit(20))).scalars().all()
        return [{"id": e.id, "label": employee_label(e)} for e in rows]


