"""
مدل‌های اتوماسیون اداری — فاز ۱: فایل، تنظیمات پیوست هر سایت و ثبت وقایع (Migration 131).
طراحی کامل: docs/office-automation-spec.md (بخش ۳.۶، ۳.۹، ۶.۵، ۱۱)؛ پیاده‌سازی: docs/office-automation.md.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
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


# ---------- فاز ۲: قالب و پیش‌نویس نامه (Migration 136) ----------


class OaTemplate(Base, TimestampMixin):
    """قالب (سربرگ/پابرگ/حاشیه) یک سایت؛ نسخه‌دار — هر ذخیره یک OaTemplateVersion تازه است (بخش ۸.۲)."""

    __tablename__ = "oa_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    # قالب برای همه‌ی سایت‌ها یکسان است (ستون site_id در Migration 140 حذف شد)
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
    # فاز ۳الف (Migration 137): فرستنده و زمان ارسال
    sender_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sender_name_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sender_title_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Migration 138: «نیاز به اقدام گیرنده» — بدون تیک، گیرنده‌ی اصلی فقط می‌خواند (مسئولیت ساخته نمی‌شود)
    requires_action: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    action_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Migration 142: منشی برای مدیر — نامه به نام این شخص (مدیر) ارسال می‌شود؛ creator_employee_id = منشی
    principal_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Migration 143: شماره و تاریخ رسمی (صدور در ثبت نهایی = ارسال نامه‌ی داخلی)
    secretariat_id: Mapped[int | None] = mapped_column(ForeignKey("oa_secretariats.id", ondelete="RESTRICT"), nullable=True)
    official_number: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Migration 144: امضای شخصی فرستنده (چک‌باکس «امضا شود»؛ هیچ‌کس به نام دیگری امضا نمی‌کند)
    sign_on_send: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    signature_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("oa_signature_versions.id", ondelete="RESTRICT"), nullable=True
    )
    signer_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    signer_name_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    signer_title_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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


# ---------- فاز ۳الف: گیرنده، دسترسی، مسئولیت، هامش، پیوست (Migration 137) ----------


class OaRecipient(Base, TimestampMixin):
    """گیرنده‌ی اصلی (to) یا رونوشت (cc) — همیشه شخص؛ نام/سمت/واحد لحظه‌ی انتخاب ذخیره می‌شود."""

    __tablename__ = "oa_recipients"

    id: Mapped[int] = mapped_column(primary_key=True)
    letter_id: Mapped[int] = mapped_column(ForeignKey("oa_letters.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(4), nullable=False)  # to | cc
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)
    name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    title_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    department_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    selected_via: Mapped[str] = mapped_column(String(16), nullable=False, default="direct")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OaLetterAccess(Base):
    """
    دسترسی صریح یک شخص به یک نامه — تنها منبع دسترسی محتوایی (بخش ۵.۲ سند). نقش سازمانی یا مجوز ماژول رکوردی نمی‌سازد.
    source: creator | sender | recipient | cc | referral. read_at: اولین مشاهده‌ی همین شخص.
    """

    __tablename__ = "oa_letter_access"

    id: Mapped[int] = mapped_column(primary_key=True)
    letter_id: Mapped[int] = mapped_column(ForeignKey("oa_letters.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    can_act: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_refer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    granted_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    granted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class OaTask(Base, TimestampMixin):
    """مسئولیت: kind action (اقدام) | info (اطلاع)؛ origin delivery (گیرنده‌ی اصلی) | referral. درخت با parent_task_id."""

    __tablename__ = "oa_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    letter_id: Mapped[int] = mapped_column(ForeignKey("oa_letters.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_task_id: Mapped[int | None] = mapped_column(ForeignKey("oa_tasks.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    origin: Mapped[str] = mapped_column(String(12), nullable=False, default="delivery")
    assignee_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    assignee_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    assignee_title_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="open")  # open | done | cancelled
    result_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    created_by_name_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    acted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OaNote(Base, TimestampMixin):
    """هامش داخلی؛ فقط برای کسانی که به نامه دسترسی دارند؛ هرگز در چاپ رسمی نمی‌آید."""

    __tablename__ = "oa_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    letter_id: Mapped[int] = mapped_column(ForeignKey("oa_letters.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("oa_tasks.id", ondelete="SET NULL"), nullable=True)
    author_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    author_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)


class OaAttachment(Base, TimestampMixin):
    """پیوست یک نسخه‌ی نامه (فایل اتوماسیون)."""

    __tablename__ = "oa_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    letter_version_id: Mapped[int] = mapped_column(
        ForeignKey("oa_letter_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_id: Mapped[int] = mapped_column(ForeignKey("oa_files.id", ondelete="RESTRICT"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class OaNotificationLog(Base):
    """کلید یکتای هر اعلان ارسال‌شده (رویداد:نامه:شخص:…) تا در چند worker یا تلاش دوباره تکرار نشود."""

    __tablename__ = "oa_notification_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ---------- فاز ۳الف بخش دوم: رابطه‌ی نامه‌ها و تنظیمات اعلان (Migration 139) ----------


class OaLetterRelation(Base):
    """from_letter_id (نامه‌ی جدید) به to_letter_id اشاره می‌کند: فقط reply (پاسخ). دسترسی نمی‌دهد."""

    __tablename__ = "oa_letter_relations"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_letter_id: Mapped[int] = mapped_column(ForeignKey("oa_letters.id", ondelete="CASCADE"), nullable=False, index=True)
    to_letter_id: Mapped[int] = mapped_column(ForeignKey("oa_letters.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(12), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OaNotificationPref(Base):
    """رویدادهای خاموش اعلان یک پرسنل (new_letter، cc، referral)؛ نبودن ردیف = همه روشن."""

    __tablename__ = "oa_notification_prefs"

    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True)
    disabled_events: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ---------- فاز ۳الف بخش سوم: منشی و پیوست نتیجه‌ی اقدام (Migration 142) ----------


class OaSecretary(Base):
    """منشی یک مدیر: پیش‌نویس برای او تهیه و به نام او ارسال می‌کند. تعیین: خود مدیر یا دارنده‌ی automation.settings."""

    __tablename__ = "oa_secretaries"
    __table_args__ = (UniqueConstraint("principal_employee_id", "secretary_employee_id", name="uq_oa_secretary_pair"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    principal_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    secretary_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OaTaskAttachment(Base):
    """فایل پیوست هنگام ثبت نتیجه‌ی یک مسئولیت (اقدام)."""

    __tablename__ = "oa_task_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("oa_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("oa_files.id", ondelete="RESTRICT"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ---------- فاز ۳ب: دبیرخانه و شماره‌گذاری (Migration 143) ----------


class OaSecretariat(Base, TimestampMixin):
    """یک دبیرخانه برای هر سایت؛ پیشوند شماره فقط از پرتال و پس از اولین شماره قفل."""

    __tablename__ = "oa_secretariats"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="دبیرخانه")
    number_prefix: Mapped[str | None] = mapped_column(String(10), nullable=True, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class OaNumberCounter(Base):
    """شمارنده‌ی هر دبیرخانه در هر سال شمسی (قفل ردیف هنگام صدور)."""

    __tablename__ = "oa_number_counters"
    __table_args__ = (UniqueConstraint("secretariat_id", "jalali_year", name="uq_oa_counter_year"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    secretariat_id: Mapped[int] = mapped_column(ForeignKey("oa_secretariats.id", ondelete="CASCADE"), nullable=False)
    jalali_year: Mapped[int] = mapped_column(Integer, nullable=False)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class OaIssuedNumber(Base):
    """هر شماره‌ی صادرشده (یکتا)؛ void بعد از ابطال و هرگز دوباره صادر نمی‌شود."""

    __tablename__ = "oa_issued_numbers"
    __table_args__ = (UniqueConstraint("secretariat_id", "number", name="uq_oa_issued_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    secretariat_id: Mapped[int] = mapped_column(ForeignKey("oa_secretariats.id", ondelete="RESTRICT"), nullable=False)
    number: Mapped[str] = mapped_column(String(40), nullable=False)
    letter_id: Mapped[int | None] = mapped_column(ForeignKey("oa_letters.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="used")  # used | void
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OaSignatureVersion(Base):
    """
    نسخه‌ی امضای شخصی (فاز ۳ب، Migration 144). یک نسخه‌ی active برای هر نفر؛ غیرفعال‌سازی فقط آینده را متوقف می‌کند و
    فایل امضای استفاده‌شده هرگز حذف نمی‌شود.
    """

    __tablename__ = "oa_signature_versions"
    __table_args__ = (UniqueConstraint("owner_employee_id", "version_no", name="uq_oa_signature_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    file_id: Mapped[int] = mapped_column(ForeignKey("oa_files.id", ondelete="RESTRICT"), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    method: Mapped[str] = mapped_column(String(8), nullable=False)  # draw | upload
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")  # active | inactive
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivate_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
