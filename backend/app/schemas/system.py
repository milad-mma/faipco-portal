"""Schema های مربوط به تنظیمات کلی سیستم (پنل Admin → System)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class IpAllowlistStateOut(BaseModel):
    """وضعیت کامل قابلیت محدودیت IP — یک متن ویرایش‌پذیر (هر رنج در یک خط) +
    کلید فعال/غیرفعال، مستقل از هم."""

    enabled: bool
    text: str  # هر CIDR در یک خط، مرتب‌شده
    count: int  # تعداد رنج‌های معتبر فعلی (برای نمایش سریع در پنل)


class IpAllowlistStateIn(BaseModel):
    """ذخیره کامل — کل فهرست فعلی (متن ویرایش‌شده توسط کاربر) جایگزین همان
    چیزی می‌شود که در دیتابیس بود؛ خط‌های خالی/نامعتبر نادیده گرفته می‌شوند."""

    enabled: bool
    text: str


class IpBlockedMessageIn(BaseModel):
    message: str


class IpBlockedMessageOut(BaseModel):
    message: str


class BrandingOut(BaseModel):
    name: str
    short_name: str
    description: str
    has_custom_logo: bool


class BrandingIn(BaseModel):
    """
    فیلد خالی/None یعنی «به مقدار پیش‌فرض برگرد» — نه اینکه خالی ذخیره شود.
    """

    name: str | None = Field(default=None, max_length=100)
    short_name: str | None = Field(default=None, max_length=30)  # محدودیت PWA برای short_name
    description: str | None = Field(default=None, max_length=200)
