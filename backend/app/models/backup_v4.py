"""
بکاپ نسخه‌ی ۴ — کلیدهای رمزنگاری و تاریخچه‌ی اجرا (Migration 132؛ docs/backup.md).
تنظیمات زمان‌بندی و مقصدها همان backup_settings قبلی است.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class BackupKey(Base):
    """
    کلید age برای رمزنگاری بکاپ. mode: external (فقط کلید عمومی این‌جاست؛ کلید خصوصی نزد نگهدارنده) یا server_protected
    (کلید خصوصی رمزنگاری‌شده با secret سرور). کلید فعال = جدیدترین بدون retired_at. کلید قدیمی حذف نمی‌شود.
    """

    __tablename__ = "backup_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    key_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)  # اثرانگشت کلید عمومی
    mode: Mapped[str] = mapped_column(String(24), nullable=False)
    public_key: Mapped[str] = mapped_column(String(128), nullable=False)
    encrypted_private_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BackupRun(Base):
    """یک اجرای بکاپ (دستی/زمان‌بندی‌شده/دانلود) و نتیجه‌ی هر مقصد."""

    __tablename__ = "backup_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    set_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(16), nullable=False)  # manual / scheduled / download
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")  # running/success/partial/failed
    filename: Mapped[str | None] = mapped_column(String(128), nullable=True)
    key_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    file_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    files_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    manifest_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    consistency_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    destinations: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"smb": {"ok": bool, "message": str}, ...}
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
