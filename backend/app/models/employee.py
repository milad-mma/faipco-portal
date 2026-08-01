"""
مدل‌های پرسنل:
- Department: واحد سازمانی (متعلق به یک Site)
- Employee: جدول داخلی و یکپارچه پرسنل در Portal (خروجی نهایی Sync Engine)
- EmployeeMapping: تعریف می‌کند که در دیتابیس خام هر Site، کدام جدول/ستون معادل
  کدام فیلد استاندارد Portal است. این جدول است که Sync Engine را بدون نیاز به
  تغییر کد، با ساختار متفاوت هر سایت سازگار می‌کند.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class Department(Base, TimestampMixin):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("site_id", "code", name="uq_department_site_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)

    # سرپرست این واحد — می‌تواند برای پرسنل همین واحد اطلاعیه ارسال کند
    # (بدون نیاز به هیچ نقش RBAC جداگانه‌ای؛ صرفاً همین اتصال کافی است)
    supervisor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class Employee(Base, TimestampMixin):
    """
    جدول یکپارچه پرسنل در Portal. رکوردهای این جدول توسط Sync Engine
    از دیتابیس‌های خام هر Site پر می‌شوند و مستقیماً توسط کاربر Insert/Update نمی‌شوند.
    """
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("site_id", "personnel_code", name="uq_employee_site_personnel_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    personnel_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    national_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    mobile: Mapped[str | None] = mapped_column(String(32), nullable=True)

    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # آخرین باری که این رکورد توسط Sync Engine از منبع دیده و به‌روزرسانی شده
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    site: Mapped["Site"] = relationship()
    department: Mapped["Department | None"] = relationship()


class EmployeeMapping(Base, TimestampMixin):
    """
    نگاشت ستون‌های دیتابیس خام هر Site به فیلدهای استاندارد Employee.
    هر Site دقیقاً یک Mapping فعال دارد.
    """
    __tablename__ = "employee_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    table_name: Mapped[str] = mapped_column(String(128), nullable=False)

    personnel_code_column: Mapped[str] = mapped_column(String(128), nullable=False)
    national_code_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_name_column: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name_column: Mapped[str] = mapped_column(String(128), nullable=False)
    mobile_column: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # اختیاری: اگر دیتابیس مبدأ ستونی برای فعال/غیرفعال بودن پرسنل داشته باشد
    is_active_column: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # اختیاری: نام ستونی در جدول پرسنل مبدأ که کد/شماره واحد سازمانی است
    # (مثلاً ستون Sec_No در جدول dbo.Employee کارخانه Kara)
    department_column: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # اختیاری: مشخصات جدول Lookup که آن کد را به نام واقعی واحد ترجمه می‌کند
    # (مثلاً جدول dbo.Sections با ستون‌های Sec_No و Title). اگر تعریف شود،
    # Sync Engine خودش واحد سازمانی متناظر را در Portal پیدا/می‌سازد.
    department_lookup_table: Mapped[str | None] = mapped_column(String(128), nullable=True)
    department_lookup_id_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    department_lookup_name_column: Mapped[str | None] = mapped_column(String(128), nullable=True)

    site: Mapped["Site"] = relationship()
