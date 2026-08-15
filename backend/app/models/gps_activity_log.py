"""
مدل GpsActivityLog — هم «حضور دوره‌ای» (وقتی اپ باز است، هر چند دقیقه یک‌بار
چک می‌شود آیا پرسنل داخل محدوده سایت است) هم «ثبت ورود/خروج آزمایشی» (اقدام
صریح خودِ پرسنل) را با یک جدول مشترک ثبت می‌کند — log_type تفاوت را مشخص می‌کند.

⚠️ این قابلیت آزمایشی است. ثبت ورود/خروج رسمی باید از طریق دستگاه‌های
تعبیه‌شده در کارخانه انجام شود؛ این فقط یک لاگ مکمل دیجیتال است.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class GpsLogType(str, enum.Enum):
    presence = "presence"  # حضور دوره‌ای — وقتی اپ باز است
    check_in = "check_in"  # ثبت ورود آزمایشی
    check_out = "check_out"  # ثبت خروج آزمایشی


class GpsActivityLog(Base):
    __tablename__ = "gps_activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    log_type: Mapped[GpsLogType] = mapped_column(Enum(GpsLogType, name="gps_log_type_enum"), nullable=False)

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    # شعاع اطمینان GPS به متر (هرچه کمتر، دقیق‌تر) — از مرورگر گرفته می‌شود؛
    # ممکن است خالی باشد اگر مرورگر گزارش نداد
    accuracy_meters: Mapped[float | None] = mapped_column(Float, nullable=True)

    matched_site_id: Mapped[int | None] = mapped_column(
        ForeignKey("sites.id", ondelete="SET NULL"), nullable=True
    )
    distance_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_within_geofence: Mapped[bool] = mapped_column(Boolean, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
