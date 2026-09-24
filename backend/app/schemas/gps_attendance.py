"""
Schema های Pydantic مربوط به «حضور مبتنی بر موقعیت مکانی» (GPS).

شامل مدل ورودی ثبت موقعیت، مدل‌های خروجی لاگ ورود/خروج (برای پرسنل و برای
گزارش Admin)، مدل‌های افزودن/ویرایش دستی لاگ توسط Admin و مدل‌های خروجی
نشست‌های حضور آنلاین (Presence Session).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class GpsPositionIn(BaseModel):
    """ورودی ثبت ورود/خروج با GPS: مختصات فعلی دستگاه پرسنل و سایت اختیاری."""
    latitude: float
    longitude: float
    accuracy_meters: float | None = None
    site_id: int | None = None  # اگر مشخص نشود، نزدیک‌ترین سایت دارای موقعیت GPS در نظر گرفته می‌شود


class GpsActivityLogOut(BaseModel):
    """یک رکورد لاگ ورود/خروج آن‌طور که به خودِ پرسنل نمایش داده می‌شود (بدون هویت پرسنل)."""
    id: int
    log_type: str
    latitude: float | None
    longitude: float | None
    accuracy_meters: float | None
    matched_site_id: int | None
    distance_meters: float | None
    is_within_geofence: bool  # آیا داخل شعاع مجاز سایت بوده
    is_manual: bool  # ثبت دستی توسط Admin (بدون مختصات واقعی)
    created_at: datetime

    model_config = {"from_attributes": True}  # ساخت مستقیم از شیء ORM


class GpsActivityLogAdminOut(GpsActivityLogOut):
    """همان اطلاعات، به‌علاوه هویت پرسنل و نام سایت — فقط برای گزارش Admin."""

    employee_id: int
    employee_name: str
    personnel_code: str
    matched_site_name: str | None = None


class GpsActivityLogPageOut(BaseModel):
    """یک صفحه از لاگ‌های GPS برای گزارش Admin به‌همراه تعداد کل و ماه گزارش."""
    items: list[GpsActivityLogAdminOut]
    total: int
    year: int
    month: int


class MyClockLogsOut(BaseModel):
    """لاگ‌های ورود/خروج خودِ پرسنل در یک ماه شمسی."""
    items: list[GpsActivityLogOut]
    year: int
    month: int


class GpsManualLogIn(BaseModel):
    """افزودن دستی یک رکورد ورود/خروج توسط Admin/hr-manager — بدون مختصات
    GPS واقعی (چون خودِ پرسنل آنجا نبوده که ثبت کند)."""

    employee_id: int
    log_type: str  # "check_in" یا "check_out"
    created_at: datetime  # زمان واقعی ورود/خروج که Admin اعلام می‌کند
    site_id: int | None = None


class GpsLogUpdateIn(BaseModel):
    """ویرایش دستی یک رکورد موجود — هر فیلد اختیاری است (فقط همان‌هایی که
    داده شوند تغییر می‌کنند)."""

    log_type: str | None = None
    created_at: datetime | None = None
    site_id: int | None = None


class PresenceSessionAdminOut(BaseModel):
    """یک نشست حضور آنلاین (اتصال تا قطع اتصال) یک پرسنل برای گزارش Admin."""
    id: int
    employee_id: int
    employee_name: str
    personnel_code: str
    connected_at: datetime
    disconnected_at: datetime | None
    duration_seconds: int | None  # None یعنی نشست هنوز باز است
    is_online_now: bool
    matched_site_name: str | None
    last_distance_meters: float | None
    is_within_geofence: bool | None


class PresenceSessionPageOut(BaseModel):
    """یک صفحه از نشست‌های حضور آنلاین به‌همراه تعداد کل."""
    items: list[PresenceSessionAdminOut]
    total: int
