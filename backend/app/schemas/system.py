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
    browser_title: str
    manifest_short_name: str
    manifest_description: str
    splash_title: str
    splash_subtitle: str
    login_title: str
    login_subtitle: str
    sidebar_title: str
    profile_title: str
    profile_subtitle: str
    has_custom_app_logo: bool
    has_custom_pwa_icon: bool
    has_custom_favicon: bool


class BrandingIn(BaseModel):
    """
    فیلد خالی/None یعنی «به مقدار پیش‌فرض برگرد» — نه اینکه خالی ذخیره شود.
    """

    browser_title: str | None = Field(default=None, max_length=100)
    manifest_short_name: str | None = Field(default=None, max_length=30)  # محدودیت PWA برای short_name
    manifest_description: str | None = Field(default=None, max_length=200)
    splash_title: str | None = Field(default=None, max_length=100)
    splash_subtitle: str | None = Field(default=None, max_length=100)
    login_title: str | None = Field(default=None, max_length=100)
    login_subtitle: str | None = Field(default=None, max_length=100)
    sidebar_title: str | None = Field(default=None, max_length=50)
    profile_title: str | None = Field(default=None, max_length=100)
    profile_subtitle: str | None = Field(default=None, max_length=100)
