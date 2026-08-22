"""
شمارنده تجمعی استفاده از پرتال — یک ردیف به‌ازای هر (تاریخ، ساعت) که فقط
یک عدد (تعداد درخواست) نگه می‌دارد؛ نه لاگ تک‌تک درخواست‌ها (که برای این
منظور غیرضروری و پرحجم می‌شد). برای نمودار «میزان استفاده» در پنل Admin.
"""
from __future__ import annotations

from datetime import date as date_type

from sqlalchemy import Date, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class UsageStat(Base):
    __tablename__ = "usage_stats"
    __table_args__ = (UniqueConstraint("date", "hour", name="uq_usage_stats_date_hour"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date_type] = mapped_column(Date, nullable=False, index=True)
    hour: Mapped[int] = mapped_column(Integer, nullable=False)  # ۰ تا ۲۳، به وقت ایران
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
