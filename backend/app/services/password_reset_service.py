"""
سرویس «فراموشی رمز عبور» - تولید/اعتبارسنجی/مصرف توکن یک‌بارمصرف، و
ارسال ایمیل حاوی لینک بازنشانی.

امنیتی: خروجی request_reset همیشه یکسان است، چه شناسه واردشده معتبر
باشد چه نه، و چه ایمیلی برای آن ثبت شده باشد چه نه - تا این Endpoint
نتواند برای حدس‌زدن «آیا این نام‌کاربری/کدپرسنلی وجود دارد» استفاده شود
(User Enumeration) - نگاه کنید به Endpoint در app/api/v1/endpoints/auth.py.
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
from app.services.email_service import EmailError, EmailNotConfiguredError, send_email

RESET_TOKEN_TTL_MINUTES = 30


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
    «شناسه یافت نشد» یا «ایمیلی ثبت نشده» پرتاب نمی‌شود - خروجی این تابع
    همیشه بی‌صدا کامل می‌شود، تا Endpoint همیشه یک پیام یکسان نشان دهد
    (جز وقتی خودِ سرویس ایمیل قطع/تنظیم‌نشده باشد که آن خطا بالا می‌رود).
    """
    user = await _find_user_by_identifier(db, identifier)
    if user is None:
        return

    email = await _get_user_email(db, user)
    if not email:
        return

    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        created_at=now,
        expires_at=now + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
    )
    db.add(reset_token)
    await db.commit()

    reset_link = f"{reset_link_base}?token={token}"
    body = (
        f"برای بازنشانی رمز عبور خود روی لینک زیر کلیک کنید "
        f"(تا {RESET_TOKEN_TTL_MINUTES} دقیقه معتبر است):\n\n"
        f"{reset_link}\n\n"
        "اگر شما این درخواست را نداده‌اید، این ایمیل را نادیده بگیرید."
    )
    try:
        await send_email(db, to_address=email, subject="بازنشانی رمز عبور - پرتال سازمانی", body_text=body)
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
