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

from sqlalchemy import JSON, SmallInteger, Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class Department(Base, TimestampMixin):
    """واحد سازمانی یک Site؛ کد واحد در هر سایت یکتاست و از Sync یا دستی ساخته می‌شود."""

    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("site_id", "code", name="uq_department_site_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)  # کد واحد در سیستم منبع (مثلاً Sec_No)

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

    personnel_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # کلید تطبیق با منبع (همراه site_id)
    national_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    mobile: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # فقط روز/ماه تولد (شمسی)، بدون سال؛ برای کارت «متولدین روز جاری» در داشبورد.
    # Sync Engine آن را از ستون EmployeeMapping.birth_date_column (در صورت تعریف) استخراج می‌کند.
    birth_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    birth_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # برای ماژول «بیمه تکمیلی»: تاریخ تولد و استخدام کامل شمسی («1370/05/21») و
    # جنسیت (۱=مرد، ۲=زن، همان کد کاراوب)؛ از نگاشت پرسنل Sync می‌شوند
    birth_date_jalali: Mapped[str | None] = mapped_column(String(10), nullable=True)
    hire_date_jalali: Mapped[str | None] = mapped_column(String(10), nullable=True)
    gender: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # نام سمت/عنوان شغلی به‌صورت متن (بدون جدول و Foreign Key جدا)، چون فقط برای نمایش است.
    position_title: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # تصویر بندانگشتی پرسنل (از جدول EmployeeExtendedInfo، ستون ThumbnailImg، معمولاً GIF)
    # برای نمایش آواتار کوچک؛ تصویر اصلی با کیفیت بالا همگام‌سازی نمی‌شود.
    photo_thumbnail: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # وضعیت فعال/کات در منبع؛ توسط Sync تعیین می‌شود

    # کاملاً مجزا از is_active: فقط و فقط از پنل «پرسنل» توسط Admin تغییر می‌کند.
    # Sync Engine هرگز این ستون را نمی‌خواند/نمی‌نویسد — پس با هیچ Sync جدیدی
    # از بین نمی‌رود. وضعیت واقعی «مجاز به ورود/دریافت اطلاعیه» ترکیب هر دو
    # است: is_active (وضعیت در منبع) AND is_enabled (تصمیم دستی Admin).
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # تنظیم شخصی که فقط خودِ کاربر از پنل «پرسنل من» تغییر می‌دهد؛ Sync Engine به آن دست نمی‌زند.
    # فقط روی کارت «متولدین امروز» داشبورد شخصی پرسنل اثر دارد، نه پنل Admin و نه ارسال پیام تبریک.
    hide_birthday_in_dashboard: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # True یعنی رکورد از «افزودن دستی پرسنل» (مجوز employees.create) آمده، نه از Sync؛ فقط برای گزارش.
    # اگر همان personnel_code بعداً در منبع ظاهر شود، Sync با Upsert بر اساس personnel_code+site_id آن را به‌روز می‌کند.
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

    table_name: Mapped[str] = mapped_column(String(128), nullable=False)  # جدول پرسنل در دیتابیس منبع (مثلاً dbo.Employee)

    personnel_code_column: Mapped[str] = mapped_column(String(128), nullable=False)
    national_code_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_name_column: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name_column: Mapped[str] = mapped_column(String(128), nullable=False)
    mobile_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email_column: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # اختیاری: ستون تاریخ تولد شمسی خام در مبدأ (مثل «۱۳۷۰/۰۵/۲۱»)؛ Sync Engine از آن
    # روز/ماه تولد و تاریخ کامل را بدون تبدیل تقویم استخراج می‌کند.
    birth_date_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # اختیاری (بیمه تکمیلی): تاریخ استخدام شمسی و جنسیت (کاراوب: Emp_Date / Gender)
    hire_date_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gender_column: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # اختیاری: اگر دیتابیس مبدأ ستونی برای فعال/غیرفعال بودن پرسنل داشته باشد
    is_active_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # اگر True باشد، یعنی منطق ستون بالا برعکس است (مثل ستونی به اسم IsCut
    # که ۱=غیرفعال و ۰=فعال است، برخلاف فرض پیش‌فرض ۱=فعال و ۰=غیرفعال)
    is_active_inverted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # اختیاری: وقتی چند سایت یک دیتابیس/جدول پرسنل مشترک دارند (مثل
    # Employee.BranchCode در کاراوب): فقط ردیف‌هایی که مقدار این ستون برابر
    # branch_code_value است مال این سایت‌اند و Sync می‌شوند.
    branch_code_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    branch_code_value: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # اختیاری: نام ستونی در جدول پرسنل مبدأ که کد/شماره واحد سازمانی است
    # (مثلاً ستون Sec_No در جدول dbo.Employee)
    department_column: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # اختیاری: مشخصات جدول Lookup که آن کد را به نام واقعی واحد ترجمه می‌کند
    # (مثلاً جدول dbo.Sections با ستون‌های Sec_No و Title). اگر تعریف شود،
    # Sync Engine خودش واحد سازمانی متناظر را در Portal پیدا/می‌سازد.
    department_lookup_table: Mapped[str | None] = mapped_column(String(128), nullable=True)
    department_lookup_id_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    department_lookup_name_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # اختیاری: ستون «واحد بالادست» در همان جدول Lookup (کاراوب: Sections.TFather)؛
    # برای تقسیم درخت واحدها بین چند سایتی که یک دیتابیس منبع مشترک دارند.
    department_lookup_parent_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # کد واحدهای ریشه‌ی این سایت. هر واحد متعلق به سایتی است که نزدیک‌ترین ریشه‌ی
    # بالادستش را دارد (core/org_tree.py). فهرست خالی = بدون فیلتر درختی (همه‌ی پرسنل).
    root_department_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

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

    # اختیاری (گزارش جذب و ترک کار — Migration 089): فقط برای خواندن مستقیم آمار از منبع؛
    # پرسنل قطع‌همکاری‌شده وارد پرتال نمی‌شوند. کاراوب: End_Date / Cut_Reason / Grade_No + Grades
    termination_date_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    termination_reason_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    education_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    education_lookup_table: Mapped[str | None] = mapped_column(String(128), nullable=True)
    education_lookup_id_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    education_lookup_name_column: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # ماه شروع آمار این سایت (مثل «1403/06» = شروع کار با سیستم منبع)؛ خالی = از اولین داده
    turnover_start_month: Mapped[str | None] = mapped_column(String(7), nullable=True)
    # اختیاری (Migration 090): جدول تاریخچه‌ی تغییرات پرسنل با همان ستون‌های جدول پرسنل (کاراوب: LogEmployee)
    # و ستون زمان تغییر (ChangeDate). کاراوب برای استخدام مجدد رکورد جدید نمی‌سازد؛ دوره‌های قبلی فقط اینجا می‌مانند.
    history_table: Mapped[str | None] = mapped_column(String(128), nullable=True)
    history_order_column: Mapped[str | None] = mapped_column(String(128), nullable=True)

    site: Mapped["Site"] = relationship()
