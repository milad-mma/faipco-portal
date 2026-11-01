"""
مدل‌های اتوماسیون اداری — فاز ۱: فایل، تنظیمات پیوست هر سایت و ثبت وقایع (Migration 131).
طراحی کامل: docs/office-automation-spec.md (بخش ۳.۶، ۳.۹، ۶.۵، ۱۱)؛ پیاده‌سازی: docs/office-automation.md.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin


class OaFile(Base, TimestampMixin):
    """
    فایل ذخیره‌شده بیرون از دیتابیس (Storage خصوصی، write-once)؛ متادیتا و هش این‌جا.
    status چرخه‌ی ۶.۵ (uploading → rejected | scanning → clean | infected | scan_pending)؛ state: temp تا وقتی به
    نسخه‌ی ثبت‌شده/امضا/قالب وصل نشده، سپس permanent (فقط clean).
    """

    __tablename__ = "oa_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), nullable=True, index=True)
    storage_key: Mapped[str | None] = mapped_column(String(255), nullable=True)  # نسبی؛ None = محتوا حذف شد (rejected)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    detected_format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, default="attachment")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="uploading", index=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="temp", index=True)
    reject_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    scan_result: Mapped[str | None] = mapped_column(String(255), nullable=True)  # نام بدافزار یا خطای اسکنر
    scan_db_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    scan_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OaAttachmentSettings(Base, TimestampMixin):
    """تعداد، حجم و فرمت مجاز پیوست‌ها برای یک سایت؛ از پرتال (automation.settings همان سایت) — بخش ۱۱."""

    __tablename__ = "oa_attachment_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, unique=True)
    letter_max_files: Mapped[int] = mapped_column(Integer, nullable=False)
    letter_max_file_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    letter_max_total_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    action_max_files: Mapped[int] = mapped_column(Integer, nullable=False)
    action_max_file_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    action_max_total_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    letter_all_max_total_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    allowed_formats: Mapped[list] = mapped_column(JSON, nullable=False)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class OaAuditEvent(Base):
    """ثبت وقایع (فقط افزودنی؛ بدون مسیر ویرایش/حذف در API و رابط) — بخش ۳.۹."""

    __tablename__ = "oa_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    letter_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # FK در فاز ۳الف
    site_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    entity: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    on_behalf_of: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
