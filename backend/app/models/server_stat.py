"""
نمونه‌برداری دوره‌ای از مصرف منابع خودِ سرور (CPU، RAM، فضای دیسک) — برای
نمودار «مصرف سرور» در پنل Admin. هر ردیف یک لحظه مشخص است (نه تجمعی مثل
UsageStat)، چون این‌ها مقادیر لحظه‌ای هستند نه شمارنده.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ServerStat(Base):
    __tablename__ = "server_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    cpu_percent: Mapped[float] = mapped_column(Float, nullable=False)

    ram_percent: Mapped[float] = mapped_column(Float, nullable=False)
    ram_used_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    ram_total_mb: Mapped[int] = mapped_column(Integer, nullable=False)

    disk_percent: Mapped[float] = mapped_column(Float, nullable=False)
    disk_used_gb: Mapped[float] = mapped_column(Float, nullable=False)
    disk_total_gb: Mapped[float] = mapped_column(Float, nullable=False)
