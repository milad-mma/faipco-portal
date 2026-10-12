"""
سرویس کد تأیید یک‌بارمصرف (OTP) برای عملیات حساس داخل پروفایل کاربر واردشده (جدول verification_codes، Migration 112).

دو کاربرد:
- تغییر رمز عبور (purpose="password"): کد ۶ رقمی به موبایل (پیامک) یا ایمیل خود کاربر فرستاده می‌شود و
  جای «رمز عبور فعلی» را می‌گیرد. اگر کاربر هیچ کانال قابل‌استفاده‌ای نداشته باشد (موبایل/ایمیل ثبت نشده یا
  سرویس پیامک/ایمیل در پنل خاموش باشد)، همان روش قبلی (رمز فعلی) استفاده می‌شود.
- تغییر شماره موبایل (purpose="mobile"): کد فقط با پیامک و به «شماره‌ی جدید» فرستاده می‌شود؛ کد فقط برای همان
  شماره معتبر است (ثابت می‌کند شماره‌ی جدید واقعاً در دست کاربر است). اگر سرویس پیامک خاموش باشد، رمز فعلی لازم است.

نکات امنیتی:
- فقط هش SHA-256 کد ذخیره می‌شود؛ مقایسه constant-time است.
- هر کد ۵ دقیقه عمر دارد، حداکثر ۵ بار اشتباه پذیرفته می‌شود و بعد باطل می‌شود.
- ارسال دوباره تا ۶۰ ثانیه ممکن نیست (ضد اسپم پیامک)؛ با هر ارسال جدید، کدهای قبلی همان هدف باطل می‌شوند.
- برخلاف «فراموشی رمز»، کاربر واردشده است و نشت وجود حساب مطرح نیست؛ پس ارسال همین‌جا (نه در پس‌زمینه)
  انجام می‌شود و خطای درگاه به‌صورت پیام فارسی به کاربر نشان داده می‌شود.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.text_normalize import normalize_search_text
from app.models.user import User
from app.models.verification_code import VerificationCode
from app.services.email_service import get_smtp_settings, send_email
from app.services.password_reset_service import _get_user_email as user_email  # noqa: F401 - برای Endpoint
from app.services.password_reset_service import _get_user_mobile as user_mobile
from app.services.password_reset_service import _mask_email as mask_email
from app.services.password_reset_service import _mask_mobile as mask_mobile
from app.services.sms_service import get_sms_settings, send_sms_code

logger = logging.getLogger(__name__)

PURPOSE_PASSWORD = "password"
PURPOSE_MOBILE = "mobile"
CODE_TTL_SECONDS = 5 * 60  # عمر کد
RESEND_COOLDOWN_SECONDS = 60  # فاصله‌ی مجاز بین دو ارسال
MAX_ATTEMPTS = 5  # حداکثر کد اشتباه برای یک کد
CODE_LENGTH = 6
SEND_TIMEOUT_SECONDS = 30


class OtpError(Exception):
    """خطای قابل نمایش به کاربر (کد اشتباه/منقضی، ارسال ناموفق، ارسال زودهنگام و ...)."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class OtpOptions:
    """کانال‌های قابل‌استفاده برای تغییر رمز: {"sms": "0912***6789", "email": "al***@x.com"}؛ خالی = روش رمز فعلی."""
    channels: dict[str, str] = field(default_factory=dict)

    @property
    def otp_required(self) -> bool:
        return bool(self.channels)


def _hash(code: str) -> str:
    """هش SHA-256 کد (hex)."""
    return hashlib.sha256(code.encode()).hexdigest()


def normalize_code(raw: str | None) -> str:
    """ارقام فارسی/عربی را لاتین و فاصله‌ها را حذف می‌کند."""
    return "".join(ch for ch in normalize_search_text(raw or "") if not ch.isspace())


def generate_code() -> str:
    """کد ۶ رقمی تصادفی امن (100000..999999)."""
    return str(secrets.randbelow(900_000) + 100_000)


async def sms_available(db: AsyncSession) -> bool:
    """True اگر سرویس پیامک در پنل فعال و کامل باشد."""
    s = await get_sms_settings(db)
    return bool(s.enabled and s.api_key_encrypted and s.from_number)


async def email_available(db: AsyncSession) -> bool:
    """True اگر سرویس ایمیل (SMTP) در پنل فعال و کامل باشد."""
    s = await get_smtp_settings(db)
    return bool(s.enabled and s.host and s.from_address)


def is_mandatory_password_change(user: User) -> bool:
    """
    True اگر کاربر در وضعیت «تغییر رمز اجباری» (اولین ورود / رمز پیش‌فرض) باشد؛ همان شرط get_me برای
    must_change_password. در این حالت کد تأیید خواسته نمی‌شود و فقط رمز پیش‌فرض فعلی (کد ملی/رمز اولیه) کافی است.
    """
    return bool(user.must_change_password) or (user.employee_id is not None and not user.has_custom_password)


async def password_options(db: AsyncSession, user: User) -> OtpOptions:
    """
    کانال‌های OTP قابل‌استفاده برای تغییر رمز همین کاربر (با مقصد ماسک‌شده).
    در تغییر رمز اجباری اولین ورود همیشه خالی است (یعنی «رمز عبور فعلی»)، به موبایل/ایمیل کاری ندارد.
    """
    options = OtpOptions()
    if is_mandatory_password_change(user):
        return options
    mobile = await user_mobile(db, user)
    if mobile and await sms_available(db):
        options.channels["sms"] = mask_mobile(mobile)
    email = await user_email(db, user)
    if email and await email_available(db):
        options.channels["email"] = mask_email(email)
    return options


