"""
سرویس فراموشی رمز عبور: تولید، اعتبارسنجی و مصرف توکن یک‌بارمصرف و ارسال آن با ایمیل (لینک) یا پیامک (کد ۶ رقمی).
- request_reset: ساخت و ارسال توکن؛ verify_reset_token: بررسی بدون مصرف؛ reset_password: ثبت رمز جدید و مصرف توکن.
همیشه یک مخاطب ماسک‌شده (masked_contact) و زمان انقضای کامل کانال برگردانده می‌شود، چه شناسه معتبر باشد چه نه؛
برای شناسه‌ی نامعتبر یا بدون ایمیل/موبایل، ماسک ساختگی قطعی (وابسته به identifier، یکسان در درخواست‌های تکراری)
ساخته می‌شود تا از ساختار پاسخ نتوان معتبر بودن شناسه را تشخیص داد.

نکات امنیتی:
- ارسال واقعی پیامک/ایمیل در Task پس‌زمینه (Session جدا) انجام می‌شود تا زمان پاسخ برای شناسه‌ی معتبر و نامعتبر
  یکسان باشد و خطای درگاه پیامک به کاربر (و مهاجم) نشت نکند؛ خطا فقط لاگ می‌شود و توکن حذف می‌شود تا کاربر بتواند
  دوباره درخواست بدهد.
- در دیتابیس فقط هش SHA-256 کد/توکن ذخیره می‌شود.
- کد ۶ رقمی پیامکی فقط همراه شناسه‌ی حساب (identifier) پذیرفته و با (user_id, hash) جست‌وجو می‌شود؛ هر کد اشتباه
  شمارنده‌ی attempts همان توکن را بالا می‌برد و پس از MAX_TOKEN_ATTEMPTS توکن باطل می‌شود (حدس ۱۰^۶ حالت غیرممکن).
- توکن طولانی لینک ایمیل (۲۵۶ بیت تصادفی) بدون شناسه هم پذیرفته می‌شود (حدس‌ناپذیر است).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import WeakPasswordError, hash_password, validate_password_strength
from app.models.employee import Employee
from app.models.password_reset_token import PasswordResetChannel, PasswordResetToken
from app.core.text_normalize import normalize_search_text
from app.models.user import User
from app.services.email_service import get_smtp_settings, send_email
from app.services.sms_service import send_sms_code

logger = logging.getLogger(__name__)

EMAIL_TOKEN_TTL_MINUTES = 10  # عمر لینک ایمیل (دقیقه)
SMS_TOKEN_TTL_MINUTES = 5  # عمر کد پیامکی (دقیقه)
MAX_TOKEN_ATTEMPTS = 5  # حداکثر کد اشتباه برای یک توکن؛ بعد از آن توکن باطل می‌شود
SMS_CODE_LENGTH = 6

# Taskهای پس‌زمینه‌ی ارسال (نگه‌داشتن مرجع تا GC آن‌ها را وسط کار جمع نکند)
_background_send_tasks: set[asyncio.Task] = set()


def _hash_token(raw: str) -> str:
    """هش SHA-256 (hex) کد/توکن؛ همین مقدار در ستون token ذخیره و مقایسه می‌شود."""
    return hashlib.sha256(raw.encode()).hexdigest()


def _normalize_code(raw: str) -> str:
    """ارقام فارسی/عربی کد را به لاتین تبدیل و فاصله‌ها را حذف می‌کند (برای توکن طولانی فقط strip)."""
    return "".join(ch for ch in normalize_search_text(raw) if not ch.isspace())


def is_short_code(token: str) -> bool:
    """True اگر token یک کد ۶ رقمی پیامکی باشد (نه توکن طولانی لینک ایمیل)."""
    code = _normalize_code(token)
    return len(code) == SMS_CODE_LENGTH and code.isdigit()


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
    """کاربر را با نام‌کاربری یا کد پرسنلی (همان دو روش ورود) پیدا می‌کند؛ اگر نبود None.
    ارقام فارسی/عربی شناسه به لاتین تبدیل می‌شوند (نام کاربری خام هم امتحان می‌شود)."""
    raw = identifier
    identifier = normalize_search_text(identifier)
    # ابتدا جست‌وجو بر اساس username
    result = await db.execute(select(User).where(User.username.in_({identifier, raw})))
    user = result.scalars().first()
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
        .order_by(PasswordResetToken.id.desc())
    )
    return result.scalars().first()


def _schedule_send(token_id: int, channel: str, destination: str, secret: str, reset_link_base: str) -> None:
    """ارسال پیامک/ایمیل را به‌صورت Task پس‌زمینه زمان‌بندی می‌کند و فوراً برمی‌گردد (الگوی push_background)."""
    task = asyncio.create_task(_send_in_background(token_id, channel, destination, secret, reset_link_base))
    _background_send_tasks.add(task)
    task.add_done_callback(_background_send_tasks.discard)


async def _send_in_background(token_id: int, channel: str, destination: str, secret: str, reset_link_base: str) -> None:
    """
    ارسال واقعی با Session جدا؛ هرگز استثنا پرتاب نمی‌کند. در صورت خطای درگاه (تنظیم‌نشده/قطع)، خطا لاگ و
    توکن ساخته‌شده حذف می‌شود تا کاربر بتواند بلافاصله دوباره درخواست بدهد (وگرنه تا انقضا «در انتظار» می‌ماند).
    """
    from app.db.session import AsyncSessionLocal  # import محلی برای جلوگیری از import حلقه‌ای

    try:
        async with AsyncSessionLocal() as db:
            try:
                if channel == "sms":
                    await asyncio.wait_for(send_sms_code(db, to_mobile=destination, code=secret), timeout=60)
                else:
                    subject, body = await _build_email(db, reset_link_base, secret)
                    await asyncio.wait_for(
                        send_email(db, to_address=destination, subject=subject, body_text=body), timeout=60
                    )
            except Exception:  # noqa: BLE001 - خطای درگاه نباید به کاربر برگردد (نشت وجود حساب)
                logger.exception("ارسال %s بازنشانی رمز ناموفق بود؛ توکن %s حذف می‌شود", channel, token_id)
                reset_token = await db.get(PasswordResetToken, token_id)
                if reset_token is not None:
                    await db.delete(reset_token)
                    await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("خطای پیش‌بینی‌نشده در Task پس‌زمینه‌ی بازنشانی رمز (توکن %s)", token_id)


async def _build_email(db: AsyncSession, reset_link_base: str, token: str) -> tuple[str, str]:
    """موضوع و متن ایمیل بازنشانی را از تنظیمات SMTP پنل (یا متن پیش‌فرض) می‌سازد."""
    reset_link = f"{reset_link_base}?token={token}"
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
    return subject, body


async def request_reset(db: AsyncSession, identifier: str, channel: str, reset_link_base: str) -> RequestResetResult:
    """
    ورودی: شناسه، channel ("email" یا "sms") و reset_link_base (فقط برای ایمیل). توکن می‌سازد (هش آن را ذخیره می‌کند)
    و ارسال را به پس‌زمینه می‌سپارد؛ اگر توکن معتبری از قبل باشد، توکن جدید ساخته نمی‌شود.
    خروجی: RequestResetResult؛ همیشه با عمر کامل کانال (نه زمان باقی‌مانده) تا از پاسخ نتوان وجود حساب یا
    درخواست قبلی را تشخیص داد. هیچ خطایی برای مشکل درگاه پیامک/ایمیل پرتاب نمی‌شود (فقط لاگ).
    """
    ttl_minutes = SMS_TOKEN_TTL_MINUTES if channel == "sms" else EMAIL_TOKEN_TTL_MINUTES
    expires_in = ttl_minutes * 60
    fake = _fake_masked_mobile(identifier) if channel == "sms" else _fake_masked_email(identifier)

    user = await _find_user_by_identifier(db, identifier)
    if user is None:
        # شناسه‌ی ناموجود: ماسک ساختگی و انقضای کامل کانال، تا پاسخ با حالت واقعی یکسان باشد
        return RequestResetResult(masked_contact=fake, expires_in_seconds=expires_in)

    if channel == "sms":
        destination = await _get_user_mobile(db, user)
        masked = _mask_mobile(destination) if destination else None
    else:
        destination = await _get_user_email(db, user)
        masked = _mask_email(destination) if destination else None
    if not destination:
        return RequestResetResult(masked_contact=fake, expires_in_seconds=expires_in)

    now = datetime.now(timezone.utc)
    # اگر کد/لینک معتبری از قبل ارسال شده، دوباره فرستاده نمی‌شود (ضد اسپم پیامک)؛ پاسخ همان شکل عادی است
    pending = await _get_pending_token(db, user.id, now)
    if pending is not None:
        return RequestResetResult(masked_contact=masked, expires_in_seconds=expires_in)

    if channel == "sms":
        # کد ۶ رقمی در بازه‌ی ۱۰۰۰۰۰ تا ۹۹۹۹۹۹ (بدون صفر ابتدایی)، چون پارامتر کد در Pattern پیامک
        # معمولاً عددی است و صفرهای ابتدایی حذف می‌شوند
        secret = str(secrets.randbelow(900_000) + 100_000)
        token_channel = PasswordResetChannel.sms
    else:
        secret = secrets.token_urlsafe(32)
        token_channel = PasswordResetChannel.email

    reset_token = PasswordResetToken(
        user_id=user.id,
        token=_hash_token(secret),
        channel=token_channel,
        created_at=now,
        expires_at=now + timedelta(minutes=ttl_minutes),
        attempts=0,
    )
    db.add(reset_token)
    await db.commit()

    # ارسال در پس‌زمینه؛ پاسخ HTTP منتظر درگاه نمی‌ماند
    _schedule_send(reset_token.id, channel, destination, secret, reset_link_base)
    return RequestResetResult(masked_contact=masked, expires_in_seconds=expires_in)


async def _lookup_token(db: AsyncSession, token: str, identifier: str | None) -> PasswordResetToken:
    """
    توکن معتبر را پیدا می‌کند یا PasswordResetError می‌دهد. منطق:
    - کد ۶ رقمی پیامکی فقط با identifier پذیرفته می‌شود و با (user_id, hash) جست‌وجو می‌شود؛
    - توکن طولانی لینک ایمیل بدون identifier هم با hash تنها پیدا می‌شود (اگر identifier بود، به حساب هم مقید می‌شود).
    کد اشتباه برای حسابی که توکن در انتظار دارد، attempts آن توکن را بالا می‌برد و پس از MAX_TOKEN_ATTEMPTS
    توکن باطل (used_at) می‌شود؛ پیام خطا در همه‌ی حالت‌های «نامعتبر» یکسان است تا چیزی نشت نکند.
    """
    invalid = PasswordResetError("کد/لینک بازنشانی نامعتبر است")
    code = _normalize_code(token)
    if not code:
        raise invalid
    token_hash = _hash_token(code)
    now = datetime.now(timezone.utc)

    user: User | None = None
    if identifier:
        user = await _find_user_by_identifier(db, identifier)
        if user is None:
            raise invalid
    elif is_short_code(code):
        # کد کوتاه بدون شناسه‌ی حساب: جست‌وجوی سراسری اجازه‌ی حدس روی همه‌ی حساب‌ها را می‌داد
        raise invalid

    conds = [PasswordResetToken.token == token_hash]
    if user is not None:
        conds.append(PasswordResetToken.user_id == user.id)
    result = await db.execute(select(PasswordResetToken).where(*conds).order_by(PasswordResetToken.id.desc()))
    reset_token = result.scalars().first()

    if reset_token is None:
        if user is not None:
            pending = await _get_pending_token(db, user.id, now)
            if pending is not None:
                pending.attempts = (pending.attempts or 0) + 1
                if pending.attempts >= MAX_TOKEN_ATTEMPTS:
                    pending.used_at = now  # باطل‌کردن: کاربر باید کد جدید بگیرد
                    logger.warning("توکن بازنشانی کاربر %s پس از %s کد اشتباه باطل شد", user.id, pending.attempts)
                await db.commit()
        raise invalid
    if reset_token.used_at is not None:
        raise PasswordResetError("این کد/لینک قبلاً استفاده شده است")
    if reset_token.expires_at < now:
        raise PasswordResetError("این کد/لینک منقضی شده است — دوباره درخواست بازنشانی بدهید")
    return reset_token


async def verify_reset_token(db: AsyncSession, token: str, identifier: str | None = None) -> None:
    """
    اعتبار توکن/کد را بدون مصرف آن (بدون تغییر used_at) بررسی می‌کند؛ در جریان پیامکی پیش از نمایش فرم رمز جدید.
    identifier (نام‌کاربری/کد پرسنلی) برای کد ۶ رقمی الزامی است. خطا: PasswordResetError اگر توکن ناموجود،
    مصرف‌شده یا منقضی باشد (کد اشتباه شمارنده‌ی تلاش توکن را بالا می‌برد).
    """
    await _lookup_token(db, token, identifier)


async def reset_password(db: AsyncSession, token: str, new_password: str, identifier: str | None = None) -> None:
    """
    با توکن معتبر، رمز جدید را (پس از بررسی قدرت رمز) ثبت و توکن را مصرف می‌کند؛ has_custom_password=True می‌شود.
    identifier برای کد ۶ رقمی الزامی است. خطا: PasswordResetError برای توکن ناموجود/مصرف‌شده/منقضی،
    رمز ضعیف یا کاربر ناموجود.
    """
    reset_token = await _lookup_token(db, token, identifier)

    try:
        validate_password_strength(new_password)
    except WeakPasswordError as e:
        raise PasswordResetError(str(e))

    user = await db.get(User, reset_token.user_id)
    if user is None:
        raise PasswordResetError("کاربر یافت نشد")

    # ثبت رمز جدید و علامت‌گذاری توکن به‌عنوان مصرف‌شده
    now = datetime.now(timezone.utc)
    user.password_hash = hash_password(new_password)
    user.has_custom_password = True
    user.must_change_password = False
    user.password_changed_at = now  # ابطال همه‌ی توکن‌های قبلی (مثلاً نشست مهاجمی که رمز قبلی را داشت)
    reset_token.used_at = now
    await db.commit()
