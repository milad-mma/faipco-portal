"""سرویس «دوره‌های ارزیابی عملکرد»."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation_content import EvaluationPeriod, EvaluationPeriodStatus


class EvaluationPeriodError(Exception):
    pass


_VALID_STATUSES = {s.value for s in EvaluationPeriodStatus}


class EvaluationPeriodService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_periods(self, site_id: int | None = None) -> list[EvaluationPeriod]:
        query = select(EvaluationPeriod).order_by(EvaluationPeriod.start_date.desc())
        if site_id is not None:
            # site_id=None روی خودِ دوره یعنی «همه سایت‌ها» - همیشه هم نمایش داده شود
            query = query.where((EvaluationPeriod.site_id == site_id) | (EvaluationPeriod.site_id.is_(None)))
        result = await self.db.execute(query)
        return list(result.scalars().all())

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
        if period.status not in (EvaluationPeriodStatus.draft, EvaluationPeriodStatus.scheduled):
            raise EvaluationPeriodError("فقط دوره‌های در وضعیت پیش‌نویس یا زمان‌بندی‌شده قابل‌ویرایش هستند")
        for key, value in data.items():
            setattr(period, key, value)
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
