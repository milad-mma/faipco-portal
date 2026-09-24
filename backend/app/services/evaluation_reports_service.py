"""
سرویس «گزارش‌های مدیریتی ارزیابی عملکرد»: آمار واحد/سایت برای یک دوره، مقایسه دو دوره،
روند فردی یک پرسنل، جزئیات سوال‌به‌سوال یک ارزیابی و ریز پاسخ‌های یک دوره برای Excel.
برخلاف evaluation_process_service.py (دیدگاه فردی کاربر)، این سرویس دیدگاه تجمیعی/مدیریتی دارد.

همه کوئری‌ها فقط Evaluationهای status=submitted را حساب می‌کنند؛ پیش‌نویس‌ها در آمار نمی‌آیند.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Department, Employee
from app.models.evaluation_content import EvaluationPeriod
from app.models.evaluation_process import Evaluation, EvaluationAnswer, EvaluationAssignment, EvaluationStatus
from app.models.site import Site


class EvaluationReportError(Exception):
    """خطای قابل نمایش به کاربر در گزارش‌ها (مثلاً سایت/دوره/ارزیابی یافت نشد)."""
    pass


def _format_answer_value(answer: dict) -> str:
    """ورودی: پاسخ غنی‌شده (dict). متن نمایشی پاسخ را با همان منطق UI برمی‌گرداند (متن، عدد، تاریخ یا برچسب گزینه‌ها)."""
    if answer.get("text_value"):
        return answer["text_value"]
    if answer.get("number_value") is not None:
        return str(answer["number_value"])
    if answer.get("date_value"):
        return str(answer["date_value"])
    if answer.get("selected_option_labels"):
        return "، ".join(answer["selected_option_labels"])
    return "—"


class EvaluationReportsService:
    """سرویس گزارش‌های تجمیعی ارزیابی برای مدیران."""

    def __init__(self, db: AsyncSession):
        """ورودی: نشست async دیتابیس."""
        self.db = db

    async def _department_stats(self, department_id: int, period_id: int) -> dict:
        """میانگین، تعداد، کمینه و بیشینه امتیاز ارزیابی‌های ثبت‌شده پرسنل یک واحد در یک دوره (dict)."""
        # تجمیع روی ارزیابی‌های submitted که هدفشان پرسنل این واحد است
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
        """فهرست امتیاز پرسنل یک واحد در یک دوره (بیشترین اول)، همراه evaluation_id برای Drill-down."""
        # امتیاز هر ارزیابی submitted پرسنل واحد، مرتب بر اساس امتیاز نزولی
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
        # evaluation_id برای نمایش جزئیات سوال‌به‌سوال در گزارش مدیریتی لازم است
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
        جزئیات سوال‌به‌سوال یک ارزیابی ثبت‌شده برای گزارش مدیریتی (پاسخ‌های غنی‌شده با گزینه‌ها).
        ابتدا بررسی می‌شود ارزیابی متعلق به پرسنلِ همین سایت باشد؛ در غیر این صورت EvaluationReportError.
        """
        # بررسی تعلق ارزیابی به سایت (تا با evaluation_id دلخواه نتوان سایت دیگری را خواند)
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
        # غنی‌سازی با تابع مشترک evaluation_process_service تا برچسب/فهرست گزینه‌ها با نمای پرسنلی یکسان باشد
        from app.services.evaluation_process_service import EvaluationProcessService

        return await EvaluationProcessService(self.db)._enrich_answers_with_options(
            list(result.scalars().all())
        )

    async def get_employee_trend(self, site_id: int, personnel_code: str) -> dict:
        """
        روند فردی: امتیاز یک پرسنل (با کد پرسنلی) در همه دوره‌ها به ترتیب زمان ثبت، همراه میانگین،
        بهترین و بدترین امتیاز. فقط پرسنل همین سایت؛ در غیر این صورت EvaluationReportError.
        """
        # جست‌وجوی پرسنل فقط در همین سایت
        employee_result = await self.db.execute(
            select(Employee).where(Employee.site_id == site_id, Employee.personnel_code == personnel_code)
        )
        employee = employee_result.scalar_one_or_none()
        if employee is None:
            raise EvaluationReportError("پرسنل موردنظر در این سایت یافت نشد")

        # همه ارزیابی‌های submitted این پرسنل، به ترتیب زمان ثبت
        result = await self.db.execute(
            select(
                EvaluationPeriod.id,
                EvaluationPeriod.title,
                Evaluation.total_score,
                Evaluation.id,
                Evaluation.submitted_at,
            )
            .join(EvaluationAssignment, EvaluationAssignment.period_id == EvaluationPeriod.id)
            .join(Evaluation, Evaluation.assignment_id == EvaluationAssignment.id)
            .where(
                EvaluationAssignment.target_employee_id == employee.id,
                Evaluation.status == EvaluationStatus.submitted,
            )
            .order_by(Evaluation.submitted_at)
        )
        points = [
            {
                "period_id": r[0],
                "period_title": r[1],
                "score": float(r[2]) if r[2] is not None else None,
                "evaluation_id": r[3],
                "submitted_at": r[4],
            }
            for r in result.all()
        ]
        scores = [p["score"] for p in points if p["score"] is not None]
        return {
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "personnel_code": employee.personnel_code,
            "points": points,
            "average_score": sum(scores) / len(scores) if scores else None,
            "best_score": max(scores) if scores else None,
            "worst_score": min(scores) if scores else None,
        }

    async def get_period_answers(self, site_id: int, period_id: int) -> list[dict]:
        """
        ریز پاسخ‌های همه ارزیابی‌های ثبت‌شده یک دوره برای پرسنل یک سایت، برای شیت «سوال و پاسخ» Excel.
        خروجی: لیست dict (واحد، نام، کد، امتیاز کل، سوال، پاسخ، گزینه‌ها، امتیاز سوال، نظر).
        برچسب گزینه‌ها از همان تابع غنی‌سازی مشترک می‌آید تا با UI یکسان باشد.
        """
        from app.models.evaluation_process import EvaluationAnswer
        from app.services.evaluation_process_service import EvaluationProcessService

        # ارزیابی‌های submitted دوره برای پرسنل سایت، همراه نام واحد (مرتب بر اساس واحد و نام خانوادگی)
        result = await self.db.execute(
            select(
                Employee.first_name,
                Employee.last_name,
                Employee.personnel_code,
                Department.name,
                Evaluation.id,
                Evaluation.total_score,
            )
            .join(EvaluationAssignment, EvaluationAssignment.target_employee_id == Employee.id)
            .join(Evaluation, Evaluation.assignment_id == EvaluationAssignment.id)
            .outerjoin(Department, Department.id == Employee.department_id)
            .where(
                Employee.site_id == site_id,
                EvaluationAssignment.period_id == period_id,
                Evaluation.status == EvaluationStatus.submitted,
            )
            .order_by(Department.name, Employee.last_name)
        )
        rows = result.all()
        if not rows:
            return []

        # همه پاسخ‌های این ارزیابی‌ها در یک کوئری، سپس غنی‌سازی با گزینه‌ها
        evaluation_ids = [r[4] for r in rows]
        answers_result = await self.db.execute(
            select(EvaluationAnswer)
            .where(EvaluationAnswer.evaluation_id.in_(evaluation_ids))
            .order_by(EvaluationAnswer.evaluation_id, EvaluationAnswer.id)
        )
        all_answers = list(answers_result.scalars().all())
        enriched = await EvaluationProcessService(self.db)._enrich_answers_with_options(all_answers)

        # گروه‌بندی پاسخ‌های غنی‌شده بر اساس evaluation_id (ترتیب enriched با all_answers یکی است)
        by_evaluation: dict[int, list] = {}
        for answer, raw in zip(enriched, all_answers):
            by_evaluation.setdefault(raw.evaluation_id, []).append(answer)

        # یک سطر خروجی برای هر پاسخ هر ارزیابی
        out = []
        for first_name, last_name, personnel_code, dept_name, evaluation_id, total_score in rows:
            for answer in by_evaluation.get(evaluation_id, []):
                out.append(
                    {
                        "department": dept_name,
                        "first_name": first_name,
                        "last_name": last_name,
                        "personnel_code": personnel_code,
                        "total_score": float(total_score) if total_score is not None else None,
                        "question": answer["question_text_snapshot"],
                        "answer": _format_answer_value(answer),
                        "options": "، ".join(
                            f"{o['label']} ({o['score']})" for o in answer["available_options"]
                        ),
                        "score": answer["score"],
                        "comment": answer["comment"],
                    }
                )
        return out

    async def get_site_period_report(self, site_id: int, period_id: int) -> dict:
        """
        گزارش کامل یک سایت برای یک دوره: میانگین و تعداد کل، و آمار + امتیاز پرسنل هر واحد.
        اگر سایت/دوره نباشد EvaluationReportError.
        """
        site = await self.db.get(Site, site_id)
        if site is None:
            raise EvaluationReportError("سایت موردنظر یافت نشد")
        period = await self.db.get(EvaluationPeriod, period_id)
        if period is None:
            raise EvaluationReportError("دوره ارزیابی موردنظر یافت نشد")

        departments_result = await self.db.execute(select(Department).where(Department.site_id == site_id))
        departments = departments_result.scalars().all()

        # آمار و امتیاز پرسنل برای هر واحد سایت
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

        # میانگین و تعداد کل ارزیابی‌های submitted سایت در این دوره
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
        فهرست پرسنل یک واحد با امتیاز هر دو دوره (مرتب بر اساس نام خانوادگی).
        پرسنلی که فقط در یکی از دوره‌ها ارزیابی شده هم می‌آید (امتیاز دیگر None).
        کلید تطبیق کد پرسنلی است، نه نام.
        """
        scores_a = await self._department_employee_scores(department_id, period_id_a)
        scores_b = await self._department_employee_scores(department_id, period_id_b)

        # ادغام دو فهرست بر اساس کد پرسنلی
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
            )  # اگر در دوره اول نبود، رکورد خالی ساخته می‌شود
            entry["period_b_score"] = row["score"]
            entry["period_b_evaluation_id"] = row["evaluation_id"]

        return sorted(merged.values(), key=lambda e: e["last_name"])

    async def get_period_comparison(self, site_id: int, period_id_a: int, period_id_b: int) -> dict:
        """
        مقایسه یک سایت بین دو دوره: میانگین کل هر دوره و برای هر واحد میانگین/تعداد دو دوره و مقایسه پرسنل.
        اگر سایت یا یکی از دوره‌ها نباشد EvaluationReportError.
        """
        site = await self.db.get(Site, site_id)
        if site is None:
            raise EvaluationReportError("سایت موردنظر یافت نشد")
        period_a = await self.db.get(EvaluationPeriod, period_id_a)
        period_b = await self.db.get(EvaluationPeriod, period_id_b)
        if period_a is None or period_b is None:
            raise EvaluationReportError("یکی از دو دوره ارزیابی یافت نشد")

        async def overall_average(period_id: int) -> float | None:
            """میانگین امتیاز ارزیابی‌های submitted پرسنل سایت در یک دوره (یا None)."""
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

        # آمار هر واحد در دو دوره؛ واحدی که در هیچ‌کدام ارزیابی ندارد حذف می‌شود
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
