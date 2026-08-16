"""
Rate Limiting — نسخه پایگاه‌داده‌ای (نه درون‌حافظه‌ای) — دو قابلیت مستقل:

1. قفل موقت ورود بعد از تلاش‌های ناموفق پیاپی (Login Lockout پلکانی):
   ۳ تلاش اشتباه → ۶۰ ثانیه قفل، ۳ تای بعدی (مجموع ۶) → ۵ دقیقه،
   ۳ تای بعدی (مجموع ۹ به بعد) → ۱ ساعت (و همان‌جا می‌ماند).

2. محدودیت ارسال اطلاعیه: هر کاربر حداکثر یک اطلاعیه در هر ۶۰ ثانیه.

⚠️ نسخه قبلی این ماژول شمارنده‌ها را فقط در یک dict پایتون (درون‌حافظه)
نگه می‌داشت — چون سرویس با چند Worker (`--workers 2`) اجرا می‌شود و هر
Worker حافظه پایتون کاملاً جدای خودش را دارد، آن شمارنده‌ها بین Worker ها
مشترک نبودند. یک تست نفوذ زنده این را تأیید کرد: تلاش‌های ناموفق ورود
بین دو Worker پخش می‌شدند و هیچ‌کدام به آستانه ۳ تلاش نمی‌رسیدند — یعنی
Lockout عملاً همیشه دور زده می‌شد، نه فقط گاهی. این نسخه همه شمارنده‌ها
را در دیتابیس نگه می‌دارد (با UPSERT اتمیک PostgreSQL) تا همه Worker ها
(و در آینده حتی چند سرور) دقیقاً یک شمارنده مشترک ببینند.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rate_limit import LoginAttempt, MessageRateLimit

# ---------- قفل موقت ورود ----------


def _tier_seconds(fail_count: int) -> int:
    if fail_count <= 3:
        return 60
    if fail_count <= 6:
        return 5 * 60
    return 60 * 60  # از ۹ تلاش ناموفق به بعد، همیشه ۱ ساعت


async def check_login_lockout(db: AsyncSession, identifier: str) -> float | None:
    """اگر این شناسه (یوزرنیم یا کد پرسنلی) الان قفل باشد، تعداد ثانیه
    باقی‌مانده تا باز شدن قفل را برمی‌گرداند؛ در غیر این‌صورت None."""
    key = identifier.strip().lower()
    result = await db.execute(select(LoginAttempt).where(LoginAttempt.identifier == key))
    record = result.scalar_one_or_none()
    if record is None or record.locked_until is None:
        return None
    remaining = (record.locked_until - datetime.now(timezone.utc)).total_seconds()
    return remaining if remaining > 0 else None


async def record_failed_login(db: AsyncSession, identifier: str) -> None:
    key = identifier.strip().lower()
    now = datetime.now(timezone.utc)

    # UPSERT اتمیک — اگر رکورد از قبل هست، fail_count را در همان دستور
    # (نه با Select جدا) یکی زیاد می‌کند؛ این از یک Race Condition کلاسیک
    # (دو درخواست هم‌زمان، هرکدام یک افزایش را گم کنند) جلوگیری می‌کند.
    stmt = (
        pg_insert(LoginAttempt)
        .values(identifier=key, fail_count=1, locked_until=None, updated_at=now)
        .on_conflict_do_update(
            index_elements=["identifier"],
            set_={"fail_count": LoginAttempt.fail_count + 1, "updated_at": now},
        )
    )
    await db.execute(stmt)
    await db.commit()

    result = await db.execute(select(LoginAttempt).where(LoginAttempt.identifier == key))
    record = result.scalar_one()
    # فقط دقیقاً وقتی به یک آستانه (۳، ۶، ۹، ۱۲، ...) می‌رسد، قفل تازه اعمال می‌شود
    if record.fail_count % 3 == 0:
        record.locked_until = now + timedelta(seconds=_tier_seconds(record.fail_count))
        await db.commit()


async def reset_login_attempts(db: AsyncSession, identifier: str) -> None:
    """بعد از یک ورود موفق صدا زده می‌شود — سابقه تلاش‌های ناموفق پاک می‌شود."""
    key = identifier.strip().lower()
    await db.execute(delete(LoginAttempt).where(LoginAttempt.identifier == key))
    await db.commit()


# ---------- محدودیت ارسال اطلاعیه ----------

MESSAGE_RATE_LIMIT_SECONDS = 60


async def check_message_rate_limit(db: AsyncSession, user_id: int) -> float | None:
    """اگر این کاربر کمتر از یک دقیقه پیش یک اطلاعیه فرستاده، ثانیه‌های
    باقی‌مانده تا مجاز شدن ارسال بعدی را برمی‌گرداند؛ وگرنه None."""
    result = await db.execute(select(MessageRateLimit).where(MessageRateLimit.user_id == user_id))
    record = result.scalar_one_or_none()
    if record is None:
        return None
    remaining = MESSAGE_RATE_LIMIT_SECONDS - (datetime.now(timezone.utc) - record.last_sent_at).total_seconds()
    return remaining if remaining > 0 else None


async def record_message_sent(db: AsyncSession, user_id: int) -> None:
    now = datetime.now(timezone.utc)
    stmt = (
        pg_insert(MessageRateLimit)
        .values(user_id=user_id, last_sent_at=now)
        .on_conflict_do_update(index_elements=["user_id"], set_={"last_sent_at": now})
    )
    await db.execute(stmt)
    await db.commit()
