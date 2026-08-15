"""
Rate Limiting ساده و درون‌حافظه‌ای (بدون نیاز به Redis یا هیچ زیرساخت
اضافه‌ای) — دو قابلیت مستقل:

1. قفل موقت ورود بعد از تلاش‌های ناموفق پیاپی (Login Lockout پلکانی):
   ۳ تلاش اشتباه → ۶۰ ثانیه قفل، ۳ تای بعدی (مجموع ۶) → ۵ دقیقه،
   ۳ تای بعدی (مجموع ۹ به بعد) → ۱ ساعت (و همان‌جا می‌ماند).

2. محدودیت ارسال اطلاعیه: هر کاربر حداکثر یک اطلاعیه در هر ۶۰ ثانیه.

⚠️ نکته مهم درباره محدودیت این پیاده‌سازی: چون سرویس Backend این پروژه با
چند Worker (`--workers 2` در systemd) اجرا می‌شود و هر Worker حافظه پایتون
کاملاً جدای خودش را دارد، این شمارنده‌ها **بین Worker ها مشترک نیستند** —
یعنی در بدترین حالت یک کاربر می‌تواند تقریباً به‌اندازه تعداد Worker ها
بیشتر از حد مجاز تلاش کند (نه بی‌نهایت، ولی دقیقاً ۱ هم نیست). برای اجرای
کاملاً دقیق در مقیاس چند-Worker/چند-سرور، باید این شمارنده‌ها به Redis
منتقل شوند. برای وضعیت فعلی پروژه (یک سرور، دو Worker)، این سطح از دقت
کافی و متناسب با پیچیدگی/زیرساخت فعلی است.
"""
from __future__ import annotations

import time

# ---------- قفل موقت ورود ----------

_LOGIN_ATTEMPTS: dict[str, dict] = {}


def _tier_seconds(fail_count: int) -> int:
    if fail_count <= 3:
        return 60
    if fail_count <= 6:
        return 5 * 60
    return 60 * 60  # از ۹ تلاش ناموفق به بعد، همیشه ۱ ساعت


def check_login_lockout(identifier: str) -> float | None:
    """اگر این شناسه (یوزرنیم یا کد پرسنلی) الان قفل باشد، تعداد ثانیه
    باقی‌مانده تا باز شدن قفل را برمی‌گرداند؛ در غیر این‌صورت None."""
    key = identifier.strip().lower()
    record = _LOGIN_ATTEMPTS.get(key)
    if record is None:
        return None
    remaining = record["locked_until"] - time.monotonic()
    return remaining if remaining > 0 else None


def record_failed_login(identifier: str) -> None:
    key = identifier.strip().lower()
    record = _LOGIN_ATTEMPTS.setdefault(key, {"fail_count": 0, "locked_until": 0.0})
    record["fail_count"] += 1
    # فقط دقیقاً وقتی به یک آستانه (۳، ۶، ۹، ۱۲، ...) می‌رسد، قفل تازه اعمال می‌شود
    if record["fail_count"] % 3 == 0:
        record["locked_until"] = time.monotonic() + _tier_seconds(record["fail_count"])


def reset_login_attempts(identifier: str) -> None:
    """بعد از یک ورود موفق صدا زده می‌شود — سابقه تلاش‌های ناموفق پاک می‌شود."""
    _LOGIN_ATTEMPTS.pop(identifier.strip().lower(), None)


# ---------- محدودیت ارسال اطلاعیه ----------

_LAST_MESSAGE_SENT: dict[int, float] = {}
MESSAGE_RATE_LIMIT_SECONDS = 60


def check_message_rate_limit(user_id: int) -> float | None:
    """اگر این کاربر کمتر از یک دقیقه پیش یک اطلاعیه فرستاده، ثانیه‌های
    باقی‌مانده تا مجاز شدن ارسال بعدی را برمی‌گرداند؛ وگرنه None."""
    last_sent = _LAST_MESSAGE_SENT.get(user_id)
    if last_sent is None:
        return None
    remaining = MESSAGE_RATE_LIMIT_SECONDS - (time.monotonic() - last_sent)
    return remaining if remaining > 0 else None


def record_message_sent(user_id: int) -> None:
    _LAST_MESSAGE_SENT[user_id] = time.monotonic()
