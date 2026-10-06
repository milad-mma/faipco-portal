"""Schemaهای اپ اندروید: تنظیمات، ثبت دستگاه، گزارش وضعیت، رویدادهای Geofencing و خروجی‌های پنل."""
from __future__ import annotations

from datetime import datetime

import re

from pydantic import BaseModel, Field, field_validator


class MobileAppSettings(BaseModel):
    """تنظیمات اپ اندروید (system_settings با کلید mobile_app)."""

    auto_clock_enabled: bool = True  # ثبت خودکار ورود/خروج با Geofencing
    loitering_seconds: int = Field(default=120, ge=30, le=900)  # مکث داخل محدوده پیش از ثبت ورود (موتور گوگل)
    responsiveness_seconds: int = Field(default=180, ge=0, le=900)  # تأخیر مجاز اعلان رویداد؛ بیشتر = باتری کمتر
    repeat_guard_hours: int = Field(default=12, ge=1, le=24)  # ورود پشت ورود (یا خروج پشت خروج) در این بازه ثبت نمی‌شود
    status_stale_days: int = Field(default=3, ge=1, le=30)  # گوشی بی‌خبر بیش از این = «سالم» حساب نمی‌شود
    min_version_code: int = Field(default=0, ge=0)  # نسخه‌های قدیمی‌تر = «نیاز به به‌روزرسانی»
    # «آنلاین در محیط کار»: هر وقت گوشی داخل محدوده‌ی سایت است، آنلاین شدنش (حتی با اپ بسته) ثبت می‌شود
    online_tracking_enabled: bool = True
    # اثر انگشت SHA-256 کلید امضای APK (از خروجی GitHub Actions)؛ در /.well-known/assetlinks.json نوشته می‌شود
    # تا اپ تمام‌صفحه (بدون نوار آدرس) باز شود
    signing_sha256: str = Field(default="", max_length=200)

    @field_validator("signing_sha256")
    @classmethod
    def _check_fingerprint(cls, v: str) -> str:
        """۳۲ بایت هگز با دونقطه (AB:CD:...)؛ فاصله و حروف کوچک هم پذیرفته و استاندارد می‌شوند."""
        text = re.sub(r"\s+", "", v or "").upper()
        if not text:
            return ""
        if ":" not in text and re.fullmatch(r"[0-9A-F]{64}", text):
            text = ":".join(text[i : i + 2] for i in range(0, 64, 2))
        if not re.fullmatch(r"([0-9A-F]{2}:){31}[0-9A-F]{2}", text):
            raise ValueError("اثر انگشت SHA-256 باید ۶۴ رقم هگز (با یا بدون دونقطه) باشد")
        return text


class DeviceLinkIn(BaseModel):
    """بدنه‌ی POST /mobile/link: کد اتصال خودکار که اپ در آدرس پرتال فرستاده است."""

    link: str = Field(min_length=16, max_length=100)


class DeviceRegisterIn(BaseModel):
    """بدنه‌ی POST /mobile/devices/register (از بخش بومی اپ)."""

    code: str = Field(min_length=16, max_length=100)
    device_uid: str = Field(min_length=8, max_length=64)
    manufacturer: str | None = Field(default=None, max_length=60)
    model: str | None = Field(default=None, max_length=80)
    os_version: str | None = Field(default=None, max_length=20)
    sdk_int: int | None = None
    app_version_code: int | None = None
    app_version_name: str | None = Field(default=None, max_length=30)


class DeviceStatusIn(BaseModel):
    """بدنه‌ی POST /mobile/devices/status (از بخش بومی اپ)."""

    fine_location: bool = False
    background_location: bool = False
    notifications: bool = False
    battery_unrestricted: bool = False
    location_enabled: bool = True
    has_gms: bool | None = None
    engine: str | None = Field(default=None, max_length=20)
    geofences_registered: bool = False
    geofence_count: int = Field(default=0, ge=0, le=100)
    app_version_code: int | None = None
    app_version_name: str | None = Field(default=None, max_length=30)
    os_version: str | None = Field(default=None, max_length=20)
    sdk_int: int | None = None


