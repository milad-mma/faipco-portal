"""
Schema های مربوط به «پیام‌های تبریک تولد».
شامل ورودی/خروجی متن‌های آماده تبریک، ساعت ارسال روزانه و فعال/غیرفعال بودن ارسال
(مورد استفاده در endpointهای /hr/birthday-*).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BirthdayTemplateIn(BaseModel):
    """ورودی POST /hr/birthday-templates برای افزودن متن تبریک جدید."""
    text: str


class BirthdayTemplateOut(BaseModel):
    """خروجی فهرست و ایجاد متن‌های تبریک در /hr/birthday-templates."""
    id: int
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BirthdaySendTimeIn(BaseModel):
    """ورودی PUT /hr/birthday-send-time (ساعت و دقیقه ارسال روزانه)."""
    hour: int
    minute: int


class BirthdaySendTimeOut(BaseModel):
    """خروجی GET/PUT /hr/birthday-send-time."""
    hour: int
    minute: int


class BirthdayEnabledIn(BaseModel):
    """ورودی PUT /hr/birthday-enabled برای روشن/خاموش کردن ارسال خودکار."""
    enabled: bool


class BirthdayEnabledOut(BaseModel):
    """خروجی GET/PUT /hr/birthday-enabled."""
    enabled: bool
