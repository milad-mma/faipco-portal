"""
سرویس «فراموشی رمز عبور» - تولید/اعتبارسنجی/مصرف توکن یک‌بارمصرف، و
ارسال ایمیل حاوی لینک بازنشانی.

امنیتی: خروجی request_reset همیشه یکسان است، چه شناسه واردشده معتبر
باشد چه نه، چه ایمیلی برای آن ثبت شده باشد چه نه، و چه یک درخواست قبلی
هنوز منقضی نشده باشد چه نه - تا این Endpoint نتواند برای حدس‌زدن «آیا
این نام‌کاربری/کدپرسنلی وجود دارد» استفاده شود (User Enumeration) -
نگاه کنید به Endpoint در app/api/v1/endpoints/auth.py.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import WeakPasswordError, hash_password, validate_password_strength
from app.models.employee import Employee
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services.email_service import EmailError, EmailNotConfiguredError, get_smtp_settings, send_email

RESET_TOKEN_TTL_MINUTES = 20


class PasswordResetError(Exception):
    pass


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


async def request_reset(db: AsyncSession, identifier: str, reset_link_base: str) -> None:
    """
    reset_link_base مثلاً "https://portal.example.com/reset-password" -
    توکن به‌عنوان querystring اضافه می‌شود. عمداً هیچ استثنایی برای
    «شناسه یافت نشد»، «ایمیلی ثبت نشده»، یا «یک درخواست قبلی هنوز منقضی
    نشده» پرتاب/افشا نمی‌شود - خروجی این تابع همیشه بی‌صدا کامل می‌شود،
    تا Endpoint همیشه یک پیام یکسان نشان دهد (جز وقتی خودِ سرویس ایمیل
    قطع/تنظیم‌نشده باشد که آن خطا بالا می‌رود - چون آن یک مشکل پیکربندی
    سیستم است، نه اطلاعاتی درباره یک کاربر خاص).
    """
    user = await _find_user_by_identifier(db, identifier)
    if user is None:
        return

    email = await _get_user_email(db, user)
    if not email:
        return

    # ⚠️ محدودیت نرخ: تا وقتی یک توکن معتبر (نه منقضی، نه مصرف‌شده) برای
    # همین کاربر وجود دارد، ایمیل جدیدی فرستاده نمی‌شود - چه برای جلوگیری
    # از اسپم‌کردن صندوق ورودی کاربر، چه برای جلوگیری از سوءاستفاده
    # (درخواست مکرر). این وضعیت کاملاً بی‌صدا است - Endpoint همیشه همان
    # پیام یکسان را نشان می‌دهد (حتی این حالت هم نباید افشا شود، وگرنه
    # می‌شد فهمید شناسه واردشده معتبر است یا نه).
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(PasswordResetToken.id).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
    )
    if result.first() is not None:
        return

    token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        created_at=now,
        expires_at=now + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
    )
    db.add(reset_token)
    await db.commit()

    reset_link = f"{reset_link_base}?token={token}"

    smtp_settings = await get_smtp_settings(db)
    subject = smtp_settings.password_reset_email_subject or "بازنشانی رمز عبور - پرتال سازمانی"
    body_template = smtp_settings.password_reset_email_body or (
        "برای بازنشانی رمز عبور خود روی لینک زیر کلیک کنید "
        f"(تا {RESET_TOKEN_TTL_MINUTES} دقیقه معتبر است):\n\n"
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


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token == token))
    reset_token = result.scalar_one_or_none()
    if reset_token is None:
        raise PasswordResetError("لینک بازنشانی نامعتبر است")
    if reset_token.used_at is not None:
        raise PasswordResetError("این لینک قبلاً استفاده شده است")
    if reset_token.expires_at < datetime.now(timezone.utc):
        raise PasswordResetError("این لینک منقضی شده است — دوباره درخواست بازنشانی بدهید")

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
