"""
سرویس «تولید انتساب‌های ارزیابی»: برای یک دوره و فرم مشخص، با get_evaluation_targets
(چه کسی مجاز به ارزیابی چه کسی است) برای همه پرسنل واجد شرایط رکورد EvaluationAssignment می‌سازد.

اجرای مجدد پس از تغییر ساختار سازمانی (پرسنل یا سرپرست جدید) امن است: جفت‌های موجود
نادیده گرفته می‌شوند و فقط انتساب‌های جدید اضافه می‌شوند.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.evaluation_exemption_service import exemption_sets
from app.models.employee import Employee
from app.models.evaluation_content import EvaluationForm, EvaluationPeriod
from app.models.evaluation_process import EvaluationAssignment
from app.services.evaluation_structure_service import EvaluationStructureService


class EvaluationAssignmentError(Exception):
    """خطای قابل نمایش به کاربر در تولید انتساب‌ها (مثلاً دوره/فرم یافت نشد)."""
    pass


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
        for employee in employees:
            resolution = await structure_service.get_evaluation_targets(employee.id)
            for target in resolution["targets"]:
                # هدف معاف، یا پرسنل غیرفعال/قطع همکاری در کاراوب یا غیرفعال‌شده در پرتال، ارزیابی نمی‌شود
                if target.id in exempt_ids or not (target.is_active and target.is_enabled):
                    continue
                pair = (employee.id, target.id)
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

        await self.db.commit()
        return {"created_count": created_count, "total_assignments": len(existing_pairs)}
