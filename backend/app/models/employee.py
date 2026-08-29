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

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, UniqueConstraint
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
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
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

    # فقط روز/ماه تولد (شمسی) — بدون سال، چون فقط برای کارت «متولدین روز
    # جاری» در داشبورد استفاده می‌شود، نه محاسبه سن. مقدار خام از دیتابیس
    # مبدأ (طبق EmployeeMapping.birth_date_column، در صورت تعریف) توسط
    # Sync Engine استخراج و اینجا ذخیره می‌شود.
    birth_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    birth_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # نام سمت/عنوان شغلی — مستقیماً به‌صورت متن ذخیره می‌شود (نه یک جدول جدا با
    # Foreign Key مثل Department)، چون سمت فقط برای نمایش اطلاعاتی است و به آن
    # نیازی مثل هدف‌گیری اطلاعیه یا تعیین سرپرست ندارد.
    position_title: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # تصویر بندانگشتی پرسنل (از جدول جدا EmployeeExtendedInfo، ستون ThumbnailImg
    # — معمولاً GIF) — فقط برای نمایش آواتار کوچک؛ تصویر اصلی با کیفیت بالا
    # عمداً همگام‌سازی/ذخیره نمی‌شود.
    photo_thumbnail: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # کاملاً مجزا از is_active: فقط و فقط از پنل «پرسنل» توسط Admin تغییر می‌کند.
    # Sync Engine هرگز این ستون را نمی‌خواند/نمی‌نویسد — پس با هیچ Sync جدیدی
    # از بین نمی‌رود. وضعیت واقعی «مجاز به ورود/دریافت اطلاعیه» ترکیب هر دو
    # است: is_active (وضعیت در منبع) AND is_enabled (تصمیم دستی Admin).
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # کاملاً خودانتخاب و شخصی — فقط از پنل «پرسنل من» توسط خودِ کاربر تغییر
    # می‌کند (نه Admin). دقیقاً مثل is_enabled، Sync Engine هرگز این ستون
    # را نمی‌خواند/نمی‌نویسد. فقط روی کارت «متولدین امروز» در داشبورد
    # شخصی پرسنل اثر دارد — نه پنل Admin، نه ابزار ارسال پیام تبریک تولد
    # (که هردو باید همچنان همه پرسنل را ببینند).
    hide_birthday_in_dashboard: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ⚠️ استثنای عمدی روی قاعده «همه رکوردها فقط از Sync می‌آیند» بالا —
    # طبق قابلیت «افزودن دستی پرسنل» (مجوز employees.create)، این فقط
    # برای شفافیت/گزارش‌گیری است تا Admin بداند این رکورد از کجا آمده. اگر
    # بعداً همان personnel_code در منبع Sync واقعی هم ظاهر شود، طبق منطق
    # موجود Sync Engine (Upsert بر اساس personnel_code+site_id) به‌طور
    # طبیعی به‌روزرسانی/ادغام می‌شود، نه خطا یا رکورد تکراری.
    is_manually_created: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

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

    # اختیاری: نام ستون تاریخ تولد شمسی خام در دیتابیس مبدأ (فرمت رایج
    # «۱۳۷۰/۰۵/۲۱» یا مشابه) — Sync Engine فقط روز/ماه را از آن استخراج
    # می‌کند (برای کارت «متولدین روز جاری» در داشبورد)، بدون نیاز به تبدیل
    # تقویم شمسی/میلادی.
    birth_date_column: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # اختیاری: اگر دیتابیس مبدأ ستونی برای فعال/غیرفعال بودن پرسنل داشته باشد
    is_active_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # اگر True باشد، یعنی منطق ستون بالا برعکس است (مثل ستونی به اسم IsCut
    # که ۱=غیرفعال و ۰=فعال است، برخلاف فرض پیش‌فرض ۱=فعال و ۰=غیرفعال)
    is_active_inverted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # اختیاری: نام ستونی در جدول پرسنل مبدأ که کد/شماره واحد سازمانی است
    # (مثلاً ستون Sec_No در جدول dbo.Employee)
    department_column: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # اختیاری: مشخصات جدول Lookup که آن کد را به نام واقعی واحد ترجمه می‌کند
    # (مثلاً جدول dbo.Sections با ستون‌های Sec_No و Title). اگر تعریف شود،
    # Sync Engine خودش واحد سازمانی متناظر را در Portal پیدا/می‌سازد.
    department_lookup_table: Mapped[str | None] = mapped_column(String(128), nullable=True)
    department_lookup_id_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    department_lookup_name_column: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # اختیاری: نام ستونی در جدول پرسنل مبدأ که کد سمت/عنوان شغلی است (مثلاً
    # ستون Pos_No). اگر تعریف شود، Sync Engine نام واقعی سمت را از جدول
    # Lookup زیر ترجمه می‌کند — دقیقاً همان الگوی واحد سازمانی بالا.
    position_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    position_lookup_table: Mapped[str | None] = mapped_column(String(128), nullable=True)
    position_lookup_id_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    position_lookup_name_column: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # اختیاری: جدول جداگانه‌ی عکس پرسنل (مثل EmployeeExtendedInfo با ستون‌های
    # Emp_No/ThumbnailImg) — اگر هر سه فیلد زیر تعریف شوند، Sync Engine بعد
    # از همگام‌سازی معمول پرسنل، تصویر بندانگشتی هرکدام را هم می‌خواند.
    photo_table: Mapped[str | None] = mapped_column(String(128), nullable=True)
    photo_emp_no_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    photo_thumbnail_column: Mapped[str | None] = mapped_column(String(128), nullable=True)

    site: Mapped["Site"] = relationship()
