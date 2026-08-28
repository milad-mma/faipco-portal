"""Schema های مربوط به «حضور مبتنی بر موقعیت مکانی» و «ثبت ورود/خروج آزمایشی»."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class GpsPositionIn(BaseModel):
    latitude: float
    longitude: float
    accuracy_meters: float | None = None
    site_id: int | None = None  # اگر مشخص نشود، نزدیک‌ترین سایت دارای موقعیت GPS در نظر گرفته می‌شود


class GpsActivityLogOut(BaseModel):
    id: int
    log_type: str
    latitude: float | None
    longitude: float | None
    accuracy_meters: float | None
    matched_site_id: int | None
    distance_meters: float | None
    is_within_geofence: bool
    is_manual: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class GpsActivityLogAdminOut(GpsActivityLogOut):
    """همان اطلاعات، به‌علاوه هویت پرسنل و نام سایت — فقط برای گزارش Admin."""

    employee_id: int
    employee_name: str
    personnel_code: str
    matched_site_name: str | None = None


class GpsActivityLogPageOut(BaseModel):
    items: list[GpsActivityLogAdminOut]
    total: int
    year: int
    month: int


class MyClockLogsOut(BaseModel):
    items: list[GpsActivityLogOut]
    year: int
    month: int


class GpsManualLogIn(BaseModel):
    """افزودن دستی یک رکورد ورود/خروج توسط Admin/hr-manager — بدون مختصات
    GPS واقعی (چون خودِ پرسنل آنجا نبوده که ثبت کند)."""

    employee_id: int
    log_type: str  # "check_in" یا "check_out"
    created_at: datetime
    site_id: int | None = None


class GpsLogUpdateIn(BaseModel):
    """ویرایش دستی یک رکورد موجود — هر فیلد اختیاری است (فقط همان‌هایی که
    داده شوند تغییر می‌کنند)."""

    log_type: str | None = None
    created_at: datetime | None = None
    site_id: int | None = None


class PresenceSessionAdminOut(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    personnel_code: str
    connected_at: datetime
    disconnected_at: datetime | None
    duration_seconds: int | None
    is_online_now: bool
    matched_site_name: str | None
    last_distance_meters: float | None
    is_within_geofence: bool | None


class PresenceSessionPageOut(BaseModel):
    items: list[PresenceSessionAdminOut]
    total: int
