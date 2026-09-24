"""
Schema های مربوط به تنظیمات کلی سیستم (پنل Admin → System).
شامل محدودیت IP، پیام صفحه مسدودی IP، و تنظیمات برندینگ (عنوان‌ها، جای‌های نمایش و آیکون PWA)
که در endpoint های app/api/v1/endpoints/system.py استفاده می‌شوند.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class IpAllowlistStateOut(BaseModel):
    """پاسخ GET/PUT /system/ip-allowlist: وضعیت کامل محدودیت IP — متن ویرایش‌پذیر
    (هر رنج در یک خط) و کلید فعال/غیرفعال، مستقل از هم."""

    enabled: bool
    text: str  # هر CIDR در یک خط، مرتب‌شده
    count: int  # تعداد رنج‌های معتبر فعلی (برای نمایش سریع در پنل)


class IpAllowlistStateIn(BaseModel):
    """بدنه PUT /system/ip-allowlist: ذخیره کامل — کل فهرست فعلی (متن ویرایش‌شده توسط کاربر) جایگزین همان
    چیزی می‌شود که در دیتابیس بود؛ خط‌های خالی/نامعتبر نادیده گرفته می‌شوند."""

    enabled: bool
    text: str


class IpBlockedMessageIn(BaseModel):
    """بدنه PUT /system/ip-blocked-message: متن نمایش‌داده‌شده به IP مسدود."""

    message: str


class IpBlockedMessageOut(BaseModel):
    """پاسخ GET/PUT /system/ip-blocked-message."""

    message: str


class BrandingOut(BaseModel):
    """پاسخ همه endpoint های /system/branding: عنوان‌ها، وضعیت لوگوهای سفارشی و تنظیمات هر جای نمایش."""

    browser_title: str
    manifest_name: str
    manifest_short_name: str
    manifest_description: str
    splash_title: str
    splash_subtitle: str
    login_title: str
    login_subtitle: str
    sidebar_title: str
    profile_title: str
    profile_subtitle: str
    auth_title: str
    auth_subtitle: str
    has_custom_app_logo: bool
    has_custom_app_logo_small: bool
    has_custom_pwa_icon: bool
    has_custom_favicon: bool
    has_custom_surface_splash: bool = False
    has_custom_surface_login: bool = False
    has_custom_surface_auth: bool = False
    has_custom_surface_sidebar: bool = False
    has_custom_surface_profile: bool = False
    # تنظیمات به تفکیک جای نمایش (branding_surfaces.py) + آیکون PWA
    surfaces: dict[str, dict]
    pwa_icon: dict


class BrandingSurfaceIn(BaseModel):
    """بدنه PUT /system/branding/surfaces/{surface}: فقط کلیدهای ارسالی ذخیره می‌شوند."""

    values: dict


class PwaIconSettingsIn(BaseModel):
    """بدنه PUT /system/branding/pwa-icon: تنظیمات تولید آیکون PWA."""

    values: dict


class BrandingIn(BaseModel):
    """
    بدنه PUT /system/branding: عنوان‌ها و متن‌های برند.
    فیلد خالی/None یعنی «به مقدار پیش‌فرض برگرد» — نه اینکه خالی ذخیره شود.
    """

    browser_title: str | None = Field(default=None, max_length=100)
    manifest_name: str | None = Field(default=None, max_length=45)  # نام اپ نصب‌شده (PWA name)
    manifest_short_name: str | None = Field(default=None, max_length=30)  # محدودیت PWA برای short_name
    manifest_description: str | None = Field(default=None, max_length=200)
    splash_title: str | None = Field(default=None, max_length=100)
    splash_subtitle: str | None = Field(default=None, max_length=100)
    login_title: str | None = Field(default=None, max_length=100)
    login_subtitle: str | None = Field(default=None, max_length=100)
    sidebar_title: str | None = Field(default=None, max_length=50)
    profile_title: str | None = Field(default=None, max_length=100)
    profile_subtitle: str | None = Field(default=None, max_length=100)
    auth_title: str | None = Field(default=None, max_length=100)
    auth_subtitle: str | None = Field(default=None, max_length=100)
