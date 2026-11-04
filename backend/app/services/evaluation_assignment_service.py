"""
سرویس «تولید انتساب‌های ارزیابی»: برای یک دوره و فرم مشخص، با get_evaluation_targets
(چه کسی مجاز به ارزیابی چه کسی است) برای همه پرسنل واجد شرایط رکورد EvaluationAssignment می‌سازد.

اجرای مجدد پس از تغییر ساختار سازمانی (پرسنل یا سرپرست جدید) امن است: جفت‌های موجود نادیده گرفته می‌شوند،
انتساب‌های جدید اضافه می‌شوند و انتساب‌هایی که دیگر با ساختار نمی‌خوانند (مثلاً فرد به فهرست یک مدیر منتقل شده) اگر
هنوز ارزیابی‌شان شروع نشده حذف می‌شوند. ارزیابی شروع‌شده/ثبت‌شده هرگز حذف نمی‌شود.

reconcile_target: همین کار فقط برای یک نفر در همه‌ی دوره‌های باز — بلافاصله بعد از جابه‌جایی او در ساختار
(افزودن/حذف از فهرست مدیر، سرشیفت) صدا زده می‌شود تا ارزیاب قبلی دیگر او را در کارتابل نبیند و ارزیاب جدید ببیند.
"""
from __future__ import annotations

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Department, Employee
from app.models.evaluation import (
    EvaluationDepartmentSupervisor,
    EvaluationManager,
    EvaluationManagerAssignment,
    EvaluationShiftAssignment,
    EvaluationShiftLead,
)
from app.models.evaluation_content import EvaluationForm, EvaluationPeriod
from app.models.evaluation_process import Evaluation, EvaluationAssignment
from app.services.evaluation_exemption_service import (
    OPEN_PERIOD_STATUSES,
    exemption_sets,
)
from app.services.evaluation_structure_service import EvaluationStructureService


class EvaluationAssignmentError(Exception):
    """خطای قابل نمایش به کاربر در تولید انتساب‌ها (مثلاً دوره/فرم یافت نشد)."""


