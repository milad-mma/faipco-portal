"""
سرویس فراموشی رمز عبور: تولید، اعتبارسنجی و مصرف توکن یک‌بارمصرف و ارسال آن با ایمیل (لینک) یا پیامک (کد ۶ رقمی).
- request_reset: ساخت و ارسال توکن؛ verify_reset_token: بررسی بدون مصرف؛ reset_password: ثبت رمز جدید و مصرف توکن.
همیشه یک مخاطب ماسک‌شده (masked_contact) و زمان انقضا برگردانده می‌شود، چه شناسه معتبر باشد چه نه؛
برای شناسه‌ی نامعتبر یا بدون ایمیل/موبایل، ماسک ساختگی قطعی (وابسته به identifier، یکسان در درخواست‌های تکراری)
ساخته می‌شود تا از ساختار پاسخ نتوان معتبر بودن شناسه را تشخیص داد.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import WeakPasswordError, hash_password, validate_password_strength
from app.models.employee import Employee
from app.models.password_reset_token import PasswordResetChannel, PasswordResetToken
from app.models.user import User
from app.services.email_service import EmailError, EmailNotConfiguredError, get_smtp_settings, send_email
from app.services.sms_service import SmsError, SmsNotConfiguredError, send_sms_code

EMAIL_TOKEN_TTL_MINUTES = 10  # عمر لینک ایمیل (دقیقه)
SMS_TOKEN_TTL_MINUTES = 5  # عمر کد پیامکی (دقیقه)


class PasswordResetError(Exception):
    """خطای قابل نمایش به کاربر در بازنشانی رمز (توکن نامعتبر/مصرف‌شده/منقضی، رمز ضعیف و ...)."""
    pass


@dataclass
class RequestResetResult:
    """نتیجه‌ی request_reset: مخاطب ماسک‌شده و ثانیه‌های باقی‌مانده تا انقضای توکن."""
    masked_contact: str | None = None
    expires_in_seconds: int | None = None


def _mask_email(email: str) -> str:
    """ایمیل را ماسک می‌کند: ali.rezaei@example.com -> al*******@example.com"""
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = local[0] + "*" * max(1, len(local) - 1)
    else:
        masked_local = local[:2] + "*" * (len(local) - 2)
    return f"{masked_local}@{domain}" if domain else masked_local


def _mask_mobile(mobile: str) -> str:
    """موبایل را ماسک می‌کند (۴ رقم اول و آخر می‌ماند): 09123456789 -> 0912***6789"""
    if len(mobile) <= 8:
        return "*" * len(mobile)
    return mobile[:4] + "*" * (len(mobile) - 8) + mobile[-4:]


def _fake_masked_email(identifier: str) -> str:
    """
    برای شناسه‌ی نامعتبر یا بدون ایمیل، یک ایمیل ماسک‌شده‌ی ساختگی با دامنه‌ی gmail.com می‌سازد
    که به‌طور قطعی از hash شناسه به دست می‌آید. فقط رشته‌ی نمایشی است و هرگز به آن ایمیلی ارسال نمی‌شود.
    """
    digest = hashlib.sha256(f"email:{identifier}".encode()).hexdigest()
    local_len = 4 + (int(digest[0:2], 16) % 5)  # طول محلی بین ۴ تا ۸
    fake_local = digest[2 : 2 + local_len]
    return _mask_email(f"{fake_local}@gmail.com")


# چند پیش‌شماره واقعی و رایج اپراتورهای موبایل ایران (همراه اول، ایرانسل،
# رایتل) - فقط برای ظاهر باورپذیرتر شماره قلابی، نه اتصال به اپراتور واقعی.
_IRAN_MOBILE_PREFIXES = [
    "0912", "0913", "0914", "0915", "0916", "0917", "0918", "0919",
    "0901", "0902", "0903", "0905",
    "0930", "0933", "0935", "0936", "0937", "0938", "0939",
    "0990", "0991",
]


def _fake_masked_mobile(identifier: str) -> str:
    """
    برای شناسه‌ی نامعتبر یا بدون موبایل، یک شماره‌ی ماسک‌شده‌ی ساختگی (با پیش‌شماره‌ی واقعی) از hash شناسه می‌سازد.
    فقط رشته‌ی نمایشی است و هرگز به آن پیامکی ارسال نمی‌شود.
    """
    digest = hashlib.sha256(f"mobile:{identifier}".encode()).hexdigest()
    prefix = _IRAN_MOBILE_PREFIXES[int(digest[0:2], 16) % len(_IRAN_MOBILE_PREFIXES)]
    fake_number = prefix + "".join(str(int(ch, 16) % 10) for ch in digest[2:9])
    return _mask_mobile(fake_number)


async def _find_user_by_identifier(db: AsyncSession, identifier: str) -> User | None:
    """کاربر را با نام‌کاربری یا کد پرسنلی (همان دو روش ورود) پیدا می‌کند؛ اگر نبود None."""
    # ابتدا جست‌وجو بر اساس username
    result = await db.execute(select(User).where(User.username == identifier))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    # سپس پیدا کردن پرسنل با کد پرسنلی و حساب کاربری متصل به او
    result = await db.execute(select(Employee).where(Employee.personnel_code == identifier))
    employee = result.scalar_one_or_none()
    if employee is None:
        return None
    result = await db.execute(select(User).where(User.employee_id == employee.id))
    return result.scalar_one_or_none()


async def _get_user_email(db: AsyncSession, user: User) -> str | None:
    """ایمیل کاربر را برمی‌گرداند؛ اولویت با ایمیل Employee (سینک‌شده)، سپس User.email."""
    if user.employee_id is not None:
        employee = await db.get(Employee, user.employee_id)
        if employee is not None and employee.email:
            return employee.email
    return user.email


async def _get_user_mobile(db: AsyncSession, user: User) -> str | None:
    """موبایل کاربر را از Employee متصل برمی‌گرداند (User فیلد موبایل ندارد)؛ بدون پرسنل: None."""
    if user.employee_id is None:
        return None
    employee = await db.get(Employee, user.employee_id)
    return employee.mobile if employee else None


async def _get_pending_token(db: AsyncSession, user_id: int, now: datetime) -> PasswordResetToken | None:
    """توکن مصرف‌نشده و منقضی‌نشده‌ی کاربر را (در صورت وجود) برمی‌گرداند."""
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
    )
    return result.scalar_one_or_none()


async def request_reset(db: AsyncSession, identifier: str, channel: str, reset_link_base: str) -> RequestResetResult:
    """
    ورودی: شناسه، channel ("email" یا "sms") و reset_link_base (فقط برای ایمیل). توکن می‌سازد و ارسال می‌کند؛ اگر توکن معتبری
    از قبل باشد، توکن جدید ساخته نمی‌شود. خروجی: RequestResetResult (برای شناسه‌ی نامعتبر، ماسک ساختگی و انقضای واقعی کانال).
    خطا فقط وقتی سرویس ایمیل/پیامک تنظیم‌نشده یا قطع باشد (توکن ساخته‌شده حذف می‌شود).
    """
    user = await _find_user_by_identifier(db, identifier)
    if user is None:
        # شناسه‌ی ناموجود: ماسک ساختگی و انقضای واقعی کانال، تا پاسخ با حالت واقعی یکسان باشد
        if channel == "sms":
            return RequestResetResult(
                masked_contact=_fake_masked_mobile(identifier), expires_in_seconds=SMS_TOKEN_TTL_MINUTES * 60
            )
        return RequestResetResult(
            masked_contact=_fake_masked_email(identifier), expires_in_seconds=EMAIL_TOKEN_TTL_MINUTES * 60
        )

    now = datetime.now(timezone.utc)

    # ---------- کانال پیامک ----------
    if channel == "sms":
        mobile = await _get_user_mobile(db, user)
        if not mobile:
            return RequestResetResult(
                masked_contact=_fake_masked_mobile(identifier), expires_in_seconds=SMS_TOKEN_TTL_MINUTES * 60
            )

        # اگر کد معتبری از قبل ارسال شده، کد جدید فرستاده نمی‌شود و زمان باقی‌مانده‌ی همان برگردانده می‌شود
        pending = await _get_pending_token(db, user.id, now)
        if pending is not None:
            remaining = max(0, int((pending.expires_at - now).total_seconds()))
            return RequestResetResult(masked_contact=_mask_mobile(mobile), expires_in_seconds=remaining)

        # کد ۶ رقمی در بازه‌ی ۱۰۰۰۰۰ تا ۹۹۹۹۹۹ (بدون صفر ابتدایی)، چون پارامتر کد در Pattern پیامک
        # معمولاً عددی است و صفرهای ابتدایی حذف می‌شوند
        code = str(secrets.randbelow(900_000) + 100_000)
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=code,
            channel=PasswordResetChannel.sms,
            created_at=now,
            expires_at=now + timedelta(minutes=SMS_TOKEN_TTL_MINUTES),
        )
        db.add(reset_token)
        await db.commit()

        # ارسال پیامک؛ در صورت خطا، توکن ساخته‌شده حذف و خطا دوباره پرتاب می‌شود
        try:
            await send_sms_code(db, to_mobile=mobile, code=code)
        except (SmsNotConfiguredError, SmsError):
            await db.delete(reset_token)
            await db.commit()
            raise
        return RequestResetResult(masked_contact=_mask_mobile(mobile), expires_in_seconds=SMS_TOKEN_TTL_MINUTES * 60)

    # ---------- کانال ایمیل (channel == "email") ----------
    email = await _get_user_email(db, user)
    if not email:
        return RequestResetResult(
            masked_contact=_fake_masked_email(identifier), expires_in_seconds=EMAIL_TOKEN_TTL_MINUTES * 60
        )

    # اگر لینک معتبری از قبل ارسال شده، لینک جدید فرستاده نمی‌شود
    pending = await _get_pending_token(db, user.id, now)
    if pending is not None:
        remaining = max(0, int((pending.expires_at - now).total_seconds()))
        return RequestResetResult(masked_contact=_mask_email(email), expires_in_seconds=remaining)

    token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        channel=PasswordResetChannel.email,
        created_at=now,
        expires_at=now + timedelta(minutes=EMAIL_TOKEN_TTL_MINUTES),
    )
    db.add(reset_token)
    await db.commit()

    reset_link = f"{reset_link_base}?token={token}"

    # موضوع و متن ایمیل از تنظیمات SMTP پنل، یا متن پیش‌فرض
    smtp_settings = await get_smtp_settings(db)
    subject = smtp_settings.password_reset_email_subject or "بازنشانی رمز عبور - پرتال سازمانی"
    body_template = smtp_settings.password_reset_email_body or (
        "برای بازنشانی رمز عبور خود روی لینک زیر کلیک کنید "
        f"(تا {EMAIL_TOKEN_TTL_MINUTES} دقیقه معتبر است):\n\n"
        "{reset_link}\n\n"
        "اگر شما این درخواست را نداده‌اید، این ایمیل را نادیده بگیرید."
    )
    # اگر قالب جای‌گذار {reset_link} نداشته باشد، لینک به انتهای متن اضافه می‌شود
    if "{reset_link}" in body_template:
        # replace به‌جای format() تا آکولادهای دیگر در قالب سفارشی (مثل "{نام}") خطای KeyError ندهند
        body = body_template.replace("{reset_link}", reset_link)
    else:
        body = f"{body_template}\n\n{reset_link}"

    # ارسال ایمیل؛ در صورت خطا، توکن ساخته‌شده حذف و خطا دوباره پرتاب می‌شود
    try:
        await send_email(db, to_address=email, subject=subject, body_text=body)
    except (EmailNotConfiguredError, EmailError):
        await db.delete(reset_token)
        await db.commit()
        raise

    return RequestResetResult(masked_contact=_mask_email(email), expires_in_seconds=EMAIL_TOKEN_TTL_MINUTES * 60)


async def verify_reset_token(db: AsyncSession, token: str) -> None:
    """
    اعتبار توکن/کد را بدون مصرف آن (بدون تغییر used_at) بررسی می‌کند؛ در جریان پیامکی پیش از نمایش فرم رمز جدید.
    خطا: PasswordResetError اگر توکن ناموجود، مصرف‌شده یا منقضی باشد.
    """
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token == token))
    reset_token = result.scalar_one_or_none()
    if reset_token is None:
        raise PasswordResetError("کد/لینک بازنشانی نامعتبر است")
    if reset_token.used_at is not None:
        raise PasswordResetError("این کد/لینک قبلاً استفاده شده است")
    if reset_token.expires_at < datetime.now(timezone.utc):
        raise PasswordResetError("این کد/لینک منقضی شده است — دوباره درخواست بازنشانی بدهید")


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    """
    با توکن معتبر، رمز جدید را (پس از بررسی قدرت رمز) ثبت و توکن را مصرف می‌کند؛ has_custom_password=True می‌شود.
    خطا: PasswordResetError برای توکن ناموجود/مصرف‌شده/منقضی، رمز ضعیف یا کاربر ناموجود.
    """
    # اعتبارسنجی توکن (همان بررسی‌های verify_reset_token)
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token == token))
    reset_token = result.scalar_one_or_none()
    if reset_token is None:
        raise PasswordResetError("کد/لینک بازنشانی نامعتبر است")
    if reset_token.used_at is not None:
        raise PasswordResetError("این کد/لینک قبلاً استفاده شده است")
    if reset_token.expires_at < datetime.now(timezone.utc):
        raise PasswordResetError("این کد/لینک منقضی شده است — دوباره درخواست بازنشانی بدهید")

    try:
        validate_password_strength(new_password)
    except WeakPasswordError as e:
        raise PasswordResetError(str(e))

    user = await db.get(User, reset_token.user_id)
    if user is None:
        raise PasswordResetError("کاربر یافت نشد")

    # ثبت رمز جدید و علامت‌گذاری توکن به‌عنوان مصرف‌شده
    user.password_hash = hash_password(new_password)
    user.has_custom_password = True
    user.must_change_password = False
    reset_token.used_at = datetime.now(timezone.utc)
    await db.commit()