class GeofenceEventIn(BaseModel):
    """یک رویداد ورود/خروج."""

    id: str = Field(min_length=8, max_length=64)  # شناسه‌ی یکتای سمت اپ (برای جلوگیری از ثبت دوباره در ارسال مجدد)
    transition: str = Field(pattern="^(enter|dwell|exit)$")
    site_id: int
    occurred_at: int  # میلی‌ثانیه از epoch (زمان گوشی؛ فقط پشتیبان وقتی کرنومتر قابل استفاده نیست)
    # «کرنومتر» گوشی (SystemClock.elapsedRealtime: میلی‌ثانیه از روشن شدن، غیرقابل تغییر توسط کاربر) لحظه‌ی رویداد
    # و شماره‌ی روشن شدن گوشی (Settings.Global.BOOT_COUNT)؛ با now_elapsed_ms ارسال، زمان واقعی با ساعت سرور حساب می‌شود
    elapsed_ms: int | None = Field(default=None, ge=0, le=10**13)
    boot_count: int | None = Field(default=None, ge=0, le=10**9)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy: float | None = Field(default=None, ge=0)
    is_mock: bool = False
    engine: str | None = Field(default=None, max_length=20)


class GeofenceEventsIn(BaseModel):
    events: list[GeofenceEventIn] = Field(max_length=100)
    # کرنومتر و شماره‌ی روشن شدن گوشی لحظه‌ی ارسال (نسخه‌های قدیمی اپ ندارند ← زمان گوشی، مثل قبل)
    now_elapsed_ms: int | None = Field(default=None, ge=0, le=10**13)
    boot_count: int | None = Field(default=None, ge=0, le=10**9)
    # ساعت گوشی لحظه‌ی ارسال؛ فقط برای تشخیص خاموش/روشن شدن در اندروید ۶ (بدون BOOT_COUNT)
    now_wall_ms: int | None = Field(default=None, ge=0, le=10**14)


class ConnectivityEventIn(BaseModel):
    """«آنلاین در محیط کار»: گوشی داخل محدوده‌ی یک سایت آنلاین است (online = تازه وصل شد، alive = هنوز وصل است)."""

    id: str = Field(min_length=8, max_length=64)
    kind: str = Field(pattern="^(online|alive)$")
    site_id: int
    network: str | None = Field(default=None, pattern="^(wifi|cellular|other)$")
    occurred_at: int
    elapsed_ms: int | None = Field(default=None, ge=0, le=10**13)
    boot_count: int | None = Field(default=None, ge=0, le=10**9)


class ConnectivityEventsIn(BaseModel):
    events: list[ConnectivityEventIn] = Field(max_length=200)
    now_elapsed_ms: int | None = Field(default=None, ge=0, le=10**13)
    boot_count: int | None = Field(default=None, ge=0, le=10**9)
    # ساعت گوشی لحظه‌ی ارسال؛ فقط برای تشخیص خاموش/روشن شدن در اندروید ۶ (بدون BOOT_COUNT)
    now_wall_ms: int | None = Field(default=None, ge=0, le=10**14)


class ExemptionIn(BaseModel):
    employee_id: int
    reason: str | None = Field(default=None, max_length=200)


class DeviceOut(BaseModel):
    """ردیف فهرست دستگاه‌ها در پنل."""

    id: int
    user_id: int
    employee_id: int | None
    employee_name: str | None
    personnel_code: str | None
    site_name: str | None
    manufacturer: str | None
    model: str | None
    os_version: str | None
    app_version_name: str | None
    app_version_code: int | None
    has_gms: bool | None
    geofence_engine: str | None
    perm_fine_location: bool
    perm_background_location: bool
    perm_notifications: bool
    battery_unrestricted: bool
    location_enabled: bool
    geofences_registered: bool
    geofence_count: int
    created_at: datetime
    status_reported_at: datetime | None
    last_event_at: datetime | None
    revoked_at: datetime | None
    healthy: bool
    issues: list[str]
