"""
Schema های تنظیمات پیامک (ippanel) - همان الگوی امنیتی SmtpSettingsIn/Out:
API Key هرگز در پاسخ برنمی‌گردد؛ در ورودی اختیاری است - خالی یعنی مقدار
قبلی حفظ شود. مورد استفاده در endpointهای /system/sms-settings.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.models.sms_settings import SmsSendingType


class SmsSettingsIn(BaseModel):
    """ورودی PUT /system/sms-settings."""
    enabled: bool = False
    api_key: str | None = Field(default=None, description="در ویرایش، خالی بگذارید تا مقدار قبلی حفظ شود")
    from_number: str | None = None
    sending_type: SmsSendingType = SmsSendingType.pattern
    pattern_code: str | None = None
    webservice_message_template: str | None = Field(
        default=None, description="می‌تواند شامل {code} باشد که با کد تأیید واقعی جایگزین می‌شود"
    )

    @model_validator(mode="after")
    def _validate_required_when_enabled(self) -> "SmsSettingsIn":
        """در حالت فعال، شماره فرستنده و (برای حالت pattern) کد الگو را الزامی می‌کند."""
        if self.enabled:
            if not self.from_number:
                raise ValueError("برای فعال‌کردن پیامک، شماره فرستنده الزامی است")
            if self.sending_type == SmsSendingType.pattern and not self.pattern_code:
                raise ValueError("برای حالت الگو (Pattern)، کد الگو الزامی است")
        return self


class SmsSettingsOut(BaseModel):
    """خروجی GET/PUT /system/sms-settings؛ به‌جای خود کلید فقط has_api_key برمی‌گردد."""
    enabled: bool
    has_api_key: bool
    from_number: str | None
    sending_type: SmsSendingType
    pattern_code: str | None
    webservice_message_template: str | None


class SmsTestSendIn(BaseModel):
    """ورودی POST /system/sms-settings/test (شماره موبایل مقصد پیامک آزمایشی)."""
    to_mobile: str = Field(min_length=1)
