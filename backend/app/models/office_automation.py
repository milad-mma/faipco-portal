"""
مدل‌های اتوماسیون اداری — فاز ۱: فایل، تنظیمات پیوست هر سایت و ثبت وقایع (Migration 131).
طراحی کامل: docs/office-automation-spec.md (بخش ۳.۶، ۳.۹، ۶.۵، ۱۱)؛ پیاده‌سازی: docs/office-automation.md.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
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


# ---------- فاز ۲: قالب و پیش‌نویس نامه (Migration 134) ----------


class OaTemplate(Base, TimestampMixin):
    """قالب (سربرگ/پابرگ/حاشیه) یک سایت؛ نسخه‌دار — هر ذخیره یک OaTemplateVersion تازه است (بخش ۸.۲)."""

    __tablename__ = "oa_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    default_paper_size: Mapped[str] = mapped_column(String(4), nullable=False, default="A4")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class OaTemplateVersion(Base):
    """یک نسخه‌ی تغییرناپذیر از چیدمان قالب برای A4 و A5 (layouts: {"A4": {...}, "A5": {...}})."""

    __tablename__ = "oa_template_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("oa_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    layouts: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OaLetter(Base, TimestampMixin):
    """
    نامه. فاز ۲ فقط پیش‌نویس شخصی (status=draft؛ فقط ایجادکننده می‌بیند)؛ ارسال، گیرنده و دسترسی از فاز ۳الف.
    row_version برای قفل خوش‌بینانه (ذخیره‌ی هم‌زمان از دو تب → 409).
    """

    __tablename__ = "oa_letters"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="RESTRICT"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(12), nullable=False, default="internal")
    confidentiality: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    urgency: Mapped[str] = mapped_column(String(12), nullable=False, default="normal")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)
    subject: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    creator_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    discarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OaLetterVersion(Base, TimestampMixin):
    """نسخه‌ی نامه؛ status: editing (فاز ۲) ← submitted/approved/superseded/frozen از فاز ۳ب."""

    __tablename__ = "oa_letter_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    letter_id: Mapped[int] = mapped_column(ForeignKey("oa_letters.id", ondelete="CASCADE"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    body_html: Mapped[str] = mapped_column(Text, nullable=False, default="")
    paper_size: Mapped[str] = mapped_column(String(4), nullable=False, default="A4")
    template_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("oa_template_versions.id", ondelete="RESTRICT"), nullable=True
    )
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="editing")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
