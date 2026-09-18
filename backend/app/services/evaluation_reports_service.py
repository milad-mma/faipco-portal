"""
سرویس «گزارش‌های مدیریتی ارزیابی عملکرد» - میانگین واحد/سایت برای یک
دوره، و مقایسه بین دو دوره. برخلاف evaluation_process_service.py که
دیدگاه فردی (خودِ کاربر) دارد، این سرویس دیدگاه تجمیعی/مدیریتی دارد.

⚠️ همه Query ها فقط از Evaluation های status=submitted استفاده
می‌کنند - ارزیابی‌های Draft هنوز نهایی نشده‌اند و نباید در میانگین‌های
مدیریتی حساب شوند.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Department, Employee
from app.models.evaluation_content import EvaluationPeriod
from app.models.evaluation_process import Evaluation, EvaluationAnswer, EvaluationAssignment, EvaluationStatus
from app.models.site import Site


class EvaluationReportError(Exception):
    pass


class EvaluationReportsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _department_stats(self, department_id: int, period_id: int) -> dict:
        result = await self.db.execute(
            select(
                func.avg(Evaluation.total_score),
                func.count(Evaluation.id),
                func.min(Evaluation.total_score),
                func.max(Evaluation.total_score),
            )
            .join(EvaluationAssignment, EvaluationAssignment.id == Evaluation.assignment_id)
            .join(Employee, Employee.id == EvaluationAssignment.target_employee_id)
            .where(
                Employee.department_id == department_id,
                EvaluationAssignment.period_id == period_id,
                Evaluation.status == EvaluationStatus.submitted,
            )
        )
        average, count, minimum, maximum = result.one()
        return {
            "average_score": float(average) if average is not None else None,
            "count": count,
            "min_score": float(minimum) if minimum is not None else None,
            "max_score": float(maximum) if maximum is not None else None,
        }

    async def _department_employee_scores(self, department_id: int, period_id: int) -> list[dict]:
        result = await self.db.execute(
            select(
                Employee.first_name,
                Employee.last_name,
                Employee.personnel_code,
                Evaluation.total_score,
                Evaluation.id,
            )
            .join(EvaluationAssignment, EvaluationAssignment.id == Evaluation.assignment_id)
            .join(Employee, Employee.id == EvaluationAssignment.target_employee_id)
            .where(
                Employee.department_id == department_id,
                EvaluationAssignment.period_id == period_id,
                Evaluation.status == EvaluationStatus.submitted,
            )
            .order_by(Evaluation.total_score.desc())
        )
        # ⚠️ evaluation_id برای Drill-down جزئیات سوال‌به‌سوال در گزارش
        # مدیریتی لازم است (کارت/دیالوگ جزئیات) - قبلاً برگردانده نمی‌شد.
        return [
            {
                "first_name": r[0],
                "last_name": r[1],
                "personnel_code": r[2],
                "score": r[3],
                "evaluation_id": r[4],
            }
            for r in result.all()
        ]

    async def get_evaluation_answers(self, site_id: int, evaluation_id: int) -> list[EvaluationAnswer]:
        """
        ⚠️ جزئیات سوال‌به‌سوال یک ارزیابی برای گزارش مدیریتی.

        ⚠️ امنیت: بررسی می‌شود که این ارزیابی واقعاً متعلق به همان سایتی
        باشد که کاربر برایش مجوز گزارش‌گیری دارد - وگرنه با دانستن یک
        evaluation_id دلخواه می‌شد جزئیات ارزیابی سایت دیگری را خواند.
        """
        owner = await self.db.execute(
            select(Evaluation.id)
            .join(EvaluationAssignment, EvaluationAssignment.id == Evaluation.assignment_id)
            .join(Employee, Employee.id == EvaluationAssignment.target_employee_id)
            .where(
                Evaluation.id == evaluation_id,
                Employee.site_id == site_id,
                Evaluation.status == EvaluationStatus.submitted,
            )
        )
        if owner.scalar_one_or_none() is None:
            raise EvaluationReportError("ارزیابی موردنظر یافت نشد")

        result = await self.db.execute(
            select(EvaluationAnswer)
            .where(EvaluationAnswer.evaluation_id == evaluation_id)
            .order_by(EvaluationAnswer.id)
        )
        # ⚠️ از همان تابع غنی‌سازی evaluation_process_service استفاده می‌شود
        # (نه یک کپی دوم) - تا برچسب گزینه‌ها و فهرست گزینه‌های ممکن در
        # گزارش مدیریتی و نمای پرسنلی دقیقاً یکسان ساخته شوند.
        from app.services.evaluation_process_service import EvaluationProcessService

        return await EvaluationProcessService(self.db)._enrich_answers_with_options(
            list(result.scalars().all())
        )

    async def get_site_period_report(self, site_id: int, period_id: int) -> dict:
        """گزارش کامل یک سایت برای یک دوره - میانگین کل + شکسته‌شده به هر واحد."""
        site = await self.db.get(Site, site_id)
        if site is None:
            raise EvaluationReportError("سایت موردنظر یافت نشد")
        period = await self.db.get(EvaluationPeriod, period_id)
        if period is None:
            raise EvaluationReportError("دوره ارزیابی موردنظر یافت نشد")

        departments_result = await self.db.execute(select(Department).where(Department.site_id == site_id))
        departments = departments_result.scalars().all()

        department_entries = []
        for department in departments:
            stats = await self._department_stats(department.id, period_id)
            if stats["count"] == 0:
                continue  # واحدهایی که هنوز هیچ ارزیابی ثبت‌نهایی‌شده‌ای ندارند، در گزارش نشان داده نمی‌شوند
            employees = await self._department_employee_scores(department.id, period_id)
            department_entries.append(
                {
                    "department_id": department.id,
                    "department_name": department.name,
                    **stats,
                    "employees": employees,
                }
            )

        overall_result = await self.db.execute(
            select(func.avg(Evaluation.total_score), func.count(Evaluation.id))
            .join(EvaluationAssignment, EvaluationAssignment.id == Evaluation.assignment_id)
            .join(Employee, Employee.id == EvaluationAssignment.target_employee_id)
            .where(
                Employee.site_id == site_id,
                EvaluationAssignment.period_id == period_id,
                Evaluation.status == EvaluationStatus.submitted,
            )
        )
        overall_average, overall_count = overall_result.one()

        return {
            "site_id": site_id,
            "site_name": site.name,
            "period_id": period_id,
            "period_title": period.title,
            "overall_average_score": float(overall_average) if overall_average is not None else None,
            "overall_count": overall_count,
            "departments": department_entries,
        }

    async def _department_employee_comparison(
        self, department_id: int, period_id_a: int, period_id_b: int
    ) -> list[dict]:
        """
        ⚠️ طبق درخواست صریح کاربر: زیر هر واحد در «مقایسه دوره‌ها»، لیست
        پرسنل با امتیاز هر دو دوره و میزان تغییر.

        پرسنلی که فقط در یکی از دو دوره ارزیابی شده هم می‌آید (امتیاز
        دوره دیگرش None می‌شود) - چون حذفشان تصویر ناقصی از واحد می‌داد.
        کلید تطبیق، کد پرسنلی است (نه نام، که ممکن است تکراری باشد).
        """
        scores_a = await self._department_employee_scores(department_id, period_id_a)
        scores_b = await self._department_employee_scores(department_id, period_id_b)

        merged: dict[str, dict] = {}
        for row in scores_a:
            merged[row["personnel_code"]] = {
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "personnel_code": row["personnel_code"],
                "period_a_score": row["score"],
                "period_a_evaluation_id": row["evaluation_id"],
                "period_b_score": None,
                "period_b_evaluation_id": None,
            }
        for row in scores_b:
            entry = merged.setdefault(
                row["personnel_code"],
                {
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "personnel_code": row["personnel_code"],
                    "period_a_score": None,
                    "period_a_evaluation_id": None,
                    "period_b_score": None,
                    "period_b_evaluation_id": None,
                },
            )
            entry["period_b_score"] = row["score"]
            entry["period_b_evaluation_id"] = row["evaluation_id"]

        return sorted(merged.values(), key=lambda e: e["last_name"])

    async def get_period_comparison(self, site_id: int, period_id_a: int, period_id_b: int) -> dict:
        """مقایسه میانگین یک سایت بین دو دوره - کل سایت + شکسته‌شده به هر واحد."""
        site = await self.db.get(Site, site_id)
        if site is None:
            raise EvaluationReportError("سایت موردنظر یافت نشد")
        period_a = await self.db.get(EvaluationPeriod, period_id_a)
        period_b = await self.db.get(EvaluationPeriod, period_id_b)
        if period_a is None or period_b is None:
            raise EvaluationReportError("یکی از دو دوره ارزیابی یافت نشد")

        async def overall_average(period_id: int) -> float | None:
            result = await self.db.execute(
                select(func.avg(Evaluation.total_score))
                .join(EvaluationAssignment, EvaluationAssignment.id == Evaluation.assignment_id)
                .join(Employee, Employee.id == EvaluationAssignment.target_employee_id)
                .where(
                    Employee.site_id == site_id,
                    EvaluationAssignment.period_id == period_id,
                    Evaluation.status == EvaluationStatus.submitted,
                )
            )
            value = result.scalar_one()
            return float(value) if value is not None else None

        avg_a = await overall_average(period_id_a)
        avg_b = await overall_average(period_id_b)

        departments_result = await self.db.execute(select(Department).where(Department.site_id == site_id))
        departments = departments_result.scalars().all()

        department_entries = []
        for department in departments:
            stats_a = await self._department_stats(department.id, period_id_a)
            stats_b = await self._department_stats(department.id, period_id_b)
            if stats_a["count"] == 0 and stats_b["count"] == 0:
                continue
            department_entries.append(
                {
                    "department_id": department.id,
                    "department_name": department.name,
                    "period_a_average": stats_a["average_score"],
                    "period_a_count": stats_a["count"],
                    "period_b_average": stats_b["average_score"],
                    "period_b_count": stats_b["count"],
                    "employees": await self._department_employee_comparison(
                        department.id, period_id_a, period_id_b
                    ),
                }
            )

        return {
            "site_id": site_id,
            "site_name": site.name,
            "period_a": {"id": period_id_a, "title": period_a.title, "average_score": avg_a},
            "period_b": {"id": period_id_b, "title": period_b.title, "average_score": avg_b},
            "departments": department_entries,
        }
