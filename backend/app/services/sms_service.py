"""
سرویس ارسال پیامک - از تنظیمات پیامک سراسری (app/models/sms_settings.py،
یک ردیف Singleton) می‌خواند. کاربرد: «فراموشی رمز عبور از طریق پیامک»
(کد تأیید ۶ رقمی).

مستندات ippanel Edge API: https://ippanelcom.github.io/Edge-Document/docs/send/
    - Base URL: https://edge.ippanel.com/v1
    - Auth: هدر Authorization با API Key (از پنل ippanel -> Developers -> Access Keys)
    - webservice: متن پیام کاملاً آزاد - POST /api/send با sending_type=webservice
    - pattern: الگوی از پیش تأییدشده در پنل ippanel (توصیه‌شده برای
      پیامک‌های تراکنشی/OTP در ایران) - POST /api/send با sending_type=pattern

httpx به‌صورت Async است - نیازی به asyncio.to_thread نیست (برخلاف smtplib/pymssql).
"""
from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_secret
from app.models.sms_settings import SmsSettings

_SETTINGS_ID = 1
_IPPANEL_SEND_URL = "https://edge.ippanel.com/v1/api/send"


class SmsError(Exception):
    pass


class SmsNotConfiguredError(SmsError):
    pass


async def get_sms_settings(db: AsyncSession) -> SmsSettings:
    settings = await db.get(SmsSettings, _SETTINGS_ID)
    if settings is None:
        settings = SmsSettings(id=_SETTINGS_ID)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


def _to_e164(mobile: str) -> str:
    """۰۹۱۲۳۴۵۶۷۸۹ (فرمت داخلی این پروژه) -> +989123456789 (فرمت مورد نیاز ippanel)."""
    digits = "".join(ch for ch in mobile if ch.isdigit())
    if digits.startswith("0"):
        digits = "98" + digits[1:]
    elif not digits.startswith("98"):
        digits = "98" + digits
    return f"+{digits}"


async def send_sms_code(db: AsyncSession, *, to_mobile: str, code: str) -> None:
    settings = await get_sms_settings(db)
    if not settings.enabled:
        raise SmsNotConfiguredError("سرویس پیامک هنوز در پنل ادمین فعال/تنظیم نشده است")
    if not (settings.api_key_encrypted and settings.from_number):
        raise SmsNotConfiguredError("تنظیمات پیامک کامل نیست - API Key یا شماره فرستنده خالی است")

    api_key = decrypt_secret(settings.api_key_encrypted)
    recipient = _to_e164(to_mobile)

    if settings.sending_type.value == "pattern":
        if not settings.pattern_code:
            raise SmsNotConfiguredError("کد الگوی پیامک (Pattern Code) تنظیم نشده است")
        payload = {
            "sending_type": "pattern",
            "from_number": settings.from_number,
            "code": settings.pattern_code,
            "recipients": [recipient],
            "params": {"code": code},
        }
    else:
        template = settings.webservice_message_template or "کد تأیید بازنشانی رمز عبور شما: {code}"
        message = template.replace("{code}", code) if "{code}" in template else f"{template} {code}"
        payload = {
            "sending_type": "webservice",
            "from_number": settings.from_number,
            "message": message,
            "params": {"recipients": [recipient]},
        }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                _IPPANEL_SEND_URL,
                json=payload,
                headers={"Authorization": api_key, "Content-Type": "application/json"},
            )
        body = response.json()
        if not (response.status_code == 200 and body.get("meta", {}).get("status") is True):
            error_message = body.get("meta", {}).get("message", "خطای نامشخص")
            raise SmsError(f"ارسال پیامک ناموفق بود: {error_message}")
    except httpx.HTTPError as e:
        raise SmsError(f"اتصال به سرویس پیامک ناموفق بود: {e}") from e
