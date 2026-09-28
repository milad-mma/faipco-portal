"""
مدل‌های اپ اندروید (docs/android-app.md):
- MobileDevice: گوشی متصل به حساب کاربر؛ توکن دستگاه (فقط هش)، وضعیت دسترسی‌ها و موتور Geofencing.
- DevicePairingCode: کد یک‌بارمصرف اتصال گوشی (پرتال داخل اپ ← بخش بومی اپ).
- GeofenceEvent: هر رویداد ورود/خروج که اپ فرستاده، با نتیجه‌ی پردازش (ثبت، تکراری، جعلی، ...).
- MobileAppExemption: پرسنل معاف از پیش‌نیاز «اپ اندروید با دسترسی موقعیت».
- MobileAppRelease: فایل‌های APK بارگذاری‌شده برای دانلود از پرتال.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class MobileDevice(Base):
    """یک گوشی متصل (جدول mobile_devices)."""
    __tablename__ = "mobile_devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    device_uid: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # شناسه‌ی تصادفی نصب اپ
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)  # SHA-256 توکن دستگاه

    manufacturer: Mapped[str | None] = mapped_column(String(60), nullable=True)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sdk_int: Mapped[int | None] = mapped_column(Integer, nullable=True)
    app_version_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    app_version_name: Mapped[str | None] = mapped_column(String(30), nullable=True)

    has_gms: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # سرویس‌های گوگل دارد؟
    geofence_engine: Mapped[str | None] = mapped_column(String(20), nullable=True)  # gms | platform
    perm_fine_location: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    perm_background_location: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    perm_notifications: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    battery_unrestricted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    location_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)  # GPS گوشی روشن است
    geofences_registered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    geofence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)


class DevicePairingCode(Base):
    """کد یک‌بارمصرف اتصال گوشی (جدول device_pairing_codes)؛ فقط هش ذخیره می‌شود."""
    __tablename__ = "device_pairing_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GeofenceEvent(Base):
    """رویداد ورود/خروج دریافتی از اپ (جدول geofence_events)."""
    __tablename__ = "geofence_events"
    __table_args__ = (UniqueConstraint("device_id", "client_event_id", name="uq_geofence_events_device_client"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("mobile_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), nullable=True)
    client_event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    transition: Mapped[str] = mapped_column(String(10), nullable=False)  # enter | dwell | exit
    engine: Mapped[str | None] = mapped_column(String(20), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # logged | duplicate | already_in | already_out | mock | disabled | unknown_site | no_employee
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    gps_log_id: Mapped[int | None] = mapped_column(
        ForeignKey("gps_activity_logs.id", ondelete="SET NULL"), nullable=True
    )


class MobileAppExemption(Base):
    """پرسنل معاف از پیش‌نیاز اپ اندروید (جدول mobile_app_exemptions)."""
    __tablename__ = "mobile_app_exemptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MobileAppRelease(Base):
    """یک نسخه‌ی APK (جدول mobile_app_releases)."""
    __tablename__ = "mobile_app_releases"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_code: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    version_name: Mapped[str] = mapped_column(String(30), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
