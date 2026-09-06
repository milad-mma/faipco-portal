"""
سرویس «تولید انتساب‌های ارزیابی» - برای یک دوره + فرم مشخص، با استفاده
از get_evaluation_targets (مرحله اول: چه کسی مجاز به ارزیابی چه کسی
است)، برای تمام پرسنل واجد شرایط، رکوردهای EvaluationAssignment می‌سازد.

⚠️ Dynamic بودن (طبق طرح اولیه، بخش ۸): این تابع را می‌توان هر زمان که
ساختار سازمانی تغییر کرد (پرسنل جدید، سرپرست جدید) دوباره اجرا کرد -
Assignment های تکراری نادیده گرفته می‌شوند (UniqueConstraint) - یعنی
Admin مجبور نیست برای هر تغییر، دستی Assignment جدید بسازد.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.evaluation_content import EvaluationForm, EvaluationPeriod
from app.models.evaluation_process import EvaluationAssignment
from app.services.evaluation_structure_service import EvaluationStructureService


class EvaluationAssignmentError(Exception):
    pass


class EvaluationAssignmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_assignments(self, period_id: int, form_id: int) -> dict:
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
        employees = employees_result.scalars().all()

        structure_service = EvaluationStructureService(self.db)
        existing_result = await self.db.execute(
            select(EvaluationAssignment.evaluator_employee_id, EvaluationAssignment.target_employee_id).where(
                EvaluationAssignment.period_id == period_id, EvaluationAssignment.form_id == form_id
            )
        )
        existing_pairs = {(row[0], row[1]) for row in existing_result.all()}

        created_count = 0
        for employee in employees:
            resolution = await structure_service.get_evaluation_targets(employee.id)
            for target in resolution["targets"]:
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
                existing_pairs.add(pair)
                created_count += 1

        await self.db.commit()
        return {"created_count": created_count, "total_assignments": len(existing_pairs)}
