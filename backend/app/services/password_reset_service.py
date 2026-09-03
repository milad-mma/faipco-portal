"""
سرویس «فراموشی رمز عبور» - تولید/اعتبارسنجی/مصرف توکن یک‌بارمصرف، و
ارسال از طریق ایمیل (لینک) یا پیامک (کد ۶ رقمی).

⚠️ نکته امنیتی درباره نمایش مخاطب ناقص: طبق درخواست صریح، همیشه یک نسخه
ناقص از مخاطب (masked_contact) و زمان انقضا برگردانده می‌شود - چه
درخواست واقعاً موفق باشد (شناسه معتبر + ایمیل/موبایل ثبت‌شده) چه نه.
برای شناسه نامعتبر یا بدون ایمیل/موبایل ثبت‌شده، یک ماسک قلابی (ولی
قطعی و باورپذیر، وابسته به خودِ identifier - نه تصادفی در هر بار، تا
درخواست‌های تکراری برای همان شناسه، نتیجه یکسان بدهند مثل حالت واقعی)
تولید می‌شود - این‌طور پاسخ از نظر ساختاری («آیا masked_contact خالی
است یا نه») هرگز نمی‌تواند برای تشخیص معتبربودن شناسه استفاده شود؛
تنها راه تشخیص، عملاً دریافت‌نکردن پیام واقعی در ایمیل/موبایل است، که
طبیعتاً از کنترل این سیستم خارج است.
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

EMAIL_TOKEN_TTL_MINUTES = 10
SMS_TOKEN_TTL_MINUTES = 5


class PasswordResetError(Exception):
    pass


@dataclass
class RequestResetResult:
    masked_contact: str | None = None
    expires_in_seconds: int | None = None


def _mask_email(email: str) -> str:
    """ali.rezaei@example.com -> al*******@example.com"""
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = local[0] + "*" * max(1, len(local) - 1)
    else:
        masked_local = local[:2] + "*" * (len(local) - 2)
    return f"{masked_local}@{domain}" if domain else masked_local


def _mask_mobile(mobile: str) -> str:
    """09123456789 -> 0912***6789"""
    if len(mobile) <= 8:
        return "*" * len(mobile)
    return mobile[:4] + "*" * (len(mobile) - 8) + mobile[-4:]


def _fake_masked_email(identifier: str) -> str:
    """
    برای شناسه نامعتبر یا بدون ایمیل ثبت‌شده - یک نسخه ناقص «قابل‌قبول»
    و به‌طور قطعی وابسته به identifier (نه تصادفی در هر بار) تولید
    می‌کند، تا پاسخ از نظر ظاهری از حالت واقعی قابل‌تشخیص نباشد (نه
    خالی/None که خودش یک نشانه افشاکننده بود).
    """
    digest = hashlib.sha256(f"email:{identifier}".encode()).hexdigest()
    local_len = 4 + (int(digest[0:2], 16) % 5)  # طول محلی بین ۴ تا ۸
    fake_local = digest[2 : 2 + local_len]
    domains = ["example.com", "mail.com", "company.com"]
    fake_domain = domains[int(digest[10:12], 16) % len(domains)]
    return _mask_email(f"{fake_local}@{fake_domain}")


def _fake_masked_mobile(identifier: str) -> str:
    digest = hashlib.sha256(f"mobile:{identifier}".encode()).hexdigest()
    fake_number = "09" + "".join(str(int(ch, 16) % 10) for ch in digest[:9])
    return _mask_mobile(fake_number)


async def _find_user_by_identifier(db: AsyncSession, identifier: str) -> User | None:
    """همان دو روش ورود سیستم را پوشش می‌دهد: نام‌کاربری مدیریتی، یا کد پرسنلی."""
    result = await db.execute(select(User).where(User.username == identifier))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    result = await db.execute(select(Employee).where(Employee.personnel_code == identifier))
    employee = result.scalar_one_or_none()
    if employee is None:
        return None
    result = await db.execute(select(User).where(User.employee_id == employee.id))
    return result.scalar_one_or_none()


async def _get_user_email(db: AsyncSession, user: User) -> str | None:
    """اولویت با ایمیل خودِ Employee (تازه Sync شده) - چون User.email عملاً هیچ‌جا ست نمی‌شود."""
    if user.employee_id is not None:
        employee = await db.get(Employee, user.employee_id)
        if employee is not None and employee.email:
            return employee.email
    return user.email


async def _get_user_mobile(db: AsyncSession, user: User) -> str | None:
    """موبایل فقط روی Employee است - User مدل فیلد موبایل ندارد."""
    if user.employee_id is None:
        return None
    employee = await db.get(Employee, user.employee_id)
    return employee.mobile if employee else None


async def _get_pending_token(db: AsyncSession, user_id: int, now: datetime) -> PasswordResetToken | None:
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
    channel: "email" یا "sms". reset_link_base فقط برای channel="email"
    استفاده می‌شود (مثلاً "https://portal.example.com/reset-password").

    برای شناسه نامعتبر یا بدون ایمیل/موبایل ثبت‌شده، یک ماسک قلابی (نگاه
    کنید به _fake_masked_email/_fake_masked_mobile) و زمان انقضای واقعی
    همان کانال برگردانده می‌شود - هیچ استثنایی پرتاب/افشا نمی‌شود، جز
    وقتی خودِ سرویس ایمیل/پیامک قطع/تنظیم‌نشده باشد (که آن یک مشکل
    پیکربندی سیستم است، نه اطلاعاتی درباره یک کاربر خاص).
    """
    user = await _find_user_by_identifier(db, identifier)
    if user is None:
        # ⚠️ حتی برای شناسه ناموجود، یک ماسک قلابی (ولی قطعی و باورپذیر)
        # و زمان انقضای واقعی همان کانال برگردانده می‌شود - نه خالی/None -
        # تا پاسخ از حالت واقعی از نظر ساختاری قابل‌تشخیص نباشد.
        if channel == "sms":
            return RequestResetResult(
                masked_contact=_fake_masked_mobile(identifier), expires_in_seconds=SMS_TOKEN_TTL_MINUTES * 60
            )
        return RequestResetResult(
            masked_contact=_fake_masked_email(identifier), expires_in_seconds=EMAIL_TOKEN_TTL_MINUTES * 60
        )

    now = datetime.now(timezone.utc)

    if channel == "sms":
        mobile = await _get_user_mobile(db, user)
        if not mobile:
            return RequestResetResult(
                masked_contact=_fake_masked_mobile(identifier), expires_in_seconds=SMS_TOKEN_TTL_MINUTES * 60
            )

        pending = await _get_pending_token(db, user.id, now)
        if pending is not None:
            remaining = max(0, int((pending.expires_at - now).total_seconds()))
            return RequestResetResult(masked_contact=_mask_mobile(mobile), expires_in_seconds=remaining)

        # ⚠️ عمداً بدون صفر ابتدایی (بازه ۱۰۰۰۰۰ تا ۹۹۹۹۹۹، نه ۰۰۰۰۰۰ تا
        # ۹۹۹۹۹۹) - چون در قالب‌های Pattern سرویس پیامک، پارامتر کد معمولاً
        # از نوع عددی (Integer) تعریف می‌شود؛ یک رشته با صفر ابتدایی (مثل
        # "003456") در تبدیل به عدد صفرهای ابتدایی‌اش را از دست می‌داد و
        # کد واقعی به کاربر نادرست نمایش داده می‌شد.
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

        try:
            await send_sms_code(db, to_mobile=mobile, code=code)
        except (SmsNotConfiguredError, SmsError):
            await db.delete(reset_token)
            await db.commit()
            raise
        return RequestResetResult(masked_contact=_mask_mobile(mobile), expires_in_seconds=SMS_TOKEN_TTL_MINUTES * 60)

    # channel == "email"
    email = await _get_user_email(db, user)
    if not email:
        return RequestResetResult(
            masked_contact=_fake_masked_email(identifier), expires_in_seconds=EMAIL_TOKEN_TTL_MINUTES * 60
        )

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

    smtp_settings = await get_smtp_settings(db)
    subject = smtp_settings.password_reset_email_subject or "بازنشانی رمز عبور - پرتال سازمانی"
    body_template = smtp_settings.password_reset_email_body or (
        "برای بازنشانی رمز عبور خود روی لینک زیر کلیک کنید "
        f"(تا {EMAIL_TOKEN_TTL_MINUTES} دقیقه معتبر است):\n\n"
        "{reset_link}\n\n"
        "اگر شما این درخواست را نداده‌اید، این ایمیل را نادیده بگیرید."
    )
    # ⚠️ اگر قالب سفارشی Admin عمداً/سهواً جای‌گذار {reset_link} را نداشته
    # باشد، خودِ لینک هم به انتهای پیام اضافه می‌شود - وگرنه ایمیل بدون
    # هیچ لینک قابل‌کلیکی می‌رفت و کاربر هیچ راهی برای بازنشانی نداشت.
    if "{reset_link}" in body_template:
        # ⚠️ عمداً replace ساده به‌جای .format() - اگر Admin در قالب سفارشی
        # به‌اشتباه یک آکولاد دیگر هم بگذارد (مثلاً "{نام}")، format()
        # با KeyError کل ارسال ایمیل را می‌شکست؛ replace با هر متن دیگری
        # کاملاً بی‌خطر کار می‌کند.
        body = body_template.replace("{reset_link}", reset_link)
    else:
        body = f"{body_template}\n\n{reset_link}"

    try:
        await send_email(db, to_address=email, subject=subject, body_text=body)
    except (EmailNotConfiguredError, EmailError):
        await db.delete(reset_token)
        await db.commit()
        raise

    return RequestResetResult(masked_contact=_mask_email(email), expires_in_seconds=EMAIL_TOKEN_TTL_MINUTES * 60)


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
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

    user.password_hash = hash_password(new_password)
    user.has_custom_password = True
    user.must_change_password = False
    reset_token.used_at = datetime.now(timezone.utc)
    await db.commit()
