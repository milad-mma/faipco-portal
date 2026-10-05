"""
ثبت شمارنده استفاده از پرتال — برای نمودار «میزان استفاده» در پنل Admin.

شمارش در حافظه‌ی هر Worker انجام می‌شود (record_usage فقط یک dict را زیاد
می‌کند، بدون هیچ Session یا کوئری در مسیر درخواست) و به‌صورت دوره‌ای
(Job هر ۶۰ ثانیه در Scheduler و یک‌بار در shutdown) با flush_usage به دیتابیس
UPSERT می‌شود. معنای داده‌ی ذخیره‌شده همان قبلی است: یک ردیف (date, hour)
به وقت تهران با مجموع تعداد درخواست‌های احرازهویت‌شده‌ی آن ساعت؛ چون
UPSERT تجمعی است (request_count + n)، شمارش چند Worker با هم جمع می‌شود.

flush با Session کاملاً جدا اجرا می‌شود و در try/except کامل پیچیده شده تا
اگر به هر دلیلی (مثلاً یک لحظه فشار روی دیتابیس) شکست بخورد، شمارش
برنگشته دوباره به حافظه برگردد و در تیک بعدی تلاش شود.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.usage_stat import UsageStat

logger = logging.getLogger("faipco.usage")

_TEHRAN_TZ = ZoneInfo("Asia/Tehran")  # تاریخ و ساعت شمارنده‌ها به وقت ایران است

# شمارنده‌ی در حافظه‌ی این Worker: {(تاریخ، ساعت): تعداد درخواست‌های هنوز flush نشده}
_pending_counts: dict[tuple[date, int], int] = {}


def record_usage() -> None:
    """
    شمارنده‌ی در حافظه‌ی درخواست‌های ساعت جاری (به وقت تهران) را یکی زیاد می‌کند.
    همزمان (sync) و بدون دسترسی به دیتابیس — روی مسیر درخواست هیچ تأخیری ندارد؛
    مقدار با flush_usage دوره‌ای به دیتابیس می‌رسد.
    """
    now = datetime.now(_TEHRAN_TZ)
    key = (now.date(), now.hour)
    _pending_counts[key] = _pending_counts.get(key, 0) + 1


async def flush_usage() -> None:
    """
    شمارنده‌های جمع‌شده در حافظه را با UPSERT تجمعی به دیتابیس می‌نویسد
    (ساخت ردیف (date, hour) با مقدار n یا افزودن n به ردیف موجود) و حافظه را خالی می‌کند.
    در صورت خطا، شمارش‌ها به حافظه برمی‌گردند تا در تیک بعدی دوباره تلاش شود؛ خطا فقط لاگ می‌شود.
    """
    global _pending_counts
    if not _pending_counts:
        return
    # dict فعلی برداشته و یک dict تازه جایش گذاشته می‌شود تا درخواست‌های حین flush گم نشوند
    counts, _pending_counts = _pending_counts, {}
    try:
        async with AsyncSessionLocal() as db:
            for (bucket_date, bucket_hour), count in counts.items():
                stmt = (
                    pg_insert(UsageStat)
                    .values(date=bucket_date, hour=bucket_hour, request_count=count)
                    .on_conflict_do_update(
                        index_elements=["date", "hour"],
                        set_={"request_count": UsageStat.request_count + count},
                    )
                )
                await db.execute(stmt)
            await db.commit()
    except BaseException as e:  # noqa: BLE001 - CancelledError (لغو Job هنگام خاموش شدن) هم نباید شمارش را گم کند
        # برگرداندن شمارش‌های نوشته‌نشده به حافظه (جمع با آنچه در این فاصله اضافه شده)
        for key, count in counts.items():
            _pending_counts[key] = _pending_counts.get(key, 0) + count
        if not isinstance(e, Exception):
            raise  # لغو/خروج باید ادامه پیدا کند؛ flush پایانی lifespan شمارش‌ها را می‌نویسد
        logger.exception("ثبت آمار استفاده ناموفق بود — شمارش‌ها برای تلاش بعدی در حافظه نگه داشته شد")


async def get_usage_stats(db: AsyncSession, days: int = 90) -> list[UsageStat]:
    """
    خام‌ترین شکل داده (هر ردیف = یک ساعت مشخص از یک روز مشخص) را برای
    آخرین `days` روز برمی‌گرداند — تجمیع روزانه/هفتگی/ماهانه و «کدام ساعت
    شبانه‌روز پرترافیک‌تر است» عمداً در فرانت‌اند انجام می‌شود (چون حجم داده
    برای این بازه — حداکثر ۹۰×۲۴ ردیف — به‌قدر کافی کوچک است)، نه با چند
    Query تجمیعی جدا برای هر بازه زمانی.
    خروجی: ردیف‌های UsageStat مرتب بر اساس تاریخ و ساعت.
    """
    cutoff = datetime.now(_TEHRAN_TZ).date() - timedelta(days=days)
    result = await db.execute(
        select(UsageStat).where(UsageStat.date >= cutoff).order_by(UsageStat.date, UsageStat.hour)
    )
    return list(result.scalars().all())
