"""
سرویس «دوره‌های ارزیابی عملکرد»: فهرست دوره‌ها با آمار انتساب‌ها، هم‌گام‌سازی خودکار وضعیت
دوره‌ها بر اساس تاریخ و پیشرفت، ایجاد/ویرایش/حذف دوره، و مدیریت ارزیابی‌های منتشرشده یک دوره.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.evaluation_content import EvaluationPeriod, EvaluationPeriodStatus
from app.models.evaluation_process import Evaluation, EvaluationAssignment, EvaluationAssignmentStatus


class EvaluationPeriodError(Exception):
    """خطای قابل نمایش به کاربر در عملیات دوره‌ها."""
    pass


# مقادیر مجاز وضعیت دوره (برای اعتبارسنجی ورودی)
_VALID_STATUSES = {s.value for s in EvaluationPeriodStatus}


class EvaluationPeriodService:
    """سرویس مدیریت دوره‌های ارزیابی."""

    def __init__(self, db: AsyncSession):
        """ورودی: نشست async دیتابیس."""
        self.db = db

    async def list_periods(
        self, site_id: int | None = None, allowed_site_ids: set[int] | None = None
    ) -> list[EvaluationPeriod]:
        """
        ورودی: site_id اختیاری. ابتدا وضعیت‌های خودکار را هم‌گام می‌کند، سپس دوره‌ها (جدیدترین اول)
        را همراه assignments_total/assignments_completed برمی‌گرداند؛ با site_id، دوره‌های سراسری هم می‌آیند.
        allowed_site_ids: فقط دوره‌های این سایت‌ها به‌علاوه‌ی دوره‌های سراسری (None = بدون محدودیت).
        """
        # هم‌گام‌سازی وضعیت‌ها پیش از نمایش، تا وضعیت واقعی دیده شود
        await self.sync_automatic_statuses()

        query = select(EvaluationPeriod).order_by(EvaluationPeriod.start_date.desc())
        if site_id is not None:
            # site_id=None روی خودِ دوره یعنی «همه سایت‌ها» - همیشه هم نمایش داده شود
            query = query.where((EvaluationPeriod.site_id == site_id) | (EvaluationPeriod.site_id.is_(None)))
        if allowed_site_ids is not None:
            query = query.where(
                EvaluationPeriod.site_id.in_(allowed_site_ids) | EvaluationPeriod.site_id.is_(None)
            )
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
            # ضمیمه‌کردن آمار به اشیای دوره (ویژگی غیر ستونی، برای schema خروجی)
            for period in periods:
                total, done = by_period.get(period.id, (0, 0))
                period.assignments_total = total
                period.assignments_completed = done
        return periods

    async def sync_automatic_statuses(self) -> dict:
        """
        وضعیت دوره‌های scheduled/active را بر اساس تاریخ و پیشرفت به‌روز می‌کند و تعداد تغییرات
        ({"activated", "rescheduled", "closed"}) را برمی‌گرداند. قواعد:

            پیش‌نویس        → دست‌نخورده می‌ماند (تصمیم ادمین، نه تاریخ)
            زمان‌بندی‌شده   → با رسیدن تاریخ شروع، «فعال» می‌شود
            فعال            → اگر تاریخ شروع به آینده منتقل شده باشد، «زمان‌بندی‌شده» می‌شود
            فعال            → با گذشتن تاریخ پایان، «بسته‌شده» می‌شود
            فعال            → اگر همه ارزیابی‌ها زودتر انجام شده باشد، «بسته‌شده» می‌شود
            بسته/بایگانی‌شده → هرگز خودکار باز نمی‌شود

        اجبار «تکمیل ارزیابی‌ها» (access gate) به وضعیت بسته/بایگانی‌شده وابسته است: تا دوره در جریان
        است ارزیاب آزاد است و با بسته‌شدن دوره، کار ناتمام قفل ایجاد می‌کند. ادمین می‌تواند اجبار را در
        تنظیمات غیرفعال کند، زمان‌بندی را تغییر دهد یا وضعیت را دستی به «فعال» برگرداند.
        """
        now = datetime.now(timezone.utc)
        # فقط دوره‌های زمان‌بندی‌شده و فعال بررسی می‌شوند
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
            # دوره بدون هیچ Assignment بسته نمی‌شود (دوره تازه فعال‌شده‌ای که هنوز انتساب ندارد)
            if total > 0 and pending == 0:
                period.status = EvaluationPeriodStatus.closed
                closed += 1

        if activated or rescheduled or closed:  # commit فقط در صورت تغییر
            await self.db.commit()
        return {"activated": activated, "rescheduled": rescheduled, "closed": closed}

    async def create_period(self, data: dict, created_by_user_id: int | None) -> EvaluationPeriod:
        """ورودی: فیلدهای دوره و شناسه سازنده. دوره جدید (draft) را ذخیره و برمی‌گرداند."""
        period = EvaluationPeriod(**data, created_by_user_id=created_by_user_id)
        self.db.add(period)
        await self.db.commit()
        await self.db.refresh(period)
        return period

    async def update_period(self, period_id: int, data: dict) -> EvaluationPeriod:
        """
        فیلدهای دوره (از جمله تاریخ‌ها) را در هر وضعیتی به‌جز archived به‌روز می‌کند.
        اگر دوره بسته‌شده با تاریخ پایان آینده تمدید شود، دوباره فعال/زمان‌بندی‌شده می‌شود.
        خروجی: دوره به‌روزشده؛ اگر نباشد یا بایگانی‌شده باشد EvaluationPeriodError.
        """
        period = await self.db.get(EvaluationPeriod, period_id)
        if period is None:
            raise EvaluationPeriodError("دوره ارزیابی موردنظر یافت نشد")
        # ویرایش (تمدید مهلت) برای دوره‌های فعال و بسته‌شده هم مجاز است؛ فقط بایگانی‌شده‌ها قفل‌اند
        if period.status == EvaluationPeriodStatus.archived:
            raise EvaluationPeriodError("دوره‌های بایگانی‌شده قابل‌ویرایش نیستند - اول وضعیت را تغییر دهید")
        for key, value in data.items():
            setattr(period, key, value)
        now = datetime.now(timezone.utc)
        # بازگشایی دوره بسته‌شده‌ای که تاریخ پایانش به آینده منتقل شده (بر اساس تاریخ شروع: فعال یا زمان‌بندی‌شده)
        if period.status == EvaluationPeriodStatus.closed and period.end_date > now:
            period.status = (
                EvaluationPeriodStatus.scheduled if period.start_date > now else EvaluationPeriodStatus.active
            )
        await self.db.commit()
        # تغییر تاریخ ممکن است وضعیت را عوض کند؛ بلافاصله هم‌گام می‌شود
        await self.sync_automatic_statuses()
        await self.db.refresh(period)
        return period

    async def update_title(self, period_id: int, title: str) -> EvaluationPeriod:
        """
        عنوان دوره را در هر وضعیتی تغییر می‌دهد؛ ارزیابی‌های قبلی از period_title_snapshot استفاده
        می‌کنند، پس تاریخچه تغییر نمی‌کند. اگر دوره نباشد EvaluationPeriodError.
        """
        period = await self.db.get(EvaluationPeriod, period_id)
        if period is None:
            raise EvaluationPeriodError("دوره ارزیابی موردنظر یافت نشد")
        period.title = title
        await self.db.commit()
        await self.db.refresh(period)
        return period

    async def update_status(self, period_id: int, status: str) -> EvaluationPeriod:
        """وضعیت دوره را دستی تنظیم می‌کند؛ وضعیت نامعتبر یا دوره ناموجود: EvaluationPeriodError."""
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
        """
        دوره را همراه همه انتساب‌ها، ارزیابی‌ها و نتایجش (CASCADE، برگشت‌ناپذیر) حذف می‌کند.
        اگر دوره انتساب داشته باشد یا draft نباشد، confirm_title باید دقیقاً برابر عنوان دوره باشد؛
        وگرنه EvaluationPeriodError.
        """
        period = await self.db.get(EvaluationPeriod, period_id)
        if period is None:
            return
        # شمارش انتساب‌ها برای تصمیم درباره نیاز به تأیید
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
        """ارزیابی‌های منتشرشده (انتساب‌های) یک دوره: ارزیاب، ارزیابی‌شونده، فرم، وضعیت و امتیاز (لیست dict)."""
        # انتساب‌های دوره همراه ارزیاب، هدف و فرم
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
        # وضعیت/امتیاز ارزیابی‌های شروع‌شده، به تفکیک assignment_id
        evaluations = {}
        if assignments:
            rows = await self.db.execute(
                select(Evaluation.assignment_id, Evaluation.status, Evaluation.total_score, Evaluation.submitted_at).where(
                    Evaluation.assignment_id.in_([a.id for a in assignments])
                )
            )
            evaluations = {r[0]: r for r in rows.all()}

        def _name(emp):
            """نام کامل پرسنل یا «—» اگر موجود نباشد."""
            return f"{emp.first_name} {emp.last_name}" if emp else "—"

        # ساخت ردیف خروجی برای هر انتساب؛ بدون Evaluation یعنی not_started
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
        """حذف یک ارزیابی منتشرشده (انتساب + ارزیابی و پاسخ‌هایش با CASCADE)؛ اگر در این دوره نباشد EvaluationPeriodError."""
        assignment = await self.db.get(EvaluationAssignment, assignment_id)
        if assignment is None or assignment.period_id != period_id:
            raise EvaluationPeriodError("ارزیابی موردنظر یافت نشد")
        await self.db.delete(assignment)
        await self.db.commit()
