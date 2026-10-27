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

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
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

    async def generate_assignments(self, period_id: int, form_id: int) -> dict:
        """
        ورودی: شناسه دوره و فرم. برای هر پرسنل فعال (سایت دوره یا همه، اگر دوره سراسری باشد)
        اهداف ارزیابی‌اش را پیدا کرده و انتساب‌های جدید را می‌سازد.
        خروجی: {"created_count", "total_assignments"}؛ اگر دوره/فرم نباشد EvaluationAssignmentError.
        """
        period = await self.db.get(EvaluationPeriod, period_id)
        if period is None:
            raise EvaluationAssignmentError("دوره ارزیابی موردنظر یافت نشد")
        form = await self.db.get(EvaluationForm, form_id)
        if form is None:
            raise EvaluationAssignmentError("فرم ارزیابی موردنظر یافت نشد")

        # پرسنل واجد شرایط: یا همان سایت دوره، یا (اگر دوره سراسری است) همه پرسنل
        employees_query = select(Employee).where(Employee.is_enabled.is_(True))
        if period.site_id is not None:
            employees_query = employees_query.where(Employee.site_id == period.site_id)
        employees_result = await self.db.execute(employees_query)
        # معاف از ارزیابی (Migration 110): هیچ معافی هدف نیست؛ معافیت «کامل» ارزیاب هم نیست
        exempt_ids, full_exempt_ids = await exemption_sets(self.db)
        employees = [e for e in employees_result.scalars().all() if e.id not in full_exempt_ids]

        structure_service = EvaluationStructureService(self.db)
        # جفت‌های (ارزیاب، هدف) موجود برای همین دوره+فرم، تا تکراری ساخته نشوند
        existing_result = await self.db.execute(
            select(EvaluationAssignment.evaluator_employee_id, EvaluationAssignment.target_employee_id).where(
                EvaluationAssignment.period_id == period_id, EvaluationAssignment.form_id == form_id
            )
        )
        existing_pairs = {(row[0], row[1]) for row in existing_result.all()}

        # برای هر پرسنل، اهداف ارزیابی‌اش را گرفته و انتساب‌های جدید را اضافه می‌کند
        created_count = 0
        valid_pairs: set[tuple[int, int]] = set()
        for employee in employees:
            resolution = await structure_service.get_evaluation_targets(employee.id)
            for target in resolution["targets"]:
                # هدف معاف، یا پرسنل غیرفعال/قطع همکاری در کاراوب یا غیرفعال‌شده در پرتال، ارزیابی نمی‌شود
                if target.id in exempt_ids or not (target.is_active and target.is_enabled):
                    continue
                pair = (employee.id, target.id)
                valid_pairs.add(pair)
                if pair in existing_pairs:
                    continue
                self.db.add(
                    EvaluationAssignment(
                        period_id=period_id,
                        form_id=form_id,
                        evaluator_employee_id=employee.id,
                        target_employee_id=target.id,
                    )
                )
                existing_pairs.add(pair)  # جلوگیری از تکرار در همین اجرا
                created_count += 1

        # انتساب‌هایی که دیگر با ساختار نمی‌خوانند (و ارزیابی‌شان شروع نشده) حذف می‌شوند
        removed_count = await self._remove_stale(period_id, form_id, existing_pairs - valid_pairs)

        await self.db.commit()
        return {
            "created_count": created_count,
            "removed_count": removed_count,
            "total_assignments": len(existing_pairs) - removed_count,
        }

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
        target_ok = target.id not in exempt_ids and target.is_active and target.is_enabled
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
