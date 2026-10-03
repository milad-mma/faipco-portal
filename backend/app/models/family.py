"""
جدول‌های ماژول «مشخصات خانوادگی» (پایه‌ی حق تاهل و حق اولاد):
- FamilyProfile: یک پرونده برای هر پرسنل (وضعیت تاهل، سرپرستی خانوار، وضعیت بررسی، داده‌ی تأییدشده)
- FamilyMember: همسر و فرزندان (پسر/دختر) پرونده
- FamilyDocument: مدارک پیوست (سند ازدواج، شناسنامه، گواهی تحصیل، ...)؛ محتوای فایل داخل دیتابیس
- FamilyChangeLog: تاریخچه‌ی ثبت/تأیید/رد/بازگشایی برای پیگیری

این ماژول مستقل از «بیمه تکمیلی» است و هیچ داده‌ای از آن نمی‌خواند.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class FamilyProfile(Base, TimestampMixin):
    __tablename__ = "family_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # draft (فقط مدرک آپلود شده، فرم ثبت نشده) / pending / approved / rejected / returned
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    marital_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    marriage_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    separation_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_head_of_household: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_children: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # بررسی منابع انسانی
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)  # دلیل رد/بازگشت؛ به کارمند نمایش داده می‌شود
    effective_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # تاریخ اثر آخرین تأیید (شمسی)
    # آخرین نسخه‌ی تأییدشده (برای گزارش حقوق)؛ ویرایش بعدی کارمند تا تأیید دوباره روی آن اثر نمی‌گذارد
    approved_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # فقط منابع انسانی: سابقه‌ی پرداخت حق بیمه (روز) و یادداشت داخلی (به کارمند نمایش داده نمی‌شود)
    insurance_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # «کل سابقه» (جایگزین محاسبه)
    hr_prior_insurance_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # سابقه‌ی پیش از استخدام (منابع انسانی)
    # سابقه‌ی بیمه‌ی پیش از استخدام که خود پرسنل در فرم اعلام کرده (با روزهای پس از استخدام جمع می‌شود)
    prior_insurance_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hr_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    employee = relationship("Employee")
    members: Mapped[list["FamilyMember"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="FamilyMember.sort_order"
    )
    documents: Mapped[list["FamilyDocument"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="FamilyDocument.id"
    )


class FamilyMember(Base):
    """همسر (spouse) یا فرزند (son/daughter)؛ ستون‌های نامرتبط با نوع عضو خالی می‌مانند."""

    __tablename__ = "family_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("family_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_type: Mapped[str] = mapped_column(String(16), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    father_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    national_id: Mapped[str | None] = mapped_column(String(10), nullable=True)
    birth_certificate_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    birth_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # همسر
    marriage_certificate_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(11), nullable=True)
    is_employed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    employer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_insured: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    receives_child_allowance: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_disabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # فرزند
    relation: Mapped[str | None] = mapped_column(String(16), nullable=True)  # biological / adopted / step
    other_parent_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    custody: Mapped[str | None] = mapped_column(String(16), nullable=True)  # employee / other_parent / joint
    is_student: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # پسر
    education_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    school_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_married: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # دختر
    marriage_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    student_cert_expiry: Mapped[str | None] = mapped_column(String(10), nullable=True)  # تاریخ اعتبار گواهی تحصیل (شمسی)

    profile: Mapped[FamilyProfile] = relationship(back_populates="members")
    documents: Mapped[list["FamilyDocument"]] = relationship(back_populates="member", order_by="FamilyDocument.id")


class FamilyDocument(Base):
    """
    یک فایل مدرک. member_id خالی = مدرک کل پرونده (سند ازدواج، ...).
    linked=False یعنی آپلود شده ولی هنوز در فرم ثبت‌شده به آن ارجاع نشده (زمان‌بند بعد از ۷۲ ساعت پاک می‌کند).
    """

    __tablename__ = "family_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("family_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[int | None] = mapped_column(
        ForeignKey("family_members.id", ondelete="SET NULL"), nullable=True, index=True
    )
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    linked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # حذف‌شده در ویرایش جدید ولی جزو نسخه‌ی تأییدشده (approved_data)؛ در فرم دیده نمی‌شود و با تأیید بعدی پاک می‌شود
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    uploaded_jalali: Mapped[str | None] = mapped_column(String(10), nullable=True)  # مبنای محاسبه‌ی انقضا

    profile: Mapped[FamilyProfile] = relationship(back_populates="documents")
    member: Mapped[FamilyMember | None] = relationship(back_populates="documents")


class FamilyChangeLog(Base):
    """یک رویداد در تاریخچه‌ی پرونده (submitted/approved/rejected/returned/insurance_days)."""

    __tablename__ = "family_change_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("family_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
