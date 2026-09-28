"""
Rate Limiting — نسخه پایگاه‌داده‌ای (نه درون‌حافظه‌ای) — دو قابلیت مستقل:

1. قفل موقت ورود بعد از تلاش‌های ناموفق پیاپی (Login Lockout پلکانی):
   پیش‌فرض: ۳ تلاش اشتباه → ۶۰ ثانیه قفل، ۳ تای بعدی (مجموع ۶) → ۵ دقیقه،
   ۳ تای بعدی (مجموع ۹ به بعد) → ۱ ساعت (و همان‌جا می‌ماند). تعداد و مدت‌ها از «امنیت ورود»
   (login_security_service) قابل تنظیم‌اند.

2. محدودیت ارسال اطلاعیه: هر کاربر حداکثر یک اطلاعیه در هر ۶۰ ثانیه.

همه شمارنده‌ها در دیتابیس (جدول‌های LoginAttempt و MessageRateLimit) با UPSERT
اتمیک PostgreSQL نگهداری می‌شوند تا همه Workerهای uvicorn (و حتی چند سرور)
یک شمارنده مشترک ببینند؛ شمارنده درون‌حافظه‌ای بین Workerها مشترک نیست.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rate_limit import LoginAttempt, MessageRateLimit
from app.core.text_normalize import normalize_search_text

# ---------- قفل موقت ورود ----------


DEFAULT_ATTEMPTS_PER_TIER = 3  # هر چند تلاش ناموفق یک پله‌ی قفل
DEFAULT_LOCK_SECONDS = (60, 5 * 60, 60 * 60)  # مدت قفل پله‌ها؛ از آخرین پله به بعد همان می‌ماند


def _tier_seconds(fail_count: int, attempts_per_tier: int = DEFAULT_ATTEMPTS_PER_TIER,
                  lock_seconds: tuple[int, ...] | list[int] = DEFAULT_LOCK_SECONDS) -> int:
    """ورودی: تعداد تلاش ناموفق و تنظیم پله‌ها. خروجی: مدت قفل پله‌ی فعلی به ثانیه."""
    tier = max(1, math.ceil(fail_count / max(1, attempts_per_tier)))
    seconds = list(lock_seconds) or list(DEFAULT_LOCK_SECONDS)
    return int(seconds[min(tier, len(seconds)) - 1])


def _login_key(identifier: str) -> str:
    """کلید شمارنده‌ی تلاش ورود: «۱۲۳» و «123» یک شمارنده دارند (وگرنه تعداد تلاش مجاز دو برابر می‌شد)."""
    return normalize_search_text(identifier).lower()


async def check_login_lockout(db: AsyncSession, identifier: str) -> float | None:
    """اگر این شناسه (یوزرنیم یا کد پرسنلی) الان قفل باشد، تعداد ثانیه
    باقی‌مانده تا باز شدن قفل را برمی‌گرداند؛ در غیر این‌صورت None."""
    key = _login_key(identifier)  # شناسه بدون حساسیت به حروف، فاصله و ارقام فارسی/لاتین
    result = await db.execute(select(LoginAttempt).where(LoginAttempt.identifier == key))
    record = result.scalar_one_or_none()
    if record is None or record.locked_until is None:
        return None
    remaining = (record.locked_until - datetime.now(timezone.utc)).total_seconds()
    return remaining if remaining > 0 else None


async def record_failed_login(
    db: AsyncSession,
    identifier: str,
    attempts_per_tier: int = DEFAULT_ATTEMPTS_PER_TIER,
    lock_seconds: tuple[int, ...] | list[int] = DEFAULT_LOCK_SECONDS,
) -> int:
    """
    ورودی: session، شناسه ورود و تنظیم پله‌ها (از تنظیمات امنیت ورود). یک تلاش ناموفق ثبت می‌کند
    (fail_count یکی زیاد می‌شود) و در هر مضرب attempts_per_tier، قفل پلکانی جدید اعمال می‌شود.
    خروجی: fail_count به‌روزشده.
    """
    key = _login_key(identifier)
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

    # خواندن مقدار به‌روزشده fail_count بعد از UPSERT
    result = await db.execute(select(LoginAttempt).where(LoginAttempt.identifier == key))
    record = result.scalar_one()
    # فقط دقیقاً وقتی به یک آستانه (مثلاً ۳، ۶، ۹، ...) می‌رسد، قفل تازه اعمال می‌شود
    per_tier = max(1, attempts_per_tier)
    if record.fail_count % per_tier == 0:
        record.locked_until = now + timedelta(seconds=_tier_seconds(record.fail_count, per_tier, lock_seconds))
        await db.commit()
    return record.fail_count


async def get_fail_count(db: AsyncSession, identifier: str) -> int:
    """تعداد تلاش‌های ناموفق پیاپی ثبت‌شده برای این شناسه (۰ اگر سابقه‌ای نیست)."""
    result = await db.execute(select(LoginAttempt.fail_count).where(LoginAttempt.identifier == _login_key(identifier)))
    return result.scalar_one_or_none() or 0


async def lock_key_for(db: AsyncSession, identifier: str, seconds: int) -> None:
    """کلید داده‌شده (مثلاً ip:1.2.3.4) را تا seconds ثانیه‌ی بعد قفل می‌کند (UPSERT اتمیک)."""
    key = _login_key(identifier)
    now = datetime.now(timezone.utc)
    until = now + timedelta(seconds=seconds)
    stmt = (
        pg_insert(LoginAttempt)
        .values(identifier=key, fail_count=0, locked_until=until, updated_at=now)
        .on_conflict_do_update(index_elements=["identifier"], set_={"locked_until": until, "updated_at": now})
    )
    await db.execute(stmt)
    await db.commit()


async def reset_login_attempts(db: AsyncSession, identifier: str) -> None:
    """بعد از یک ورود موفق صدا زده می‌شود — سابقه تلاش‌های ناموفق پاک می‌شود."""
    key = _login_key(identifier)
    await db.execute(delete(LoginAttempt).where(LoginAttempt.identifier == key))
    await db.commit()


# ---------- محدودیت ارسال اطلاعیه ----------

MESSAGE_RATE_LIMIT_SECONDS = 60  # حداقل فاصله بین دو اطلاعیه از یک کاربر


async def check_message_rate_limit(db: AsyncSession, user_id: int) -> float | None:
    """اگر این کاربر کمتر از یک دقیقه پیش یک اطلاعیه فرستاده، ثانیه‌های
    باقی‌مانده تا مجاز شدن ارسال بعدی را برمی‌گرداند؛ وگرنه None."""
    # آخرین زمان ارسال این کاربر
    result = await db.execute(select(MessageRateLimit).where(MessageRateLimit.user_id == user_id))
    record = result.scalar_one_or_none()
    if record is None:
        return None
    remaining = MESSAGE_RATE_LIMIT_SECONDS - (datetime.now(timezone.utc) - record.last_sent_at).total_seconds()
    return remaining if remaining > 0 else None


async def record_message_sent(db: AsyncSession, user_id: int) -> None:
    """ورودی: session و شناسه کاربر. زمان آخرین ارسال اطلاعیه را ثبت/به‌روز می‌کند."""
    now = datetime.now(timezone.utc)
    # UPSERT: درج رکورد جدید یا به‌روزرسانی last_sent_at
    stmt = (
        pg_insert(MessageRateLimit)
        .values(user_id=user_id, last_sent_at=now)
        .on_conflict_do_update(index_elements=["user_id"], set_={"last_sent_at": now})
    )
    await db.execute(stmt)
    await db.commit()
