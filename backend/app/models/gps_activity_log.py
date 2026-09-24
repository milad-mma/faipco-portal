"""
مدل GpsActivityLog — هم «حضور دوره‌ای» (وقتی اپ باز است، هر چند دقیقه یک‌بار
چک می‌شود آیا پرسنل داخل محدوده سایت است) هم «ثبت ورود/خروج آزمایشی» (اقدام
صریح خودِ پرسنل) را با یک جدول مشترک ثبت می‌کند — log_type تفاوت را مشخص می‌کند.

این قابلیت آزمایشی است؛ ثبت ورود/خروج رسمی با دستگاه‌های حضور و غیاب کارخانه
انجام می‌شود و این جدول فقط یک لاگ مکمل دیجیتال است.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class GpsLogType(str, enum.Enum):
    """نوع رکورد لاگ GPS."""
    presence = "presence"  # حضور دوره‌ای — وقتی اپ باز است
    check_in = "check_in"  # ثبت ورود آزمایشی
    check_out = "check_out"  # ثبت خروج آزمایشی


class GpsActivityLog(Base):
    """یک رکورد موقعیت پرسنل همراه با سایت منطبق، فاصله و نتیجه بررسی محدوده (Geofence)."""
    __tablename__ = "gps_activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    log_type: Mapped[GpsLogType] = mapped_column(Enum(GpsLogType, name="gps_log_type_enum"), nullable=False)

    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    # شعاع اطمینان GPS به متر (هرچه کمتر، دقیق‌تر) — از مرورگر گرفته می‌شود؛
    # ممکن است خالی باشد اگر مرورگر گزارش نداد
    accuracy_meters: Mapped[float | None] = mapped_column(Float, nullable=True)

    # نزدیک‌ترین سایت به موقعیت ثبت‌شده
    matched_site_id: Mapped[int | None] = mapped_column(
        ForeignKey("sites.id", ondelete="SET NULL"), nullable=True
    )
    distance_meters: Mapped[float | None] = mapped_column(Float, nullable=True)  # فاصله تا سایت منطبق به متر
    is_within_geofence: Mapped[bool] = mapped_column(Boolean, nullable=False)  # آیا داخل شعاع مجاز سایت بوده

    # True اگر Admin/hr-manager دستی این رکورد را ثبت/ویرایش کرده باشد (نه
    # خودِ پرسنل با GPS واقعی) — در گزارش با یک ستاره کنار زمان مشخص می‌شود.
    # این رکوردها latitude/longitude ندارند، به همین دلیل آن دو ستون Nullable هستند.
    is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
