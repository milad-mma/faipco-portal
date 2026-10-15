"""
نشست دستگاه (Migration 115؛ docs/login-security.md): هر ورود موفق یک ردیف با sid یکتا می‌سازد و همان sid داخل
Access/Refresh Token می‌نشیند. هر درخواست، نشست را بررسی می‌کند (باطل‌نشده) و «آخرین فعالیت» را تازه می‌کند.
خروج فقط همین نشست را باطل می‌کند؛ دستگاه‌های دیگر وارد می‌مانند.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (Index("ix_user_sessions_user_active", "user_id", "revoked_at", "last_seen_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    device_label: Mapped[str | None] = mapped_column(String(120), nullable=True)  # مثل «Chrome روی Windows»
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    client_app: Mapped[str | None] = mapped_column(String(20), nullable=True)  # android = پرتال داخل اپ اندروید
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # logout (خودِ دستگاه) | remote (کاربر از دستگاه دیگر) | admin | limit (ورود دستگاه جدید) | password | deactivated
    revoked_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)

    user: Mapped["User"] = relationship()  # noqa: F821
