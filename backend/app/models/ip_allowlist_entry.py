"""
مدل IpAllowlistEntry — رنج‌های IP مجاز برای ورود (مثلاً فقط شبکه دفتر
مرکزی). اگر این جدول کاملاً خالی باشد، هیچ محدودیتی اعمال نمی‌شود — منطق
واقعی چک‌کردن در app/core/ip_allowlist.py است.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class IpAllowlistEntry(Base):
    __tablename__ = "ip_allowlist_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    # فرمت CIDR — هم یک IP تکی («203.0.113.5/32») هم یک رنج («192.168.1.0/24») را می‌پذیرد
    cidr: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
