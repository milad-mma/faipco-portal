"""
مدل PresenceSession — مانیتورینگ زنده «آنلاین‌بودن» پرسنل با WebSocket،
دقیقاً مثل نشانگر آنلاین یک سیستم چت: لحظه وصل‌شدن = شروع Session، لحظه
قطع‌شدن (بستن تب، قطعی شبکه، هرچیز دیگر) = پایان Session، و duration_seconds
دقیقاً محاسبه‌شده است — نه یک لاگ نقطه‌ای دوره‌ای مثل GpsActivityLog.

⚠️ فقط تا زمانی کار می‌کند که اپ/تب باز و WebSocket برقرار باشد؛ وقتی اپ
کاملاً بسته شود، همان لحظه به‌عنوان «پایان Session» ثبت می‌شود — نمی‌تواند
چیزی را برای زمانی که واقعاً بسته بوده رصد کند (محدودیت پلتفرم مرورگر است).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PresenceSession(Base):
    __tablename__ = "presence_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )

    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # تا وقتی NULL است یعنی همین الان آنلاین است
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    last_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_accuracy_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    matched_site_id: Mapped[int | None] = mapped_column(
        ForeignKey("sites.id", ondelete="SET NULL"), nullable=True
    )
    last_distance_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_within_geofence: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
