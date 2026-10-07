"""
گزارش خطاها (Migration 105؛ docs/error-logs.md).

ErrorLog: یک «گروه» خطا — همه‌ی رخدادهای یک خطای یکسان (همان بخش، همان نوع، همان متن بدون اعداد) یک ردیف با تعداد،
اولین و آخرین زمان. ErrorLogOccurrence: هر رخداد جدا (کد پیگیری، کاربر، مسیر، زمان) برای جست‌وجو با کد پیگیری.
هر دو بعد از ۳۰ روز پاک می‌شوند (error_log_service.purge_old).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    # error = خطای سرور، slow = درخواست کند، client = خطای مرورگر کاربر، android = خطای بخش بومی اپ
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # بخش: kara، sync، server، scheduler، email، sms، backup، frontend، network، android، ...
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)  # نام logger / مسیر / بخش اپ
    message: Mapped[str] = mapped_column(Text, nullable=False)  # متن خطا (آخرین رخداد)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # Traceback / Stack (آخرین رخداد)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_request: Mapped[str | None] = mapped_column(String(300), nullable=True)  # «GET /api/v1/sites»
    last_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_user_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # مرورگر، صفحه، نسخه‌ی اپ، مدت درخواست
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ErrorLogOccurrence(Base):
    __tablename__ = "error_log_occurrences"

    id: Mapped[int] = mapped_column(primary_key=True)
    error_id: Mapped[int] = mapped_column(ForeignKey("error_logs.id", ondelete="CASCADE"), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    request_id: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)  # کد پیگیری
    request: Mapped[str | None] = mapped_column(String(300), nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
