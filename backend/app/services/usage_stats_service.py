"""
ثبت شمارنده استفاده از پرتال — برای نمودار «میزان استفاده» در پنل Admin.

عمداً یک Session کاملاً جدا از Session اصلی درخواست استفاده می‌کند (نه
همان db که به Endpoint تزریق شده) — تا هیچ ارتباطی با Commit/Rollback
تراکنش اصلیِ خودِ درخواست نداشته باشد؛ و در try/except کامل پیچیده شده تا
اگر همین ثبت به هر دلیلی (مثلاً یک لحظه فشار روی دیتابیس) شکست بخورد،
هرگز خودِ درخواست واقعی کاربر را خراب نکند.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.usage_stat import UsageStat

logger = logging.getLogger("faipco.usage")

_TEHRAN_TZ = ZoneInfo("Asia/Tehran")


async def record_usage() -> None:
    try:
        now = datetime.now(_TEHRAN_TZ)
        async with AsyncSessionLocal() as db:
            stmt = (
                pg_insert(UsageStat)
                .values(date=now.date(), hour=now.hour, request_count=1)
                .on_conflict_do_update(
                    index_elements=["date", "hour"],
                    set_={"request_count": UsageStat.request_count + 1},
                )
            )
            await db.execute(stmt)
            await db.commit()
    except Exception:  # noqa: BLE001 - هرگز نباید درخواست واقعی کاربر را خراب کند
        logger.exception("ثبت آمار استفاده ناموفق بود (بی‌اثر روی خودِ درخواست)")


async def get_usage_stats(db: AsyncSession, days: int = 90) -> list[UsageStat]:
    """
    خام‌ترین شکل داده (هر ردیف = یک ساعت مشخص از یک روز مشخص) را برای
    آخرین `days` روز برمی‌گرداند — تجمیع روزانه/هفتگی/ماهانه و «کدام ساعت
    شبانه‌روز پرترافیک‌تر است» عمداً در فرانت‌اند انجام می‌شود (چون حجم داده
    برای این بازه — حداکثر ۹۰×۲۴ ردیف — به‌قدر کافی کوچک است)، نه با چند
    Query تجمیعی جدا برای هر بازه زمانی.
    """
    cutoff = datetime.now(_TEHRAN_TZ).date() - timedelta(days=days)
    result = await db.execute(
        select(UsageStat).where(UsageStat.date >= cutoff).order_by(UsageStat.date, UsageStat.hour)
    )
    return list(result.scalars().all())
