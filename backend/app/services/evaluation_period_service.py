"""سرویس «دوره‌های ارزیابی عملکرد»."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation_content import EvaluationPeriod, EvaluationPeriodStatus
from app.models.evaluation_process import EvaluationAssignment, EvaluationAssignmentStatus


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
        return list(result.scalars().all())

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
        # دوره‌های بسته/بایگانی‌شده همچنان قفل‌اند تا تاریخچه ثبت‌شده
        # دست‌نخورده بماند.
        if period.status in (EvaluationPeriodStatus.closed, EvaluationPeriodStatus.archived):
            raise EvaluationPeriodError("دوره‌های بسته یا بایگانی‌شده قابل‌ویرایش نیستند")
        for key, value in data.items():
            setattr(period, key, value)
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

    async def delete_period(self, period_id: int) -> None:
        period = await self.db.get(EvaluationPeriod, period_id)
        if period is None:
            return
        # ⚠️ Historical Integrity: بعد از فعال‌شدن یک دوره (یعنی احتمال دارد
        # ارزیابی واقعی به آن مرتبط شده باشد)، دیگر Hard-Delete مجاز نیست -
        # فقط می‌تواند به «archived» تغییر وضعیت دهد.
        if period.status != EvaluationPeriodStatus.draft:
            raise EvaluationPeriodError(
                "این دوره در وضعیت پیش‌نویس نیست - برای حفظ تاریخچه، به‌جای حذف، وضعیت آن را «بایگانی» کنید"
            )
        await self.db.delete(period)
        await self.db.commit()
