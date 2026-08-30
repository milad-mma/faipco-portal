"""
مدل‌های Site (کارخانه/شعبه) و SiteConnection (اطلاعات اتصال به دیتابیس آن Site).

نکته امنیتی: فیلد password_encrypted هرگز رمزگشایی‌شده در دیتابیس ذخیره نمی‌شود.
رمزنگاری/رمزگشایی آن فقط از طریق app.core.security.encrypt_secret/decrypt_secret انجام می‌شود.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class DbType(str, enum.Enum):
    mssql = "mssql"
    mysql = "mysql"
    postgresql = "postgresql"


class SyncStatus(str, enum.Enum):
    never = "never"
    success = "success"
    failed = "failed"
    partial = "partial"
    running = "running"


class Site(Base, TimestampMixin):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # موقعیت GPS + شعاع مجاز (اختیاری) — اگر تنظیم نشده باشد (NULL)، هیچ
    # محدودیت مکانی برای پرسنل این سایت اعمال نمی‌شود. برای «حضور دوره‌ای»
    # و «ثبت ورود/خروج آزمایشی» استفاده می‌شود.
    gps_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_radius_meters: Mapped[int | None] = mapped_column(Integer, nullable=True)

    connection: Mapped["SiteConnection"] = relationship(
        back_populates="site", cascade="all, delete-orphan", uselist=False
    )


class SiteConnection(Base, TimestampMixin):
    """هر Site دقیقاً یک اتصال دیتابیس منبع دارد (رابطه یک‌به‌یک)."""

    __tablename__ = "site_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    db_type: Mapped[DbType] = mapped_column(Enum(DbType, name="db_type_enum"), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    database_name: Mapped[str] = mapped_column(String(128), nullable=False)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus, name="sync_status_enum"), default=SyncStatus.never, nullable=False
    )
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    site: Mapped["Site"] = relationship(back_populates="connection")


class AttendanceMapping(Base, TimestampMixin):
    """
    نگاشت ستون‌های دیتابیس خام تردد هر Site به فیلدهای استاندارد «گزارش
    تردد ماهانه» — دقیقاً همان الگوی EmployeeMapping (app/models/employee.py):
    چون نرم‌افزارهای مختلف حضور و غیاب دستگاهی، نام جدول/ستون‌های متفاوتی
    دارند، این‌ها هاردکد نیستند و از پنل «تنظیمات سایت» قابل‌تنظیم‌اند.

    وجود یا نبود این رکورد برای یک Site، خودِ «آیا گزارش تردد ماهانه برای
    این سایت فعال است؟» را هم مشخص می‌کند — یک فلگ boolean جدا لازم نیست.
    هر Site حداکثر یک Mapping تردد دارد (site_id یکتا).
    """

    __tablename__ = "attendance_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    table_name: Mapped[str] = mapped_column(String(128), nullable=False)
    personnel_code_column: Mapped[str] = mapped_column(String(128), nullable=False)
    date_column: Mapped[str] = mapped_column(String(128), nullable=False)
    time_column: Mapped[str] = mapped_column(String(128), nullable=False)

    # نگاشت اختیاری جدول تقویم/تعطیلات — کاملاً مستقل از جدول تردد بالا.
    # اگر calendar_table_name خالی باشد، این قابلیت برای این سایت غیرفعال
    # است (گزارش تردد بدون رنگ‌آمیزی تعطیلات، دقیقاً مثل قبل کار می‌کند).
    # ساختار مورد انتظار: یک ردیف به‌ازای هر (سال، ماه شمسی)، با ستون‌های
    # روز شماره‌گذاری‌شده (مثلاً D1 تا D31) که هرکدام یا صفر (روز عادی)
    # یا یک عدد غیرصفر (تعطیل) هستند.
    calendar_table_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    calendar_year_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    calendar_month_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # پیشوند ستون‌های روز — مثلاً "D" یعنی ستون‌ها D1، D2، ...، D31 هستند
    calendar_day_column_prefix: Mapped[str | None] = mapped_column(String(32), nullable=True)
