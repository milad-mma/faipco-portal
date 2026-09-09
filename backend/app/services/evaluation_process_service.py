"""
سرویس «جریان انجام ارزیابی» - شروع، ذخیره پیش‌نویس، ثبت نهایی، و
خلاصه‌سازی برای کارت داشبورد.

⚠️ امنیتی: هر عملیات روی یک Evaluation، ابتدا تأیید می‌کند که کاربر
جاری واقعاً ارزیابِ همان Assignment است - هرگز فقط به این‌که یک
evaluation_id معتبر داده شده اعتماد نمی‌شود.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.evaluation_rules import calculate_option_based_question_score, calculate_weighted_average
from app.core.persian_date import get_current_jalali_date, jalali_year_range_utc
from app.models.employee import Department, Employee
from app.models.evaluation import EvaluationDepartmentSupervisor, EvaluationShiftLead
from app.models.evaluation_content import (
    EvaluationCategory,
    EvaluationForm,
    EvaluationPeriod,
    EvaluationPeriodStatus,
    EvaluationQuestion,
)
from app.models.evaluation_process import (
    Evaluation,
    EvaluationAnswer,
    EvaluationAssignment,
    EvaluationAssignmentStatus,
    EvaluationStatus,
)
from app.models.site import Site

_OPTION_BASED_TYPES = {"single_choice", "multiple_choice", "rating", "yes_no"}


class EvaluationProcessError(Exception):
    pass


class EvaluationProcessService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_owned_assignment(self, assignment_id: int, evaluator_employee_id: int) -> EvaluationAssignment:
        assignment = await self.db.get(EvaluationAssignment, assignment_id)
        if assignment is None:
            raise EvaluationProcessError("این ارزیابی یافت نشد")
        if assignment.evaluator_employee_id != evaluator_employee_id:
            raise EvaluationProcessError("شما مجاز به انجام این ارزیابی نیستید")
        return assignment

    async def _is_supervisor_of_evaluator(self, original_evaluator_employee_id: int, requesting_employee_id: int) -> bool:
        """
        طبق درخواست صریح: سرپرست یک واحد باید دسترسی ویرایش ارزیابی‌های
        انجام‌شده توسط سرشیفت‌های همان واحد را هم داشته باشد - یعنی اگر
        ارزیابِ اصلی، سرشیفتِ یک واحدی است که requesting_employee_id
        سرپرست همان واحد است، دسترسی مجاز است.
        """
        shift_lead_result = await self.db.execute(
            select(EvaluationShiftLead.department_id).where(
                EvaluationShiftLead.employee_id == original_evaluator_employee_id
            )
        )
        shift_lead_department_ids = [row[0] for row in shift_lead_result.all()]
        if not shift_lead_department_ids:
            return False
        supervisor_result = await self.db.execute(
            select(EvaluationDepartmentSupervisor.id).where(
                EvaluationDepartmentSupervisor.employee_id == requesting_employee_id,
                EvaluationDepartmentSupervisor.department_id.in_(shift_lead_department_ids),
            )
        )
        return supervisor_result.scalar_one_or_none() is not None

    async def _get_owned_evaluation(self, evaluation_id: int, evaluator_employee_id: int) -> Evaluation:
        result = await self.db.execute(
            select(Evaluation)
            .options(selectinload(Evaluation.assignment), selectinload(Evaluation.answers))
            .where(Evaluation.id == evaluation_id)
        )
        evaluation = result.scalar_one_or_none()
        if evaluation is None:
            raise EvaluationProcessError("این ارزیابی یافت نشد")
        if evaluation.assignment.evaluator_employee_id != evaluator_employee_id and not (
            await self._is_supervisor_of_evaluator(evaluation.assignment.evaluator_employee_id, evaluator_employee_id)
        ):
            raise EvaluationProcessError("شما مجاز به انجام این ارزیابی نیستید")
        return evaluation

    async def get_evaluation(self, evaluation_id: int, requesting_employee_id: int) -> Evaluation:
        """
        دریافت مستقیم یک Evaluation با ID خودش - برخلاف start_evaluation
        (که با assignment_id کار می‌کند و فقط برای ارزیابِ اصلی مجاز
        است)، این متد از همان بررسی دسترسی گسترده‌تر _get_owned_evaluation
        استفاده می‌کند - یعنی هم ارزیابِ اصلی، هم سرپرستی که این ارزیاب
        سرشیفتِ واحد اوست، می‌توانند از این طریق به یک Evaluation از‌قبل
        باز‌شده (draft) برسند - برای ادامه/ویرایش، بدون نیاز به عبور از
        بررسی مالکیت Assignment.
        """
        return await self._get_owned_evaluation(evaluation_id, requesting_employee_id)

    async def start_evaluation(self, assignment_id: int, evaluator_employee_id: int) -> Evaluation:
        """
        اگر Evaluation ای برای این Assignment از قبل وجود دارد (ادامه یک
        Draft قبلی)، همان برگردانده می‌شود - وگرنه یک Evaluation جدید با
        Historical Snapshot کامل (از وضعیت *همین لحظه* پرسنل/سایت/واحد)
        ساخته می‌شود.
        """
        assignment = await self._get_owned_assignment(assignment_id, evaluator_employee_id)

        existing_result = await self.db.execute(
            select(Evaluation)
            .options(selectinload(Evaluation.answers), selectinload(Evaluation.assignment))
            .where(Evaluation.assignment_id == assignment_id)
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            return existing

        evaluator = await self.db.get(Employee, assignment.evaluator_employee_id)
        target = await self.db.get(Employee, assignment.target_employee_id)
        form = await self.db.get(EvaluationForm, assignment.form_id)
        period = await self.db.get(EvaluationPeriod, assignment.period_id)
        if evaluator is None or target is None or form is None or period is None:
            raise EvaluationProcessError("اطلاعات ارزیاب/ارزیابی‌شونده/فرم/دوره یافت نشد")

        site = await self.db.get(Site, target.site_id)
        department_name = None
        if target.department_id is not None:
            department = await self.db.get(Department, target.department_id)
            department_name = department.name if department else None

        evaluation = Evaluation(
            assignment_id=assignment_id,
            status=EvaluationStatus.draft,
            evaluator_name_snapshot=f"{evaluator.first_name} {evaluator.last_name}",
            evaluator_personnel_code_snapshot=evaluator.personnel_code,
            target_name_snapshot=f"{target.first_name} {target.last_name}",
            target_personnel_code_snapshot=target.personnel_code,
            site_name_snapshot=site.name if site else "",
            department_name_snapshot=department_name,
            form_title_snapshot=form.title,
            period_title_snapshot=period.title,
        )
        self.db.add(evaluation)
        await self.db.flush()  # برای پرشدن evaluation.id بدون Expire شدن (برخلاف commit)
        evaluation_id = evaluation.id
        await self.db.commit()

        # ⚠️ بعد از commit()، هر Object در Session (از‌جمله همان assignment
        # که بالاتر گرفتیم) Expire می‌شود - دسترسی مستقیم به آن یا حتی به
        # یک رابطه دستی‌تنظیم‌شده روی evaluation، دوباره همان خطای
        # MissingGreenlet را می‌دهد. امن‌ترین راه، Query مجدد با
        # selectinload صریح است - دقیقاً همان الگویی که در بقیه این ماژول
        # (evaluation_structure_service.py) استفاده شده.
        result = await self.db.execute(
            select(Evaluation)
            .options(selectinload(Evaluation.answers), selectinload(Evaluation.assignment))
            .where(Evaluation.id == evaluation_id)
        )
        return result.scalar_one()

    async def save_answers(self, evaluation_id: int, evaluator_employee_id: int, answers: list[dict]) -> Evaluation:
        evaluation = await self._get_owned_evaluation(evaluation_id, evaluator_employee_id)
        if evaluation.status != EvaluationStatus.draft:
            raise EvaluationProcessError("این ارزیابی قبلاً ثبت نهایی شده و دیگر قابل‌ویرایش نیست")

        for answer_data in answers:
            question = await self.db.get(EvaluationQuestion, answer_data["question_id"])
            if question is None:
                continue  # سوال حذف شده - نادیده گرفته می‌شود

            # ⚠️ طبق تصمیم صریح: برای سوالات «عدد»، عدد واردشده مستقیماً
            # امتیاز آن سوال است (از حداکثر weight) - پس باید در همان
            # محدوده [۰, weight] باشد؛ خارج از این محدوده منطقاً بی‌معنی
            # است (نمی‌شود بیشتر از حداکثر امتیاز ممکن آن سوال امتیاز داد).
            if question.question_type.value == "number" and answer_data.get("number_value") is not None:
                number_value = answer_data["number_value"]
                weight = float(question.weight)
                if number_value < 0 or number_value > weight:
                    raise EvaluationProcessError(
                        f"پاسخ سوال «{question.text}» باید بین ۰ تا {weight:g} باشد (وزن این سوال {weight:g} است)"
                    )

            existing_result = await self.db.execute(
                select(EvaluationAnswer).where(
                    EvaluationAnswer.evaluation_id == evaluation_id,
                    EvaluationAnswer.question_id == answer_data["question_id"],
                )
            )
            existing_answer = existing_result.scalar_one_or_none()

            fields = {
                "question_text_snapshot": question.text,
                "question_type_snapshot": question.question_type.value,
                "selected_option_ids": answer_data.get("selected_option_ids"),
                "text_value": answer_data.get("text_value"),
                "number_value": answer_data.get("number_value"),
                "date_value": answer_data.get("date_value"),
                "comment": answer_data.get("comment"),
            }
            if existing_answer is not None:
                for key, value in fields.items():
                    setattr(existing_answer, key, value)
            else:
                self.db.add(EvaluationAnswer(evaluation_id=evaluation_id, question_id=question.id, **fields))

        await self.db.commit()
        return await self._get_owned_evaluation(evaluation_id, evaluator_employee_id)

    async def submit_evaluation(self, evaluation_id: int, evaluator_employee_id: int) -> Evaluation:
        evaluation = await self._get_owned_evaluation(evaluation_id, evaluator_employee_id)
        if evaluation.status != EvaluationStatus.draft:
            raise EvaluationProcessError("این ارزیابی قبلاً ثبت نهایی شده است")

        form_result = await self.db.execute(
            select(EvaluationForm)
            .options(
                selectinload(EvaluationForm.categories)
                .selectinload(EvaluationCategory.questions)
                .selectinload(EvaluationQuestion.options)
            )
            .where(EvaluationForm.id == evaluation.assignment.form_id)
        )
        form = form_result.scalar_one()

        answers_by_question = {a.question_id: a for a in evaluation.answers}

        missing_required = []
        for category in form.categories:
            if not category.is_active:
                continue
            for question in category.questions:
                if question.is_active and question.required and question.id not in answers_by_question:
                    missing_required.append(question.text)
        if missing_required:
            raise EvaluationProcessError(
                "پاسخ به سوالات اجباری زیر الزامی است: "
                + "، ".join(missing_required[:5])
                + ("..." if len(missing_required) > 5 else "")
            )

        category_scores = []
        for category in form.categories:
            if not category.is_active:
                continue
            question_scores = []
            for question in category.questions:
                if not question.is_active:
                    continue
                answer = answers_by_question.get(question.id)
                score = self._score_single_answer(question, answer)
                if answer is not None:
                    answer.score = score
                question_scores.append({"weight": float(question.weight), "score": score})
            if question_scores:
                category_scores.append(
                    {"weight": float(category.weight), "score": calculate_weighted_average(question_scores)}
                )

        total_score = calculate_weighted_average(category_scores) if category_scores else 0.0

        evaluation.status = EvaluationStatus.submitted
        evaluation.total_score = total_score
        evaluation.submitted_at = datetime.now(timezone.utc)
        evaluation.assignment.status = EvaluationAssignmentStatus.completed

        await self.db.commit()
        return await self._get_owned_evaluation(evaluation_id, evaluator_employee_id)

    def _score_single_answer(self, question: EvaluationQuestion, answer: EvaluationAnswer | None) -> float:
        """
        ⚠️ برای انواع متن/تاریخ (که امتیازدهی مستقیم ندارند)، فقط «پاسخ
        داده شده یا نه» سنجیده می‌شود (۱۰۰ یا ۰).

        ⚠️ نوع «عدد» طبق تصمیم صریح: عدد واردشده مستقیماً معادل همان
        تعداد امتیاز (از حداکثر امتیازِ همان سوال، که با weight برابر
        است) محسوب می‌شود - نه «پاسخ داده شده یا نه». مثلاً برای سوالی
        با weight=20، عدد ۱۲ یعنی «۱۲ امتیاز از ۲۰» - که در مقیاس ۰ تا
        ۱۰۰ (برای استفاده در calculate_weighted_average که بر اساس
        weight/100 ضرب می‌کند) معادل (۱۲/۲۰)×۱۰۰=۶۰ است.
        """
        if question.question_type.value in _OPTION_BASED_TYPES:
            if answer is None or not answer.selected_option_ids:
                return 0.0
            option_scores = [float(o.score) for o in question.options if o.id in answer.selected_option_ids]
            return calculate_option_based_question_score(option_scores)

        if question.question_type.value == "number":
            weight = float(question.weight)
            if answer is None or answer.number_value is None or weight <= 0:
                return 0.0
            # ⚠️ Clamp دفاعی - محدوده واقعی (۰ تا weight) باید هنگام
            # ذخیره پاسخ (save_answers) رد شود؛ این فقط یک لایه ایمنی
            # اضافه است تا حتی در بدترین حالت هم امتیاز نهایی از دامنه
            # منطقی خارج نشود.
            clamped_value = min(weight, max(0.0, float(answer.number_value)))
            return (clamped_value / weight) * 100

        if answer is None:
            return 0.0
        has_value = answer.text_value or answer.date_value is not None
        return 100.0 if has_value else 0.0

    # ---------- ویرایش یک‌بارمصرفِ ارزیابیِ ثبت‌نهایی‌شده ----------

    async def reopen_for_edit(self, evaluation_id: int, evaluator_employee_id: int) -> Evaluation:
        """
        طبق درخواست صریح: ارزیاب فقط یک‌بار می‌تواند یک ارزیابی
        ثبت‌نهایی‌شده را - تا وقتی دوره‌اش هنوز بسته/بایگانی نشده - دوباره
        باز و ویرایش کند. بعد از این یک‌بار (was_edited=True)، دیگر
        امکان بازکردن دوباره وجود ندارد؛ ارزیابی به status=draft
        برمی‌گردد (پاسخ‌های قبلی به‌عنوان پیش‌فرض همچنان موجودند - چون
        هرگز حذف نشده بودند)، submit مجدد دوباره امتیاز را از نو محاسبه
        می‌کند.
        """
        evaluation = await self._get_owned_evaluation(evaluation_id, evaluator_employee_id)
        if evaluation.status != EvaluationStatus.submitted:
            raise EvaluationProcessError("فقط ارزیابی‌های ثبت‌نهایی‌شده قابل بازکردن مجدد هستند")
        if evaluation.was_edited:
            raise EvaluationProcessError("این ارزیابی قبلاً یک‌بار ویرایش شده - امکان ویرایش دوباره وجود ندارد")

        period = await self.db.get(EvaluationPeriod, evaluation.assignment.period_id)
        if period is None or period.status in (EvaluationPeriodStatus.closed, EvaluationPeriodStatus.archived):
            raise EvaluationProcessError("مهلت این دوره ارزیابی به پایان رسیده - دیگر امکان ویرایش وجود ندارد")

        evaluation.status = EvaluationStatus.draft
        evaluation.was_edited = True
        await self.db.commit()
        return await self._get_owned_evaluation(evaluation_id, evaluator_employee_id)

    # ---------- میانگین یک‌سال اخیر (شمسی) ----------

    async def get_yearly_average(self, employee_id: int, jalali_year: int | None = None) -> dict:
        if jalali_year is None:
            jalali_year, _, _ = get_current_jalali_date()
        start_utc, end_utc = jalali_year_range_utc(jalali_year)

        result = await self.db.execute(
            select(func.avg(Evaluation.total_score), func.count(Evaluation.id))
            .join(EvaluationAssignment, EvaluationAssignment.id == Evaluation.assignment_id)
            .where(
                EvaluationAssignment.target_employee_id == employee_id,
                Evaluation.status == EvaluationStatus.submitted,
                Evaluation.submitted_at >= start_utc,
                Evaluation.submitted_at < end_utc,
            )
        )
        average, count = result.one()
        return {"jalali_year": jalali_year, "average_score": float(average) if average is not None else None, "count": count}

    # ---------- فهرست‌ها ----------

    async def get_shift_lead_evaluations(self, supervisor_employee_id: int) -> list[dict]:
        """
        فهرست ارزیابی‌های ثبت‌نهایی‌شده‌ای که توسط سرشیفت‌های واحد(های)ی
        که این پرسنل سرپرست آن‌هاست، انجام شده - تا سرپرست بتواند در
        صورت نیاز (طبق درخواست صریح) آن‌ها را دوباره باز و ویرایش کند.
        """
        supervised_department_result = await self.db.execute(
            select(EvaluationDepartmentSupervisor.department_id).where(
                EvaluationDepartmentSupervisor.employee_id == supervisor_employee_id
            )
        )
        supervised_department_ids = [row[0] for row in supervised_department_result.all()]
        if not supervised_department_ids:
            return []

        shift_lead_result = await self.db.execute(
            select(EvaluationShiftLead.id, EvaluationShiftLead.employee_id).where(
                EvaluationShiftLead.department_id.in_(supervised_department_ids)
            )
        )
        shift_lead_rows = shift_lead_result.all()
        shift_lead_employee_ids = [row[1] for row in shift_lead_rows]
        if not shift_lead_employee_ids:
            return []

        evaluations_result = await self.db.execute(
            select(Evaluation)
            .options(selectinload(Evaluation.assignment))
            .join(EvaluationAssignment, EvaluationAssignment.id == Evaluation.assignment_id)
            .where(
                EvaluationAssignment.evaluator_employee_id.in_(shift_lead_employee_ids),
                Evaluation.status == EvaluationStatus.submitted,
            )
            .order_by(Evaluation.submitted_at.desc())
        )
        evaluations = evaluations_result.scalars().all()

        return [
            {
                "evaluation_id": evaluation.id,
                "assignment_id": evaluation.assignment_id,
                "shift_lead_name": evaluation.evaluator_name_snapshot,
                "target_name": evaluation.target_name_snapshot,
                "period_title": evaluation.period_title_snapshot,
                "form_title": evaluation.form_title_snapshot,
                "total_score": evaluation.total_score,
                "was_edited": evaluation.was_edited,
                "submitted_at": evaluation.submitted_at,
            }
            for evaluation in evaluations
        ]

    async def get_my_evaluations(self, evaluator_employee_id: int) -> list[dict]:
        """ارزیابی‌هایی که این پرسنل باید انجام دهد (Assignment های او) - با وضعیت فعلی هرکدام."""
        assignments_result = await self.db.execute(
            select(EvaluationAssignment)
            .options(
                selectinload(EvaluationAssignment.target_employee),
                selectinload(EvaluationAssignment.period),
                selectinload(EvaluationAssignment.form),
            )
            .where(EvaluationAssignment.evaluator_employee_id == evaluator_employee_id)
        )
        assignments = assignments_result.scalars().all()

        evaluations_result = await self.db.execute(
            select(
                Evaluation.assignment_id, Evaluation.id, Evaluation.status, Evaluation.was_edited, Evaluation.total_score
            ).where(Evaluation.assignment_id.in_([a.id for a in assignments]))
        )
        evaluation_by_assignment = {
            row[0]: {"evaluation_id": row[1], "status": row[2].value, "was_edited": row[3], "total_score": row[4]}
            for row in evaluations_result.all()
        }

        items = []
        for assignment in assignments:
            evaluation_info = evaluation_by_assignment.get(assignment.id)
            items.append(
                {
                    "assignment_id": assignment.id,
                    "target": assignment.target_employee,
                    "period_title": assignment.period.title,
                    "form_title": assignment.form.title,
                    "evaluation_id": evaluation_info["evaluation_id"] if evaluation_info else None,
                    "status": evaluation_info["status"] if evaluation_info else "not_started",
                    "was_edited": evaluation_info["was_edited"] if evaluation_info else False,
                    "total_score": evaluation_info["total_score"] if evaluation_info else None,
                }
            )
        return items

    async def get_my_results(self, target_employee_id: int) -> list[Evaluation]:
        """ارزیابی‌های ثبت‌نهایی‌شده‌ای که این پرسنل هدف آن‌ها بوده - نتایج خودش."""
        result = await self.db.execute(
            select(Evaluation)
            .join(EvaluationAssignment, EvaluationAssignment.id == Evaluation.assignment_id)
            .where(
                EvaluationAssignment.target_employee_id == target_employee_id,
                Evaluation.status == EvaluationStatus.submitted,
            )
            .order_by(Evaluation.submitted_at.desc())
        )
        return list(result.scalars().all())

    async def get_dashboard_summary(self, employee_id: int) -> dict:
        """
        خلاصه‌ی مخصوص کارت داشبورد - یک درخواست، همه‌چیز: امتیاز
        (میانگین/آخرین)، و تعداد ارزیابی‌های در انتظار انجام (اگر خودش
        هم نقش ارزیاب دارد).
        """
        results = await self.get_my_results(employee_id)
        average_score = sum(r.total_score for r in results) / len(results) if results else None
        latest_score = results[0].total_score if results else None

        pending_result = await self.db.execute(
            select(EvaluationAssignment.id).where(
                EvaluationAssignment.evaluator_employee_id == employee_id,
                EvaluationAssignment.status == EvaluationAssignmentStatus.pending,
            )
        )
        pending_count = len(pending_result.all())

        return {
            "average_score": average_score,
            "latest_score": latest_score,
            "results_count": len(results),
            "pending_to_evaluate_count": pending_count,
        }
