"""سرویس «دوره‌های ارزیابی عملکرد»."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.evaluation_content import EvaluationPeriod, EvaluationPeriodStatus
from app.models.evaluation_process import Evaluation, EvaluationAssignment, EvaluationAssignmentStatus


class EvaluationPeriodError(Exception):
    pass


_VALID_STATUSES = {s.value for s in EvaluationPeriodStatus}


class EvaluationPeriodService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_periods(self, site_id: int | None = None) -> list[EvaluationPeriod]:
        # ⚠️ قبل از نمایش، وضعیت‌های خودکار هم‌گام می‌شوند تا ادمین همیشه
        # وضعیت واقعی را ببیند، نه یک مقدار کهنه.
        await self.sync_automatic_statuses()

        query = select(EvaluationPeriod).order_by(EvaluationPeriod.start_date.desc())
        if site_id is not None:
            # site_id=None روی خودِ دوره یعنی «همه سایت‌ها» - همیشه هم نمایش داده شود
            query = query.where((EvaluationPeriod.site_id == site_id) | (EvaluationPeriod.site_id.is_(None)))
        result = await self.db.execute(query)
        periods = list(result.scalars().all())
        # تعداد ارزیابی‌های منتشرشده (انتساب‌ها) و انجام‌شده هر دوره - برای نمایش در جدول
        if periods:
            counts = await self.db.execute(
                select(
                    EvaluationAssignment.period_id,
                    func.count(EvaluationAssignment.id),
                    func.count(EvaluationAssignment.id).filter(
                        EvaluationAssignment.status == EvaluationAssignmentStatus.completed
                    ),
                )
                .where(EvaluationAssignment.period_id.in_([p.id for p in periods]))
                .group_by(EvaluationAssignment.period_id)
            )
            by_period = {row[0]: (row[1], row[2]) for row in counts.all()}
            for period in periods:
                total, done = by_period.get(period.id, (0, 0))
                period.assignments_total = total
                period.assignments_completed = done
        return periods

    async def sync_automatic_statuses(self) -> dict:
        """
        ⚠️ طبق تصمیم صریح کاربر، چرخه وضعیت دوره کاملاً خودکار است:

            پیش‌نویس        → دست‌نخورده می‌ماند (تصمیم خودِ ادمین، نه تاریخ)
            زمان‌بندی‌شده   → با رسیدن تاریخ شروع، «فعال» می‌شود
            فعال            → با گذشتن تاریخ پایان، «بسته‌شده» می‌شود
            فعال            → اگر همه ارزیابی‌ها زودتر انجام شد، «بسته‌شده»
            بسته/بایگانی‌شده → هرگز خودکار باز نمی‌شود

        ⚠️ اجبارِ «تکمیل ارزیابی‌ها» به وضعیت **بسته/بایگانی‌شده** گره
        خورده است (نه فعال) - یعنی تا وقتی دوره در جریان است ارزیاب آزاد
        است، و به‌محض بسته‌شدنِ دوره (چه با پایان مهلت، چه دستی) اگر
        کاری ناتمام مانده باشد قفل می‌شود.

        سه راه خروج برای ادمین: غیرفعال‌کردن اجبار از تنظیمات، تغییر
        زمان‌بندی دوره، یا برگرداندن دستی وضعیت به «فعال».
        """
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(EvaluationPeriod).where(
                EvaluationPeriod.status.in_(
                    [EvaluationPeriodStatus.scheduled, EvaluationPeriodStatus.active]
                )
            )
        )
        periods = list(result.scalars().all())

        activated = 0
        rescheduled = 0
        closed = 0

        for period in periods:
            # --- گذار زمانی: زمان‌بندی‌شده ↔ فعال ---
            if period.start_date > now and period.status == EvaluationPeriodStatus.active:
                period.status = EvaluationPeriodStatus.scheduled
                rescheduled += 1
                continue
            if period.start_date <= now and period.status == EvaluationPeriodStatus.scheduled:
                period.status = EvaluationPeriodStatus.active
                activated += 1

            if period.status != EvaluationPeriodStatus.active:
                continue

            # --- بستن خودکار با پایان مهلت ---
            if period.end_date < now:
                period.status = EvaluationPeriodStatus.closed
                closed += 1
                continue

            # --- بستن خودکار وقتی همه ارزیابی‌ها زودتر انجام شده ---
            counts = await self.db.execute(
                select(
                    func.count(EvaluationAssignment.id),
                    func.count(EvaluationAssignment.id).filter(
                        EvaluationAssignment.status == EvaluationAssignmentStatus.pending
                    ),
                ).where(EvaluationAssignment.period_id == period.id)
            )
            total, pending = counts.one()
            # ⚠️ دوره‌ای که اصلاً Assignment ندارد بسته نمی‌شود - وگرنه
            # دوره‌ای که ادمین تازه فعال کرده و هنوز تخصیص نداده،
            # بلافاصله بسته می‌شد.
            if total > 0 and pending == 0:
                period.status = EvaluationPeriodStatus.closed
                closed += 1

        if activated or rescheduled or closed:
            await self.db.commit()
        return {"activated": activated, "rescheduled": rescheduled, "closed": closed}

    async def create_period(self, data: dict, created_by_user_id: int | None) -> EvaluationPeriod:
        period = EvaluationPeriod(**data, created_by_user_id=created_by_user_id)
        self.db.add(period)
        await self.db.commit()
        await self.db.refresh(period)
        return period

    async def update_period(self, period_id: int, data: dict) -> EvaluationPeriod:
        period = await self.db.get(EvaluationPeriod, period_id)
        if period is None:
            raise EvaluationPeriodError("دوره ارزیابی موردنظر یافت نشد")
        # ⚠️ طبق درخواست صریح کاربر: ویرایش تاریخ شروع/پایان برای دوره‌های
        # **فعال** هم مجاز شد - چون مهلت‌ها در عمل تمدید می‌شوند و قبلاً
        # تنها راهش ساختن دوره جدید بود (که تاریخچه را تکه‌تکه می‌کرد).
        # ⚠️ طبق درخواست کاربر: دوره «بسته‌شده» هم قابل‌ویرایش است تا بتوان
        # مهلت را تمدید کرد - اگر تاریخ پایان جدید در آینده باشد، دوره دوباره
        # باز می‌شود (فعال یا زمان‌بندی‌شده بر اساس تاریخ شروع). فقط دوره‌های
        # بایگانی‌شده قفل‌اند.
        if period.status == EvaluationPeriodStatus.archived:
            raise EvaluationPeriodError("دوره‌های بایگانی‌شده قابل‌ویرایش نیستند - اول وضعیت را تغییر دهید")
        for key, value in data.items():
            setattr(period, key, value)
        now = datetime.now(timezone.utc)
        if period.status == EvaluationPeriodStatus.closed and period.end_date > now:
            period.status = (
                EvaluationPeriodStatus.scheduled if period.start_date > now else EvaluationPeriodStatus.active
            )
        await self.db.commit()
        # ⚠️ تغییر تاریخ می‌تواند وضعیت را عوض کند (مثلاً جابه‌جایی تاریخ
        # شروع به آینده → «زمان‌بندی‌شده») - بلافاصله هم‌گام می‌شود تا
        # ادمین نتیجه را همان لحظه ببیند.
        await self.sync_automatic_statuses()
        await self.db.refresh(period)
        return period

    async def update_title(self, period_id: int, title: str) -> EvaluationPeriod:
        """
        ⚠️ طبق درخواست صریح: برخلاف update_period (که فقط برای دوره‌های
        هنوز فعال‌نشده مجاز است)، عنوان یک دوره - صرف‌نظر از وضعیتش -
        همیشه قابل‌ویرایش است؛ چون تغییر متن عنوان (بر خلاف تغییر
        تاریخ/سایت) هیچ آسیبی به تاریخچه ارزیابی‌های قبلی نمی‌زند
        (Snapshot ها بر اساس form_title_snapshot/... ذخیره شده‌اند، نه
        یک ارجاع زنده به period.title).
        """
        period = await self.db.get(EvaluationPeriod, period_id)
        if period is None:
            raise EvaluationPeriodError("دوره ارزیابی موردنظر یافت نشد")
        period.title = title
        await self.db.commit()
        await self.db.refresh(period)
        return period

    async def update_status(self, period_id: int, status: str) -> EvaluationPeriod:
        if status not in _VALID_STATUSES:
            raise EvaluationPeriodError(f"وضعیت «{status}» معتبر نیست")
        period = await self.db.get(EvaluationPeriod, period_id)
        if period is None:
            raise EvaluationPeriodError("دوره ارزیابی موردنظر یافت نشد")
        period.status = EvaluationPeriodStatus(status)
        await self.db.commit()
        await self.db.refresh(period)
        return period

    async def set_disabled(self, period_id: int, disabled: bool) -> EvaluationPeriod:
        """غیرفعال/فعال‌کردن دسترسی پرسنل به ارزیابی‌های منتشرشده این دوره (برگشت‌پذیر)."""
        period = await self.db.get(EvaluationPeriod, period_id)
        if period is None:
            raise EvaluationPeriodError("دوره ارزیابی موردنظر یافت نشد")
        period.is_disabled = disabled
        await self.db.commit()
        await self.db.refresh(period)
        return period

    async def delete_period(self, period_id: int, confirm_title: str | None = None) -> None:
        period = await self.db.get(EvaluationPeriod, period_id)
        if period is None:
            return
        # ⚠️ Historical Integrity: دوره‌ای که ارزیابی منتشرشده دارد با همه
        # ارزیابی‌ها و نتایجش حذف می‌شود (CASCADE) - برگشت‌ناپذیر. طبق درخواست
        # کاربر مجاز است، ولی فقط با تأیید صریح (تایپ دقیق عنوان دوره).
        # دوره پیش‌نویسِ بدون انتساب مثل قبل بدون تأیید حذف می‌شود.
        assignments = (
            await self.db.execute(
                select(func.count(EvaluationAssignment.id)).where(EvaluationAssignment.period_id == period_id)
            )
        ).scalar_one()
        needs_confirm = assignments > 0 or period.status != EvaluationPeriodStatus.draft
        if needs_confirm and (confirm_title or "").strip() != period.title.strip():
            raise EvaluationPeriodError(
                "این دوره ارزیابی منتشرشده دارد - برای حذف قطعی (همراه همه ارزیابی‌ها و نتایج)، عنوان دوره را دقیقاً وارد کنید"
            )
        await self.db.delete(period)
        await self.db.commit()

    async def list_assignments(self, period_id: int) -> list[dict]:
        """ارزیابی‌های منتشرشده (انتساب‌های) یک دوره - ارزیاب، ارزیابی‌شونده، فرم، وضعیت، امتیاز."""
        result = await self.db.execute(
            select(EvaluationAssignment)
            .options(
                selectinload(EvaluationAssignment.evaluator_employee),
                selectinload(EvaluationAssignment.target_employee),
                selectinload(EvaluationAssignment.form),
            )
            .where(EvaluationAssignment.period_id == period_id)
            .order_by(EvaluationAssignment.id)
        )
        assignments = list(result.scalars().all())
        evaluations = {}
        if assignments:
            rows = await self.db.execute(
                select(Evaluation.assignment_id, Evaluation.status, Evaluation.total_score, Evaluation.submitted_at).where(
                    Evaluation.assignment_id.in_([a.id for a in assignments])
                )
            )
            evaluations = {r[0]: r for r in rows.all()}

        def _name(emp):
            return f"{emp.first_name} {emp.last_name}" if emp else "—"

        items = []
        for a in assignments:
            ev = evaluations.get(a.id)
            if ev is None:
                state = "not_started"
            else:
                state = ev[1].value
            items.append(
                {
                    "assignment_id": a.id,
                    "evaluator_name": _name(a.evaluator_employee),
                    "evaluator_personnel_code": a.evaluator_employee.personnel_code if a.evaluator_employee else None,
                    "target_name": _name(a.target_employee),
                    "target_personnel_code": a.target_employee.personnel_code if a.target_employee else None,
                    "form_title": a.form.title if a.form else None,
                    "status": state,
                    "total_score": ev[2] if ev else None,
                    "submitted_at": ev[3] if ev else None,
                }
            )
        return items

    async def delete_assignment(self, period_id: int, assignment_id: int) -> None:
        """حذف یک ارزیابی منتشرشده (انتساب + ارزیابی و پاسخ‌هایش - CASCADE)."""
        assignment = await self.db.get(EvaluationAssignment, assignment_id)
        if assignment is None or assignment.period_id != period_id:
            raise EvaluationPeriodError("ارزیابی موردنظر یافت نشد")
        await self.db.delete(assignment)
        await self.db.commit()
