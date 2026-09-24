"""
سرویس «جریان انجام ارزیابی»: شروع ارزیابی (با Snapshot)، ذخیره پیش‌نویس پاسخ‌ها، ثبت نهایی و
محاسبه امتیاز، بازگشایی یک‌باره برای ویرایش، یادآوری و اعلان Push، فهرست‌ها و نتایج پرسنل،
میانگین سالانه و خلاصه کارت داشبورد.

هر عملیات روی یک Evaluation ابتدا بررسی می‌کند کاربر جاری ارزیابِ همان Assignment (یا سرپرستِ
سرشیفتِ ارزیاب) باشد؛ داشتن یک evaluation_id معتبر به‌تنهایی کافی نیست.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.evaluation_rules import calculate_option_based_question_score, calculate_weighted_average
from app.core.persian_date import get_current_jalali_date, jalali_year_range_utc
from app.models.employee import Department, Employee
from app.models.evaluation import EvaluationDepartmentSupervisor, EvaluationShiftLead
from app.models.user import User
from app.models.evaluation_content import (
    EvaluationCategory,
    EvaluationForm,
    EvaluationPeriod,
    EvaluationPeriodStatus,
    EvaluationQuestion,
    EvaluationQuestionOption,
)
from app.models.evaluation_process import (
    Evaluation,
    EvaluationAnswer,
    EvaluationAssignment,
    EvaluationAssignmentStatus,
    EvaluationStatus,
)
from app.models.site import Site
from app.services.push_service import PushService

logger = logging.getLogger(__name__)

# انواع سوالی که پاسخشان انتخاب گزینه است و امتیاز از گزینه‌ها محاسبه می‌شود
_OPTION_BASED_TYPES = {"single_choice", "multiple_choice", "rating", "yes_no"}


class EvaluationProcessError(Exception):
    """خطای قابل نمایش به کاربر در جریان انجام ارزیابی (دسترسی، اعتبارسنجی، وضعیت)."""
    pass


class EvaluationProcessService:
    """سرویس انجام ارزیابی و نمایش نتایج برای پرسنل."""

    def __init__(self, db: AsyncSession):
        """ورودی: نشست async دیتابیس."""
        self.db = db

    async def _ensure_period_enabled(self, period_id: int) -> None:
        """اگر دوره وجود نداشته باشد یا ادمین آن را غیرفعال کرده باشد EvaluationProcessError می‌دهد."""
        period = await self.db.get(EvaluationPeriod, period_id)
        if period is None or period.is_disabled:
            raise EvaluationProcessError("این دوره ارزیابی غیرفعال شده و دیگر در دسترس نیست")

    async def _get_owned_assignment(self, assignment_id: int, evaluator_employee_id: int) -> EvaluationAssignment:
        """انتساب را برمی‌گرداند به شرط وجود، فعال بودن دوره و این‌که ارزیابِ آن همین پرسنل باشد؛ وگرنه EvaluationProcessError."""
        assignment = await self.db.get(EvaluationAssignment, assignment_id)
        if assignment is None:
            raise EvaluationProcessError("این ارزیابی یافت نشد")
        await self._ensure_period_enabled(assignment.period_id)
        if assignment.evaluator_employee_id != evaluator_employee_id:
            raise EvaluationProcessError("شما مجاز به انجام این ارزیابی نیستید")
        return assignment

    async def _is_supervisor_of_evaluator(self, original_evaluator_employee_id: int, requesting_employee_id: int) -> bool:
        """
        True اگر ارزیاب اصلی سرشیفت واحدی باشد که requesting_employee_id سرپرست ارزیابی آن است؛
        سرپرست به ارزیابی‌های سرشیفت‌های واحدش دسترسی مشاهده/ویرایش دارد.
        """
        shift_lead_result = await self.db.execute(
            select(EvaluationShiftLead.department_id).where(
                EvaluationShiftLead.employee_id == original_evaluator_employee_id
            )
        )
        shift_lead_department_ids = [row[0] for row in shift_lead_result.all()]
        if not shift_lead_department_ids:  # ارزیاب اصلی سرشیفت هیچ واحدی نیست
            return False
        # آیا درخواست‌کننده سرپرست یکی از همان واحدهاست
        supervisor_result = await self.db.execute(
            select(EvaluationDepartmentSupervisor.id).where(
                EvaluationDepartmentSupervisor.employee_id == requesting_employee_id,
                EvaluationDepartmentSupervisor.department_id.in_(shift_lead_department_ids),
            )
        )
        return supervisor_result.scalar_one_or_none() is not None

    async def _get_owned_evaluation(self, evaluation_id: int, evaluator_employee_id: int) -> Evaluation:
        """
        ارزیابی را همراه assignment و answers برمی‌گرداند، به شرط فعال بودن دوره و این‌که کاربر ارزیاب
        اصلی یا سرپرستِ سرشیفتِ ارزیاب باشد؛ در غیر این صورت EvaluationProcessError.
        """
        result = await self.db.execute(
            select(Evaluation)
            .options(selectinload(Evaluation.assignment), selectinload(Evaluation.answers))
            .where(Evaluation.id == evaluation_id)
        )
        evaluation = result.scalar_one_or_none()
        if evaluation is None:
            raise EvaluationProcessError("این ارزیابی یافت نشد")
        await self._ensure_period_enabled(evaluation.assignment.period_id)
        if evaluation.assignment.evaluator_employee_id != evaluator_employee_id and not (
            await self._is_supervisor_of_evaluator(evaluation.assignment.evaluator_employee_id, evaluator_employee_id)
        ):
            raise EvaluationProcessError("شما مجاز به انجام این ارزیابی نیستید")
        return evaluation

    async def get_evaluation(self, evaluation_id: int, requesting_employee_id: int) -> Evaluation:
        """
        ارزیابی را با evaluation_id برمی‌گرداند. برخلاف start_evaluation (با assignment_id و فقط برای
        ارزیاب اصلی)، از بررسی دسترسی _get_owned_evaluation استفاده می‌کند؛ پس سرپرستِ سرشیفتِ ارزیاب هم
        می‌تواند ارزیابی بازشده را ادامه/ویرایش کند.
        """
        return await self._get_owned_evaluation(evaluation_id, requesting_employee_id)

    async def start_evaluation(self, assignment_id: int, evaluator_employee_id: int) -> Evaluation:
        """
        ورودی: انتساب و ارزیاب. اگر Evaluation این انتساب از قبل وجود داشته باشد همان را برمی‌گرداند؛
        وگرنه Evaluation جدید draft با Snapshot اطلاعات همین لحظه (نام‌ها، کدها، سایت، واحد، فرم، دوره) می‌سازد.
        """
        assignment = await self._get_owned_assignment(assignment_id, evaluator_employee_id)

        # ادامه پیش‌نویس موجود
        existing_result = await self.db.execute(
            select(Evaluation)
            .options(selectinload(Evaluation.answers), selectinload(Evaluation.assignment))
            .where(Evaluation.assignment_id == assignment_id)
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            return existing

        # جمع‌آوری اطلاعات لازم برای Snapshot
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

        # پس از commit همه اشیای Session منقضی می‌شوند و دسترسی به روابطشان MissingGreenlet
        # می‌دهد؛ برای همین ارزیابی با selectinload صریح دوباره خوانده می‌شود
        result = await self.db.execute(
            select(Evaluation)
            .options(selectinload(Evaluation.answers), selectinload(Evaluation.assignment))
            .where(Evaluation.id == evaluation_id)
        )
        return result.scalar_one()

    async def save_answers(self, evaluation_id: int, evaluator_employee_id: int, answers: list[dict]) -> Evaluation:
        """
        ورودی: ارزیابی، ارزیاب و فهرست پاسخ‌ها (dict). پاسخ هر سوال را درج یا به‌روز می‌کند (با Snapshot متن/نوع سوال).
        فقط برای ارزیابی draft؛ عدد خارج از بازه [۰, weight] خطا دارد. خروجی: ارزیابی به‌روزشده.
        """
        evaluation = await self._get_owned_evaluation(evaluation_id, evaluator_employee_id)
        if evaluation.status != EvaluationStatus.draft:
            raise EvaluationProcessError("این ارزیابی قبلاً ثبت نهایی شده و دیگر قابل‌ویرایش نیست")

        # درج/به‌روزرسانی پاسخ هر سوال
        for answer_data in answers:
            question = await self.db.get(EvaluationQuestion, answer_data["question_id"])
            if question is None:
                continue  # سوال حذف شده - نادیده گرفته می‌شود

            # در سوال «عدد»، عدد واردشده مستقیماً امتیاز سوال (از حداکثر weight) است،
            # پس باید در بازه [۰, weight] باشد
            if question.question_type.value == "number" and answer_data.get("number_value") is not None:
                number_value = answer_data["number_value"]
                weight = float(question.weight)
                if number_value < 0 or number_value > weight:
                    raise EvaluationProcessError(
                        f"پاسخ سوال «{question.text}» باید بین ۰ تا {weight:g} باشد (وزن این سوال {weight:g} است)"
                    )

            # پاسخ قبلی همین سوال (در صورت وجود) به‌روز می‌شود
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
        """
        ثبت نهایی ارزیابی draft: سوالات الزامی را بررسی، امتیاز هر پاسخ و امتیاز کل وزن‌دار را محاسبه،
        انتساب را completed و وضعیت دوره‌ها را هم‌گام می‌کند و به پرسنل ارزیابی‌شده Push می‌فرستد.
        خروجی: ارزیابی ثبت‌شده؛ سوال الزامی بی‌پاسخ یا وضعیت نادرست: EvaluationProcessError.
        """
        evaluation = await self._get_owned_evaluation(evaluation_id, evaluator_employee_id)
        if evaluation.status != EvaluationStatus.draft:
            raise EvaluationProcessError("این ارزیابی قبلاً ثبت نهایی شده است")

        # فرم کامل (دسته‌بندی/سوال/گزینه) برای اعتبارسنجی و امتیازدهی
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

        # بررسی سوالات الزامیِ فعال بدون پاسخ معنادار
        missing_required = []
        for category in form.categories:
            if not category.is_active:
                continue
            for question in category.questions:
                if (
                    question.is_active
                    and question.required
                    and not self._answer_has_content(question, answers_by_question.get(question.id))
                ):
                    missing_required.append(question.text)
        if missing_required:
            raise EvaluationProcessError(
                "پاسخ به سوالات اجباری زیر الزامی است: "
                + "، ".join(missing_required[:5])
                + ("..." if len(missing_required) > 5 else "")  # حداکثر ۵ سوال در پیام
            )

        # امتیاز هر سوال → میانگین وزن‌دار هر دسته‌بندی → میانگین وزن‌دار کل (فقط موارد فعال)
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
                    answer.score = score  # ذخیره امتیاز سوال روی پاسخ
                question_scores.append({"weight": float(question.weight), "score": score})
            if question_scores:
                category_scores.append(
                    {"weight": float(category.weight), "score": calculate_weighted_average(question_scores)}
                )

        total_score = calculate_weighted_average(category_scores) if category_scores else 0.0

        # نهایی‌کردن ارزیابی و تکمیل انتساب
        evaluation.status = EvaluationStatus.submitted
        evaluation.total_score = total_score
        evaluation.submitted_at = datetime.now(timezone.utc)
        evaluation.assignment.status = EvaluationAssignmentStatus.completed

        await self.db.commit()

        # اگر این آخرین ارزیابی باقی‌مانده دوره بود، دوره همین‌جا خودکار بسته می‌شود؛ اجبار
        # «تکمیل ارزیابی‌ها» به وضعیت دوره وابسته است. خطای این مرحله فقط لاگ می‌شود.
        try:
            from app.services.evaluation_period_service import EvaluationPeriodService

            await EvaluationPeriodService(self.db).sync_automatic_statuses()
        except Exception:
            logger.exception("هم‌گام‌سازی خودکار وضعیت دوره پس از ثبت ارزیابی با خطا مواجه شد")

        # اطلاع‌رسانی Push به پرسنل ارزیابی‌شده؛ خطای Push ثبت ارزیابی را متوقف نمی‌کند
        await self._notify_target_of_submitted_evaluation(evaluation.assignment.target_employee_id)

        return await self._get_owned_evaluation(evaluation_id, evaluator_employee_id)

    async def send_pending_evaluation_reminders(self, days_before_deadline: int = 3) -> dict:
        """
        به ارزیاب‌هایی که ارزیابی انجام‌نشده دارند Push یادآوری می‌فرستد؛ فقط برای دوره‌های active و
        غیرفعال‌نشده (is_disabled=False) که تا days_before_deadline روز دیگر (و هنوز نگذشته) مهلتشان تمام می‌شود.
        هر ارزیاب یک اعلان (با تعداد موارد) می‌گیرد. خروجی: {"notified_evaluators", "pending_total"}.
        """
        now = datetime.now(timezone.utc)
        deadline_limit = now + timedelta(days=days_before_deadline)

        # تعداد انتساب‌های pending هر ارزیاب در دوره‌های واجد شرایط
        result = await self.db.execute(
            select(EvaluationAssignment.evaluator_employee_id, func.count(EvaluationAssignment.id))
            .join(EvaluationPeriod, EvaluationPeriod.id == EvaluationAssignment.period_id)
            .where(
                EvaluationAssignment.status == EvaluationAssignmentStatus.pending,
                EvaluationPeriod.status == EvaluationPeriodStatus.active,
                EvaluationPeriod.is_disabled.is_(False),
                EvaluationPeriod.end_date > now,
                EvaluationPeriod.end_date <= deadline_limit,
            )
            .group_by(EvaluationAssignment.evaluator_employee_id)
        )
        pending_by_evaluator = {row[0]: row[1] for row in result.all()}
        if not pending_by_evaluator:
            return {"notified_evaluators": 0, "pending_total": 0}

        # حساب‌های کاربری ارزیاب‌ها و ارسال یک اعلان برای هر کدام (خطای هر ارسال فقط لاگ می‌شود)
        users_result = await self.db.execute(
            select(User.id, User.employee_id).where(User.employee_id.in_(pending_by_evaluator.keys()))
        )
        notified = 0
        for user_id, employee_id in users_result.all():
            count = pending_by_evaluator.get(employee_id, 0)
            if count <= 0:
                continue
            try:
                await PushService(self.db).notify_users(
                    {user_id},
                    url="/my-performance?tab=personnel",
                    priority="normal",
                    body=(
                        f"{count} ارزیابی عملکرد انجام‌نشده دارید و مهلت آن رو به پایان است.\n"
                        "جهت تکمیل روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید."
                    ),
                )
                notified += 1
            except Exception:
                logger.exception("ارسال یادآوری ارزیابی عملکرد برای کاربر %s با خطا مواجه شد", user_id)

        return {"notified_evaluators": notified, "pending_total": sum(pending_by_evaluator.values())}

    async def _notify_target_of_submitted_evaluation(self, target_employee_id: int) -> None:
        """به کاربرِ پرسنل ارزیابی‌شده اعلان «نتیجه ثبت شد» می‌فرستد؛ نبودن حساب یا خطای Push فقط نادیده/لاگ می‌شود."""
        try:
            result = await self.db.execute(select(User).where(User.employee_id == target_employee_id))
            target_user = result.scalar_one_or_none()
            if target_user is None:
                return
            await PushService(self.db).notify_users(
                {target_user.id},
                url="/my-performance",
                priority="normal",
                body=(
                    "نتیجه ارزیابی عملکرد شما ثبت شد.\n"
                    "جهت مشاهده روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید."
                ),
            )
        except Exception:
            logger.exception("ارسال Push برای نتیجه ارزیابی عملکرد با خطا مواجه شد")

    def _answer_has_content(self, question: EvaluationQuestion, answer: EvaluationAnswer | None) -> bool:
        """
        True اگر پاسخ، بسته به نوع سوال، محتوای واقعی داشته باشد (گزینه انتخاب‌شده، عدد، تاریخ یا متن
        غیرخالی). وجود ردیف خالی کافی نیست، چون save_answers برای هر سوال حتی با مقدار خالی ردیف می‌سازد.
        هم در بررسی سوالات الزامی و هم در _score_single_answer استفاده می‌شود.
        """
        if answer is None:
            return False
        question_type = question.question_type.value
        if question_type in _OPTION_BASED_TYPES:
            return bool(answer.selected_option_ids)
        if question_type == "number":
            return answer.number_value is not None
        if question_type == "date":
            return answer.date_value is not None
        return bool(answer.text_value and answer.text_value.strip())  # متن: فقط غیرخالی پس از strip

    def _score_single_answer(self, question: EvaluationQuestion, answer: EvaluationAnswer | None) -> float:
        """
        امتیاز یک پاسخ را در مقیاس ۰ تا ۱۰۰ برمی‌گرداند:
        - گزینه‌ای: با calculate_option_based_question_score نسبت به بیشترین امتیاز گزینه‌ها
        - عدد: عدد واردشده امتیاز از weight است؛ مثلاً ۱۲ از weight=20 یعنی (۱۲/۲۰)×۱۰۰=۶۰
        - متن/تاریخ: ۱۰۰ اگر پاسخ محتوا داشته باشد (_answer_has_content)، وگرنه ۰
        """
        if question.question_type.value in _OPTION_BASED_TYPES:
            if answer is None or not answer.selected_option_ids:
                return 0.0
            option_scores = [float(o.score) for o in question.options if o.id in answer.selected_option_ids]
            max_option_score = max((float(o.score) for o in question.options), default=0.0)
            return calculate_option_based_question_score(option_scores, max_option_score)

        if question.question_type.value == "number":
            weight = float(question.weight)
            if answer is None or answer.number_value is None or weight <= 0:
                return 0.0
            # محدودسازی دفاعی به [۰, weight]؛ اعتبارسنجی اصلی در save_answers انجام می‌شود
            clamped_value = min(weight, max(0.0, float(answer.number_value)))
            return (clamped_value / weight) * 100

        return 100.0 if self._answer_has_content(question, answer) else 0.0

    # ---------- ویرایش یک‌بارمصرفِ ارزیابیِ ثبت‌نهایی‌شده ----------

    async def reopen_for_edit(self, evaluation_id: int, evaluator_employee_id: int) -> Evaluation:
        """
        ارزیابی ثبت‌شده را یک‌بار (تا وقتی دوره بسته/بایگانی نشده) به draft برمی‌گرداند و was_edited=True
        می‌کند؛ پاسخ‌های قبلی باقی می‌مانند و submit مجدد امتیاز را از نو محاسبه می‌کند.
        بار دوم، وضعیت غیر submitted یا دوره بسته: EvaluationProcessError.
        """
        evaluation = await self._get_owned_evaluation(evaluation_id, evaluator_employee_id)
        if evaluation.status != EvaluationStatus.submitted:
            raise EvaluationProcessError("فقط ارزیابی‌های ثبت‌نهایی‌شده قابل بازکردن مجدد هستند")
        if evaluation.was_edited:
            raise EvaluationProcessError("این ارزیابی قبلاً یک‌بار ویرایش شده - امکان ویرایش دوباره وجود ندارد")

        # بازگشایی فقط تا وقتی دوره بسته/بایگانی نشده
        period = await self.db.get(EvaluationPeriod, evaluation.assignment.period_id)
        if period is None or period.status in (EvaluationPeriodStatus.closed, EvaluationPeriodStatus.archived):
            raise EvaluationProcessError("مهلت این دوره ارزیابی به پایان رسیده - دیگر امکان ویرایش وجود ندارد")

        evaluation.status = EvaluationStatus.draft
        evaluation.was_edited = True
        await self.db.commit()
        return await self._get_owned_evaluation(evaluation_id, evaluator_employee_id)

    # ---------- میانگین یک‌سال اخیر (شمسی) ----------

    async def get_yearly_average(self, employee_id: int, jalali_year: int | None = None) -> dict:
        """
        میانگین و تعداد ارزیابی‌های ثبت‌شده پرسنل (به‌عنوان هدف) در یک سال شمسی (پیش‌فرض سال جاری)،
        بر اساس submitted_at و بدون دوره‌های غیرفعال. خروجی: {"jalali_year", "average_score", "count"}.
        """
        if jalali_year is None:
            jalali_year, _, _ = get_current_jalali_date()
        start_utc, end_utc = jalali_year_range_utc(jalali_year)  # بازه UTC ابتدا تا انتهای سال شمسی

        result = await self.db.execute(
            select(func.avg(Evaluation.total_score), func.count(Evaluation.id))
            .join(EvaluationAssignment, EvaluationAssignment.id == Evaluation.assignment_id)
            .join(EvaluationPeriod, EvaluationPeriod.id == EvaluationAssignment.period_id)
            .where(
                EvaluationPeriod.is_disabled.is_(False),
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
        فهرست ارزیابی‌های ثبت‌شده توسط سرشیفت‌های واحدهایی که این پرسنل سرپرست آن‌هاست (جدیدترین اول)،
        تا سرپرست بتواند آن‌ها را باز و ویرایش کند. اگر سرپرست نباشد یا سرشیفتی نباشد، لیست خالی.
        """
        supervised_department_result = await self.db.execute(
            select(EvaluationDepartmentSupervisor.department_id).where(
                EvaluationDepartmentSupervisor.employee_id == supervisor_employee_id
            )
        )
        supervised_department_ids = [row[0] for row in supervised_department_result.all()]
        if not supervised_department_ids:
            return []

        # سرشیفت‌های آن واحدها
        shift_lead_result = await self.db.execute(
            select(EvaluationShiftLead.id, EvaluationShiftLead.employee_id).where(
                EvaluationShiftLead.department_id.in_(supervised_department_ids)
            )
        )
        shift_lead_rows = shift_lead_result.all()
        shift_lead_employee_ids = [row[1] for row in shift_lead_rows]
        if not shift_lead_employee_ids:
            return []

        # ارزیابی‌های submitted این سرشیفت‌ها در دوره‌های غیرفعال‌نشده
        evaluations_result = await self.db.execute(
            select(Evaluation)
            .options(selectinload(Evaluation.assignment))
            .join(EvaluationAssignment, EvaluationAssignment.id == Evaluation.assignment_id)
            .join(EvaluationPeriod, EvaluationPeriod.id == EvaluationAssignment.period_id)
            .where(
                EvaluationPeriod.is_disabled.is_(False),
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
        """ارزیابی‌هایی که این پرسنل باید انجام دهد (انتساب‌های او، بدون دوره‌های غیرفعال‌شده) با وضعیت هرکدام؛ لیست dict."""
        assignments_result = await self.db.execute(
            select(EvaluationAssignment)
            .options(
                selectinload(EvaluationAssignment.target_employee),
                selectinload(EvaluationAssignment.period),
                selectinload(EvaluationAssignment.form),
            )
            .join(EvaluationPeriod, EvaluationPeriod.id == EvaluationAssignment.period_id)
            .where(
                EvaluationAssignment.evaluator_employee_id == evaluator_employee_id,
                EvaluationPeriod.is_disabled.is_(False),
            )
        )
        assignments = assignments_result.scalars().all()

        # وضعیت Evaluationهای شروع‌شده، به تفکیک انتساب
        evaluations_result = await self.db.execute(
            select(
                Evaluation.assignment_id, Evaluation.id, Evaluation.status, Evaluation.was_edited, Evaluation.total_score
            ).where(Evaluation.assignment_id.in_([a.id for a in assignments]))
        )
        evaluation_by_assignment = {
            row[0]: {"evaluation_id": row[1], "status": row[2].value, "was_edited": row[3], "total_score": row[4]}
            for row in evaluations_result.all()
        }

        # بدون Evaluation یعنی not_started
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
        """نتایج خود پرسنل: ارزیابی‌های ثبت‌شده‌ای که هدفشان بوده (بدون دوره‌های غیرفعال)، جدیدترین اول."""
        result = await self.db.execute(
            select(Evaluation)
            .join(EvaluationAssignment, EvaluationAssignment.id == Evaluation.assignment_id)
            .join(EvaluationPeriod, EvaluationPeriod.id == EvaluationAssignment.period_id)
            .where(
                EvaluationAssignment.target_employee_id == target_employee_id,
                Evaluation.status == EvaluationStatus.submitted,
                EvaluationPeriod.is_disabled.is_(False),
            )
            .order_by(Evaluation.submitted_at.desc())
        )
        return list(result.scalars().all())

    async def get_my_result_answers(self, evaluation_id: int, target_employee_id: int) -> list[EvaluationAnswer]:
        """
        پاسخ‌ها و امتیاز سوال‌به‌سوال یک ارزیابی برای خود پرسنل (غنی‌شده با گزینه‌ها)؛ فقط اگر ارزیابی
        ثبت‌شده باشد و او هدفش بوده، وگرنه EvaluationProcessError. comment در schema خروجی (MyAnswerOut) حذف می‌شود.
        """
        result = await self.db.execute(
            select(Evaluation)
            .join(EvaluationAssignment, EvaluationAssignment.id == Evaluation.assignment_id)
            .join(EvaluationPeriod, EvaluationPeriod.id == EvaluationAssignment.period_id)
            .where(
                Evaluation.id == evaluation_id,
                EvaluationAssignment.target_employee_id == target_employee_id,
                Evaluation.status == EvaluationStatus.submitted,
                EvaluationPeriod.is_disabled.is_(False),
            )
        )
        if result.scalar_one_or_none() is None:
            raise EvaluationProcessError("نتیجه ارزیابی موردنظر یافت نشد")

        # پاسخ‌های ارزیابی به ترتیب ثبت
        answers = await self.db.execute(
            select(EvaluationAnswer)
            .where(EvaluationAnswer.evaluation_id == evaluation_id)
            .order_by(EvaluationAnswer.id)
        )
        return await self._enrich_answers_with_options(list(answers.scalars().all()))

    async def _enrich_answers_with_options(self, answers: list) -> list[dict]:
        """
        ورودی: فهرست EvaluationAnswer. هر پاسخ را به dict تبدیل و برچسب گزینه‌های انتخاب‌شده و فهرست کامل
        گزینه‌های ممکن (با امتیاز و is_selected) را اضافه می‌کند. برچسب گزینه‌ها Snapshot نمی‌شود و با حذف
        سوال (question_id=NULL) این دو فهرست خالی برمی‌گردند.
        """
        # گزینه‌های همه سوالات مرتبط در یک کوئری، گروه‌بندی‌شده بر اساس question_id
        question_ids = {a.question_id for a in answers if a.question_id is not None}
        options_by_question: dict[int, list] = {}
        if question_ids:
            options_result = await self.db.execute(
                select(EvaluationQuestionOption)
                .where(EvaluationQuestionOption.question_id.in_(question_ids))
                .order_by(EvaluationQuestionOption.sort_order)
            )
            for option in options_result.scalars().all():
                options_by_question.setdefault(option.question_id, []).append(option)

        # ساخت dict خروجی هر پاسخ
        enriched = []
        for answer in answers:
            options = options_by_question.get(answer.question_id, [])
            selected_ids = set(answer.selected_option_ids or [])
            enriched.append(
                {
                    "id": answer.id,
                    "question_id": answer.question_id,
                    "question_text_snapshot": answer.question_text_snapshot,
                    "question_type_snapshot": answer.question_type_snapshot,
                    "selected_option_ids": answer.selected_option_ids,
                    "selected_option_labels": [o.label for o in options if o.id in selected_ids],
                    "available_options": [
                        {
                            "id": o.id,
                            "label": o.label,
                            "score": float(o.score),
                            "is_selected": o.id in selected_ids,
                        }
                        for o in options
                    ],
                    "text_value": answer.text_value,
                    "number_value": answer.number_value,
                    "date_value": answer.date_value,
                    "score": answer.score,
                    "comment": answer.comment,
                }
            )
        return enriched

    async def get_evaluation_answers_for_report(self, evaluation_id: int) -> list[EvaluationAnswer]:
        """پاسخ‌های غنی‌شده یک ارزیابی برای گزارش مدیریتی، بدون بررسی مالکیت (کنترل دسترسی بر عهده فراخواننده است)."""
        answers = await self.db.execute(
            select(EvaluationAnswer)
            .where(EvaluationAnswer.evaluation_id == evaluation_id)
            .order_by(EvaluationAnswer.id)
        )
        return await self._enrich_answers_with_options(list(answers.scalars().all()))

    async def get_dashboard_summary(self, employee_id: int) -> dict:
        """
        خلاصه کارت داشبورد در یک درخواست: میانگین و آخرین امتیاز نتایج خود پرسنل، تعداد نتایج، و
        تعداد ارزیابی‌های pending که خودش باید انجام دهد. خروجی: dict مطابق DashboardSummaryOut.
        """
        results = await self.get_my_results(employee_id)
        average_score = sum(r.total_score for r in results) / len(results) if results else None
        latest_score = results[0].total_score if results else None  # نتایج به ترتیب نزولی زمان‌اند

        # انتساب‌های pending که این پرسنل ارزیابِ آن‌هاست (در دوره‌های غیرفعال‌نشده)
        pending_result = await self.db.execute(
            select(EvaluationAssignment.id)
            .join(EvaluationPeriod, EvaluationPeriod.id == EvaluationAssignment.period_id)
            .where(
                EvaluationAssignment.evaluator_employee_id == employee_id,
                EvaluationAssignment.status == EvaluationAssignmentStatus.pending,
                EvaluationPeriod.is_disabled.is_(False),
            )
        )
        pending_count = len(pending_result.all())

        return {
            "average_score": average_score,
            "latest_score": latest_score,
            "results_count": len(results),
            "pending_to_evaluate_count": pending_count,
        }