class EvaluationAssignmentService:
    """سرویس تولید انتساب‌های ارزیابی یک دوره."""

    def __init__(self, db: AsyncSession):
        """ورودی: نشست async دیتابیس."""
        self.db = db

    SCOPES = ("site", "departments", "supervisors", "employees")

    async def _scope_targets(self, period: EvaluationPeriod, scope: str, department_ids, employee_ids) -> set[int] | None:
        """
        ارزیابی‌شونده‌های یک دامنه (فقط «چه کسی ارزیابی شود»؛ ارزیاب‌ها از ساختار): None = کل سایت دوره.
        departments: پرسنل واحدهای انتخابی. supervisors: سرپرستان ارزیابی واحدها (اختیاری محدود به واحدهای انتخابی).
        employees: همان افراد. همه محدود به سایت دوره (اگر دوره سراسری نیست).
        """
        if scope == "site":
            return None
        if scope == "departments":
            if not department_ids:
                raise EvaluationAssignmentError("حداقل یک واحد انتخاب کنید")
            stmt = select(Employee.id).where(Employee.department_id.in_(department_ids))
        elif scope == "supervisors":
            stmt = select(EvaluationDepartmentSupervisor.employee_id.label("id")).join(
                Employee, Employee.id == EvaluationDepartmentSupervisor.employee_id
            )
            if department_ids:
                stmt = stmt.where(EvaluationDepartmentSupervisor.department_id.in_(department_ids))
        elif scope == "employees":
            if not employee_ids:
                raise EvaluationAssignmentError("حداقل یک نفر انتخاب کنید")
            stmt = select(Employee.id).where(Employee.id.in_(employee_ids))
        else:
            raise EvaluationAssignmentError("دامنه‌ی تولید انتساب نامعتبر است")
        if period.site_id is not None:
            stmt = stmt.where(Employee.site_id == period.site_id)
        return set((await self.db.execute(stmt)).scalars().all())

    async def generate_assignments(
        self,
        period_id: int,
        form_id: int,
        scope: str = "site",
        department_ids: list[int] | None = None,
        employee_ids: list[int] | None = None,
    ) -> dict:
        """
        ورودی: دوره، فرم و دامنه‌ی ارزیابی‌شونده‌ها (site / departments / supervisors / employees).
        برای ارزیابی‌شونده‌های همان دامنه، از روی ساختار ارزیابی انتساب با همین فرم ساخته می‌شود.
        - جفت (ارزیاب، ارزیابی‌شونده) که در این دوره با همین فرم هست، تکراری ساخته نمی‌شود.
        - جفتی که در این دوره با فرم دیگری ارزیابی‌اش شروع شده، دست نمی‌خورد و با این فرم هم ساخته نمی‌شود.
        - انتساب‌های شروع‌نشده‌ی ارزیابی‌شونده‌های همین دامنه که دیگر با ساختار نمی‌خوانند یا فرم دیگری دارند حذف
          می‌شوند (هر گروه فرم خودش را دارد)؛ به انتساب‌های بیرون از دامنه دست زده نمی‌شود.
        خروجی: {"created_count", "removed_count", "total_assignments" (انتساب‌های این دوره+فرم)، "targets_count"}.
        """
        period = await self.db.get(EvaluationPeriod, period_id)
        if period is None:
            raise EvaluationAssignmentError("دوره ارزیابی موردنظر یافت نشد")
        form = await self.db.get(EvaluationForm, form_id)
        if form is None:
            raise EvaluationAssignmentError("فرم ارزیابی موردنظر یافت نشد")
        if period.incomplete_closed:
            raise EvaluationAssignmentError("ارزیابی‌های انجام‌نشده‌ی این دوره بسته شده است؛ برای تولید انتساب اول دوره را فعال کنید")
        scope_ids = await self._scope_targets(period, scope, department_ids, employee_ids)

        # ارزیاب‌های ممکن: یا همان سایت دوره، یا (اگر دوره سراسری است) همه پرسنل
        employees_query = select(Employee).where(Employee.is_enabled.is_(True))
        if period.site_id is not None:
            employees_query = employees_query.where(Employee.site_id == period.site_id)
        employees_result = await self.db.execute(employees_query)
        # معاف از ارزیابی (Migration 110): هیچ معافی هدف نیست؛ معافیت «کامل» ارزیاب هم نیست
        exempt_ids, full_exempt_ids = await exemption_sets(self.db)
        employees = [e for e in employees_result.scalars().all() if e.id not in full_exempt_ids]

        structure_service = EvaluationStructureService(self.db)
        # همه‌ی انتساب‌های این دوره (همه‌ی فرم‌ها): (ارزیاب، هدف) → [(شناسه، فرم، شروع‌شده؟)]
        started_ids = set((await self.db.execute(
            select(Evaluation.assignment_id).join(EvaluationAssignment, EvaluationAssignment.id == Evaluation.assignment_id)
            .where(EvaluationAssignment.period_id == period_id)
        )).scalars().all())
        current: dict[tuple[int, int], list[tuple[int, int, bool]]] = {}
        for aid, ev, tg, fid in (await self.db.execute(
            select(EvaluationAssignment.id, EvaluationAssignment.evaluator_employee_id,
                   EvaluationAssignment.target_employee_id, EvaluationAssignment.form_id)
            .where(EvaluationAssignment.period_id == period_id)
        )).all():
            current.setdefault((ev, tg), []).append((aid, fid, aid in started_ids))

        created_count = 0
        valid_pairs: set[tuple[int, int]] = set()
        targets_seen: set[int] = set()
        for employee in employees:
            resolution = await structure_service.get_evaluation_targets(employee.id)
            for target in resolution["targets"]:
                if scope_ids is not None and target.id not in scope_ids:
                    continue
                # هدف معاف یا پرسنل غیرفعال/قطع همکاری در کاراوب ارزیابی نمی‌شود؛ غیرفعال بودن حساب پرتال اثری ندارد
                if target.id in exempt_ids or not target.is_active:
                    continue
                pair = (employee.id, target.id)
                if pair in valid_pairs:
                    continue
                valid_pairs.add(pair)
                targets_seen.add(target.id)
                rows = current.get(pair, [])
                if any(fid == form_id for _, fid, _ in rows) or any(st for _, _, st in rows):
                    continue  # با همین فرم هست، یا با فرم دیگری شروع شده (دست نمی‌خورد)
                self.db.add(
                    EvaluationAssignment(
                        period_id=period_id,
                        form_id=form_id,
                        evaluator_employee_id=employee.id,
                        target_employee_id=target.id,
                    )
                )
                created_count += 1

        # حذف: انتساب‌های شروع‌نشده‌ی ارزیابی‌شونده‌های این دامنه که دیگر معتبر نیستند یا فرم دیگری دارند
        stale_ids = [
            aid
            for (ev, tg), rows in current.items()
            if scope_ids is None or tg in scope_ids
            for aid, fid, st in rows
            if not st and ((ev, tg) not in valid_pairs or fid != form_id)
        ]
        if stale_ids:
            await self.db.execute(delete(EvaluationAssignment).where(EvaluationAssignment.id.in_(stale_ids)))

        await self.db.commit()
        total = len((await self.db.execute(
            select(EvaluationAssignment.id).where(EvaluationAssignment.period_id == period_id, EvaluationAssignment.form_id == form_id)
        )).all())
        return {
            "created_count": created_count,
            "removed_count": len(stale_ids),
            "total_assignments": total,
            "targets_count": len(targets_seen),
        }

    async def scope_options(self, period_id: int) -> dict:
        """واحدهای سایت دوره و تعداد سرپرستان ارزیابی، برای دیالوگ تولید انتساب."""
        period = await self.db.get(EvaluationPeriod, period_id)
        if period is None:
            raise EvaluationAssignmentError("دوره ارزیابی موردنظر یافت نشد")
        stmt = select(Department).order_by(Department.name)
        if period.site_id is not None:
            stmt = stmt.where(Department.site_id == period.site_id)
        departments = (await self.db.execute(stmt)).scalars().all()
        sup = dict((await self.db.execute(
            select(EvaluationDepartmentSupervisor.department_id, EvaluationDepartmentSupervisor.employee_id)
        )).all())
        return {"departments": [{"id": d.id, "name": d.name, "has_supervisor": d.id in sup} for d in departments]}

    async def scope_people(self, period_id: int, q: str = "") -> list[dict]:
        """جستجوی پرسنل فعال سایت دوره برای دامنه‌ی «افراد خاص»."""
        period = await self.db.get(EvaluationPeriod, period_id)
        if period is None:
            raise EvaluationAssignmentError("دوره ارزیابی موردنظر یافت نشد")
        stmt = (
            select(Employee, Department.name)
            .outerjoin(Department, Department.id == Employee.department_id)
            .where(Employee.is_active.is_(True))  # حساب پرتال غیرفعال هم ارزیابی می‌شود
            .order_by(Employee.last_name, Employee.first_name)
            .limit(50)
        )
        if period.site_id is not None:
            stmt = stmt.where(Employee.site_id == period.site_id)
        for word in (q or "").split()[:4]:
            like = f"%{word}%"
            stmt = stmt.where(or_(Employee.first_name.ilike(like), Employee.last_name.ilike(like),
                                  Employee.personnel_code.ilike(like), Department.name.ilike(like)))
        return [{"id": e.id, "name": f"{e.first_name} {e.last_name}".strip(), "department": d}
                for e, d in (await self.db.execute(stmt)).all()]

    async def _remove_stale(self, period_id: int, form_id: int, pairs: set[tuple[int, int]]) -> int:
        """انتساب‌های این جفت‌ها را در دوره+فرم حذف می‌کند، فقط اگر هنوز Evaluation (پیش‌نویس/ثبت‌شده) ندارند. بدون commit."""
        if not pairs:
            return 0
        started = select(Evaluation.assignment_id)
        rows = (
            await self.db.execute(
                select(EvaluationAssignment.id, EvaluationAssignment.evaluator_employee_id, EvaluationAssignment.target_employee_id)
                .where(
                    EvaluationAssignment.period_id == period_id,
                    EvaluationAssignment.form_id == form_id,
                    EvaluationAssignment.id.not_in(started),
                )
            )
        ).all()
        ids = [aid for aid, ev, tg in rows if (ev, tg) in pairs]
        if ids:
            await self.db.execute(delete(EvaluationAssignment).where(EvaluationAssignment.id.in_(ids)))
        return len(ids)

    async def reconcile_target(self, target_employee_id: int) -> dict:
        """
        بعد از جابه‌جایی یک نفر در ساختار ارزیابی (افزودن/حذف از فهرست مدیر، تغییر سرشیفت): در همه‌ی دوره‌های باز که او
        انتساب دارد، انتساب ارزیاب‌های قبلی که دیگر او را ندارند (و شروع نشده) حذف و انتساب ارزیاب‌های فعلی‌اش اضافه می‌شود.
        خروجی: {"created_count", "removed_count"}. commit می‌کند.
        """
        target = await self.db.get(Employee, target_employee_id)
        if target is None:
            return {"created_count": 0, "removed_count": 0}

        # دوره+فرم‌های باز (غیرغیرفعال) که این فرد در آن‌ها انتساب دارد
        combos = (
            await self.db.execute(
                select(EvaluationAssignment.period_id, EvaluationAssignment.form_id, EvaluationPeriod.site_id)
                .join(EvaluationPeriod, EvaluationPeriod.id == EvaluationAssignment.period_id)
                .where(
                    EvaluationAssignment.target_employee_id == target_employee_id,
                    EvaluationPeriod.status.in_(OPEN_PERIOD_STATUSES),
                    EvaluationPeriod.is_disabled.is_(False),
                    EvaluationPeriod.incomplete_closed.is_(False),
                )
                .distinct()
            )
        ).all()
        if not combos:
            return {"created_count": 0, "removed_count": 0}

        # ارزیاب‌های ممکن این فرد: ارزیاب‌های فعلی انتساب‌ها + مدیر(ان) او + سرپرست واحدش + سرشیفتش
        candidates: set[int] = set(
            (
                await self.db.execute(
                    select(EvaluationAssignment.evaluator_employee_id).where(
                        EvaluationAssignment.target_employee_id == target_employee_id
                    )
                )
            ).scalars().all()
        )
        candidates.update(
            (
                await self.db.execute(
                    select(EvaluationManager.employee_id)
                    .join(EvaluationManagerAssignment, EvaluationManagerAssignment.manager_id == EvaluationManager.id)
                    .where(EvaluationManagerAssignment.target_employee_id == target_employee_id)
                )
            ).scalars().all()
        )
        if target.department_id is not None:
            candidates.update(
                (
                    await self.db.execute(
                        select(EvaluationDepartmentSupervisor.employee_id).where(
                            EvaluationDepartmentSupervisor.department_id == target.department_id
                        )
                    )
                ).scalars().all()
            )
        candidates.update(
            (
                await self.db.execute(
                    select(EvaluationShiftLead.employee_id)
                    .join(EvaluationShiftAssignment, EvaluationShiftAssignment.shift_lead_id == EvaluationShiftLead.id)
                    .where(EvaluationShiftAssignment.employee_id == target_employee_id)
                )
            ).scalars().all()
        )
        candidates.discard(target_employee_id)

        exempt_ids, full_exempt_ids = await exemption_sets(self.db)
        target_ok = target.id not in exempt_ids and target.is_active  # حساب پرتال اثری ندارد
        structure_service = EvaluationStructureService(self.db)
        evaluators = {
            e.id: e
            for e in (await self.db.execute(select(Employee).where(Employee.id.in_(candidates)))).scalars().all()
        }
        valid_evaluators: set[int] = set()
        for evaluator_id, evaluator in evaluators.items():
            if not evaluator.is_enabled or evaluator_id in full_exempt_ids:
                continue
            resolution = await structure_service.get_evaluation_targets(evaluator_id)
            if any(t.id == target_employee_id for t in resolution["targets"]):
                valid_evaluators.add(evaluator_id)

        created = removed = 0
        for period_id, form_id, period_site_id in combos:
            existing = set(
                (
                    await self.db.execute(
                        select(EvaluationAssignment.evaluator_employee_id).where(
                            EvaluationAssignment.period_id == period_id,
                            EvaluationAssignment.form_id == form_id,
                            EvaluationAssignment.target_employee_id == target_employee_id,
                        )
                    )
                ).scalars().all()
            )
            # ارزیاب‌های این دوره: همان قاعده‌ی تولید (سایت دوره، اگر دوره سراسری نیست)
            allowed = {
                eid
                for eid in valid_evaluators
                if target_ok and (period_site_id is None or evaluators[eid].site_id == period_site_id)
            }
            stale = {(eid, target_employee_id) for eid in existing - allowed}
            removed += await self._remove_stale(period_id, form_id, stale)
            for eid in allowed - existing:
                self.db.add(
                    EvaluationAssignment(
                        period_id=period_id, form_id=form_id, evaluator_employee_id=eid, target_employee_id=target_employee_id
                    )
                )
                created += 1
        await self.db.commit()
        return {"created_count": created, "removed_count": removed}