async def _send(db: AsyncSession, channel: str, destination: str, code: str, purpose: str) -> None:
    """ارسال واقعی کد؛ هر خطا به OtpError با پیام فارسی تبدیل می‌شود."""
    try:
        if channel == "sms":
            await asyncio.wait_for(send_sms_code(db, to_mobile=destination, code=code), SEND_TIMEOUT_SECONDS)
        else:
            subject = "کد تأیید تغییر رمز عبور - پرتال سازمانی"
            body = (
                f"کد تأیید شما برای تغییر رمز عبور: {code}\n\n"
                f"این کد تا {CODE_TTL_SECONDS // 60} دقیقه معتبر است.\n"
                "اگر شما درخواست تغییر رمز نداده‌اید، این ایمیل را نادیده بگیرید و رمز عبور خود را عوض کنید."
            )
            await asyncio.wait_for(
                send_email(db, to_address=destination, subject=subject, body_text=body), SEND_TIMEOUT_SECONDS
            )
    except Exception as exc:  # noqa: BLE001 - هر خطای درگاه به پیام قابل فهم تبدیل می‌شود
        logger.exception("ارسال کد تأیید (%s/%s) ناموفق بود", purpose, channel)
        what = "پیامک" if channel == "sms" else "ایمیل"
        raise OtpError(f"ارسال {what} کد تأیید ناموفق بود؛ چند دقیقه بعد دوباره امتحان کنید.") from exc


async def request_code(
    db: AsyncSession, user: User, *, purpose: str, channel: str, destination: str
) -> int:
    """
    کد تازه می‌سازد، کدهای قبلی همین هدف را باطل و کد را به destination می‌فرستد.
    خروجی: عمر کد به ثانیه. خطا: OtpError (ارسال زودتر از ۶۰ ثانیه با retry_after، یا شکست ارسال).
    """
    now = datetime.now(timezone.utc)
    last = (
        await db.execute(
            select(VerificationCode)
            .where(VerificationCode.user_id == user.id, VerificationCode.purpose == purpose)
            .order_by(VerificationCode.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if last is not None:
        created = last.created_at if last.created_at.tzinfo else last.created_at.replace(tzinfo=timezone.utc)
        wait = RESEND_COOLDOWN_SECONDS - int((now - created).total_seconds())
        if wait > 0:
            raise OtpError(f"کد تأیید همین الان ارسال شد؛ {wait} ثانیه دیگر دوباره امتحان کنید.", retry_after=wait)

    # کدهای قبلی (مصرف‌نشده) همین هدف باطل می‌شوند؛ فقط آخرین کد معتبر است
    await db.execute(
        update(VerificationCode)
        .where(
            VerificationCode.user_id == user.id,
            VerificationCode.purpose == purpose,
            VerificationCode.used_at.is_(None),
        )
        .values(used_at=now)
    )
    code = generate_code()
    row = VerificationCode(
        user_id=user.id,
        purpose=purpose,
        channel=channel,
        destination=destination,
        code_hash=_hash(code),
        created_at=now,
        expires_at=now + timedelta(seconds=CODE_TTL_SECONDS),
        attempts=0,
    )
    db.add(row)
    await db.commit()  # قبل از ارسال ذخیره می‌شود تا کد رسیده به کاربر حتماً در دیتابیس باشد

    try:
        await _send(db, channel, destination, code, purpose)
    except OtpError:
        # ارسال نشد: ردیف حذف می‌شود تا محدودیت ۶۰ ثانیه جلوی تلاش دوباره را نگیرد
        await db.delete(row)
        await db.commit()
        raise
    return CODE_TTL_SECONDS


async def verify_and_consume(
    db: AsyncSession, user: User, *, purpose: str, code: str | None, destination: str | None = None
) -> None:
    """
    آخرین کد معتبر این هدف را با code مقایسه می‌کند؛ اگر destination داده شود، کد باید برای همان مقصد ارسال شده باشد.
    درست: کد مصرف‌شده علامت می‌خورد (commit با فراخواننده). اشتباه: شمارنده بالا می‌رود (همین‌جا commit) و OtpError.
    """
    code = normalize_code(code)
    if not code:
        raise OtpError("کد تأیید را وارد کنید.")
    now = datetime.now(timezone.utc)
    row = (
        await db.execute(
            select(VerificationCode)
            .where(
                VerificationCode.user_id == user.id,
                VerificationCode.purpose == purpose,
                VerificationCode.used_at.is_(None),
                VerificationCode.expires_at > now,
            )
            .order_by(VerificationCode.id.desc())
            .limit(1)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise OtpError("کد تأیید منقضی شده یا ارسال نشده است؛ دوباره «ارسال کد» را بزنید.")
    if destination is not None and row.destination != destination:
        raise OtpError("کد تأیید برای این شماره ارسال نشده است؛ برای شماره‌ی جدید دوباره «ارسال کد» را بزنید.")
    if not hmac.compare_digest(row.code_hash, _hash(code)):
        row.attempts += 1
        if row.attempts >= MAX_ATTEMPTS:
            row.used_at = now  # باطل
            await db.commit()
            raise OtpError("کد تأیید چند بار اشتباه وارد شد و باطل شد؛ دوباره «ارسال کد» را بزنید.")
        await db.commit()
        raise OtpError("کد تأیید اشتباه است.")
    row.used_at = now
