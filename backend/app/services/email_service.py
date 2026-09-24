"""
سرویس ارسال ایمیل - از تنظیمات SMTP سراسری (app/models/smtp_settings.py،
یک ردیف Singleton) می‌خواند. کاربرد: «فراموشی رمز عبور» و «ارسال بکاپ به
ایمیل».

smtplib کتابخانه Sync است - برای این‌که کل Event Loop را برای مدت اتصال
SMTP بلاک نکند، در asyncio.to_thread اجرا می‌شود - همان الگوی
pymssql/smbclient در بقیه این پروژه.
"""
from __future__ import annotations

import asyncio
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_secret
from app.models.smtp_settings import SmtpSettings

_SETTINGS_ID = 1


class EmailError(Exception):
    """خطای عمومی ارسال ایمیل (مثلاً خطای اتصال یا احراز هویت SMTP)."""
    pass


class EmailNotConfiguredError(EmailError):
    """سرویس ایمیل غیرفعال است یا تنظیمات SMTP ناقص است."""
    pass


async def get_smtp_settings(db: AsyncSession) -> SmtpSettings:
    """ردیف تنظیمات SMTP (id=1) را برمی‌گرداند؛ اگر وجود نداشته باشد با مقادیر پیش‌فرض می‌سازد."""
    settings = await db.get(SmtpSettings, _SETTINGS_ID)
    if settings is None:
        settings = SmtpSettings(id=_SETTINGS_ID)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


def _send_email_sync(
    *,
    host: str,
    port: int,
    username: str | None,
    password: str | None,
    encryption_mode: str,
    from_address: str,
    from_name: str | None,
    to_address: str,
    subject: str,
    body_text: str,
    attachment: tuple[str, bytes] | None,
) -> None:
    """
    ارسال هم‌زمان (Sync) یک ایمیل متنی با smtplib؛ برای اجرا در thread جداگانه.
    ورودی: مشخصات سرور، فرستنده، گیرنده، موضوع، متن و پیوست اختیاری (نام، بایت‌ها).
    """
    # ساخت پیام MIME با متن UTF-8
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, from_address)) if from_name else from_address
    msg["To"] = to_address
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    # افزودن پیوست (در صورت وجود)
    if attachment:
        filename, content = attachment
        part = MIMEApplication(content, Name=filename)
        part["Content-Disposition"] = f'attachment; filename="{filename}"'
        msg.attach(part)

    # حالت ssl از ابتدا اتصال رمزنگاری‌شده می‌سازد؛ بقیه حالت‌ها اتصال ساده
    server: smtplib.SMTP
    if encryption_mode == "ssl":
        server = smtplib.SMTP_SSL(host, port, timeout=30)
    else:
        server = smtplib.SMTP(host, port, timeout=30)

    try:
        if encryption_mode == "starttls":
            server.starttls()  # ارتقای اتصال ساده به TLS
        # ورود فقط وقتی نام کاربری و رمز هر دو تنظیم شده باشند
        if username and password:
            server.login(username, password)
        server.sendmail(from_address, [to_address], msg.as_string())
    finally:
        server.quit()


async def send_email(
    db: AsyncSession,
    *,
    to_address: str,
    subject: str,
    body_text: str,
    attachment: tuple[str, bytes] | None = None,
) -> None:
    """
    یک ایمیل را با تنظیمات SMTP ذخیره‌شده ارسال می‌کند.
    attachment اختیاری: (نام_فایل، محتوای_باینری) - برای «ارسال بکاپ به ایمیل».
    خطا: EmailNotConfiguredError اگر سرویس غیرفعال/ناقص باشد، EmailError اگر ارسال شکست بخورد.
    """
    settings = await get_smtp_settings(db)
    if not settings.enabled:
        raise EmailNotConfiguredError("سرویس ایمیل هنوز در پنل ادمین فعال/تنظیم نشده است")
    if not (settings.host and settings.from_address):
        raise EmailNotConfiguredError("تنظیمات SMTP کامل نیست — آدرس سرور یا آدرس فرستنده خالی است")

    # رمز SMTP به‌صورت رمزنگاری‌شده ذخیره شده و اینجا رمزگشایی می‌شود
    password = decrypt_secret(settings.password_encrypted) if settings.password_encrypted else None

    # اجرای ارسال Sync در thread جداگانه تا Event Loop بلاک نشود
    try:
        await asyncio.to_thread(
            _send_email_sync,
            host=settings.host,
            port=settings.port,
            username=settings.username,
            password=password,
            encryption_mode=settings.encryption_mode.value,
            from_address=settings.from_address,
            from_name=settings.from_name,
            to_address=to_address,
            subject=subject,
            body_text=body_text,
            attachment=attachment,
        )
    except (smtplib.SMTPException, OSError) as e:
        raise EmailError(f"ارسال ایمیل ناموفق بود: {e}") from e
