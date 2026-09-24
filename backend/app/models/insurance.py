"""
جدول‌های ماژول «بیمه تکمیلی»:
- InsuranceRegistration: یک ثبت‌نام برای هر پرسنل (اطلاعات شخص اصلی + بانکی)
- InsuranceMember: اعضای خانواده یک ثبت‌نام (همسر/فرزند/پدر/مادر)
- InsuranceDocument: مدرک کفالت/حضانت یک عضو (محتوای فایل داخل دیتابیس)
مقادیر ثابت بیمه‌گر ذخیره نمی‌شوند و هنگام خروجی Excel اضافه می‌شوند.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class InsuranceRegistration(Base, TimestampMixin):
    __tablename__ = "insurance_registrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # نسخه‌ای از اطلاعات پرسنل در لحظه ثبت (تا خروجی Excel با تغییرات بعدی Sync عوض نشود)
    personnel_code: Mapped[str] = mapped_column(String(64), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    father_name: Mapped[str] = mapped_column(String(100), nullable=False)
    birth_date: Mapped[str] = mapped_column(String(10), nullable=False)
    gender: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    marital_status: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    national_id: Mapped[str] = mapped_column(String(10), nullable=False)
    birth_certificate_no: Mapped[str] = mapped_column(String(20), nullable=False)
    mobile_number: Mapped[str] = mapped_column(String(11), nullable=False)
    employment_date: Mapped[str] = mapped_column(String(10), nullable=False)
    insurance_no: Mapped[str] = mapped_column(String(10), nullable=False)
    bank_code: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    account_number: Mapped[str] = mapped_column(String(40), nullable=False)
    sheba: Mapped[str] = mapped_column(String(24), nullable=False)
    account_type: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    account_owner: Mapped[str] = mapped_column(String(200), nullable=False)
    account_owner_national_id: Mapped[str] = mapped_column(String(10), nullable=False)

    employee = relationship("Employee")
    members: Mapped[list["InsuranceMember"]] = relationship(
        back_populates="registration", cascade="all, delete-orphan", order_by="InsuranceMember.sort_order"
    )


class InsuranceMember(Base):
    """یک عضو خانواده؛ member_type='pending' یعنی نگهدارنده موقت مدرکی که هنوز به عضو واقعی وصل نشده."""

    __tablename__ = "insurance_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    registration_id: Mapped[int] = mapped_column(
        ForeignKey("insurance_registrations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_type: Mapped[str] = mapped_column(String(16), nullable=False)
    relation_code: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    dependency_code: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    father_name: Mapped[str] = mapped_column(String(100), nullable=False)
    birth_date: Mapped[str] = mapped_column(String(10), nullable=False)
    gender: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    marital_status: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    national_id: Mapped[str] = mapped_column(String(10), nullable=False)
    birth_certificate_no: Mapped[str] = mapped_column(String(20), nullable=False)
    mobile_number: Mapped[str] = mapped_column(String(11), nullable=False)
    kafala_status: Mapped[str | None] = mapped_column(String(3), nullable=True)  # yes / no / NULL (پرسیده نشده)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    registration: Mapped[InsuranceRegistration] = relationship(back_populates="members")
    document: Mapped["InsuranceDocument | None"] = relationship(
        back_populates="member", cascade="all, delete-orphan", uselist=False
    )


class InsuranceDocument(Base):
    """فایل مدرک یک عضو؛ هر عضو حداکثر یک مدرک دارد."""

    __tablename__ = "insurance_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(
        ForeignKey("insurance_members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    member: Mapped[InsuranceMember] = relationship(back_populates="document")
