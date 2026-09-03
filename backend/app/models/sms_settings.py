"""
مدل تنظیمات پیامک (ippanel Edge API) - یک ردیف واحد (Singleton، id=1)،
دقیقاً همان الگوی SmtpSettings.

کاربرد: «فراموشی رمز عبور از طریق پیامک» (کد تأیید ۶ رقمی).

مستندات ippanel: https://ippanelcom.github.io/Edge-Document/docs/send/
    - webservice: متن پیام کاملاً آزاد
    - pattern: یک الگوی از پیش تأییدشده در پنل ippanel (توصیه‌شده برای
      پیامک‌های تراکنشی/OTP در ایران - شانس بلاک‌شدن کمتر)
"""
from __future__ import annotations

import enum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SmsSendingType(str, enum.Enum):
    webservice = "webservice"  # متن آزاد
    pattern = "pattern"  # الگوی تأییدشده در پنل ippanel


class SmsSettings(Base):
    __tablename__ = "sms_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(String(500), nullable=True)
    from_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sending_type: Mapped[SmsSendingType] = mapped_column(
        Enum(SmsSendingType, name="sms_sending_type"), default=SmsSendingType.pattern, nullable=False
    )
    # فقط برای sending_type=pattern - کد الگوی تأییدشده در پنل ippanel
    pattern_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # فقط برای sending_type=webservice - باید شامل {code} باشد (جای‌گذار کد تأیید)
    webservice_message_template: Mapped[str | None] = mapped_column(String(500), nullable=True)
