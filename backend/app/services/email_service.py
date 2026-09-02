"""
سرویس ارسال ایمیل - از تنظیمات SMTP سراسری (app/models/smtp_settings.py،
یک ردیف Singleton) می‌خواند. کاربرد: «فراموشی رمز عبور» و «ارسال بکاپ به
ایمیل».

smtplib کتابخانه Sync است - برای این‌که کل Event Loop را برای مدت اتصال
SMTP بلاک نکند، در asyncio.to_thread اجرا می‌شود - دقیقاً همان الگوی
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
    pass


class EmailNotConfiguredError(EmailError):
    pass


async def get_smtp_settings(db: AsyncSession) -> SmtpSettings:
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
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, from_address)) if from_name else from_address
    msg["To"] = to_address
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    if attachment:
        filename, content = attachment
        part = MIMEApplication(content, Name=filename)
        part["Content-Disposition"] = f'attachment; filename="{filename}"'
        msg.attach(part)

    server: smtplib.SMTP
    if encryption_mode == "ssl":
        server = smtplib.SMTP_SSL(host, port, timeout=30)
    else:
        server = smtplib.SMTP(host, port, timeout=30)

    try:
        if encryption_mode == "starttls":
            server.starttls()
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
    """attachment اختیاری: (نام_فایل، محتوای_باینری) - برای «ارسال بکاپ به ایمیل»."""
    settings = await get_smtp_settings(db)
    if not settings.enabled:
        raise EmailNotConfiguredError("سرویس ایمیل هنوز در پنل ادمین فعال/تنظیم نشده است")
    if not (settings.host and settings.from_address):
        raise EmailNotConfiguredError("تنظیمات SMTP کامل نیست — آدرس سرور یا آدرس فرستنده خالی است")

    password = decrypt_secret(settings.password_encrypted) if settings.password_encrypted else None

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
