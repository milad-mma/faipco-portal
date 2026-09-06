"""
مدل‌های «ساختار ارزیابی عملکرد» - مشخص می‌کنند چه کسی مجاز به ارزیابی چه
کسی است، بر اساس یک انتساب صریح و مخصوص همین ماژول (نه بر اساس نام/مجوز
نقش‌های RBAC، که طبق تصمیم صریح کاربر قابل تغییر نام/دسترسی هستند و برای
این منظور قابل‌اتکا نیستند؛ و نه با استفاده مجدد از Department.supervisor_user_id
موجود، چون آن برای هدف‌گیری اطلاعیه‌ها استفاده می‌شود و باید کاملاً مستقل
از سرپرستِ ارزیابی باشد).

⚠️ همه این جدول‌ها به Employee (نه مستقیماً User) وصل می‌شوند - چون
انتخاب از پنل مدیریت همیشه از بین «پرسنل» انجام می‌شود. طبق تصمیم صریح
کاربر، اگر پرسنل انتخاب‌شده هنوز حساب کاربری نداشته باشد، به‌صورت خودکار
یک حساب برایش ساخته می‌شود (نگاه کنید به UserRepository.get_or_create_employee_user
در app/services/evaluation_structure_service.py) - دقیقاً همان مکانیزمی
که برای اولین ورود پرسنل با کد پرسنلی/کد ملی هم استفاده می‌شود.

سلسله‌مراتب نتیجه (طبق تصمیم صریح کاربر):
    مدیر سایت (چند نفر مجاز)  →  ارزیابی: سرپرست‌های واحدها + سایر مدیران
    سرپرست واحد               →  ارزیابی: پرسنل واحد خودش
                                   (اگر آن واحد سرشیفت هم داشته باشد، فقط سرشیفت‌ها)
    سرشیفت واحد                →  ارزیابی: فقط زیرمجموعه‌ی خودش (نه کل واحد،
                                   نه سرشیفت‌های دیگر همان واحد)
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class EvaluationDepartmentSupervisor(Base, TimestampMixin):
    """
    سرپرستِ ارزیابی یک واحد سازمانی - کاملاً مستقل از Department.supervisor_user_id
    موجود (که برای هدف‌گیری اطلاعیه‌ها استفاده می‌شود). هر واحد حداکثر یک
    سرپرست ارزیابی دارد (department_id یکتا).
    """

    __tablename__ = "evaluation_department_supervisors"

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)

    department: Mapped["Department"] = relationship()  # noqa: F821
    employee: Mapped["Employee"] = relationship()  # noqa: F821


class EvaluationSiteManager(Base, TimestampMixin):
    """
    مدیر سایت برای ارزیابی - طبق تصمیم صریح کاربر، هر سایت می‌تواند
    هم‌زمان چند مدیر سایت داشته باشد (نه لزوماً دقیقاً یک نفر).
    """

    __tablename__ = "evaluation_site_managers"
    __table_args__ = (UniqueConstraint("site_id", "employee_id", name="uq_evaluation_site_manager"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)

    site: Mapped["Site"] = relationship()  # noqa: F821
    employee: Mapped["Employee"] = relationship()  # noqa: F821


class EvaluationOtherManager(Base, TimestampMixin):
    """
    «سایر مدیران» یک سایت - افرادی که مدیر سایت باید ارزیابی‌شان کند،
    جدای سرپرست‌های واحد (که خودشان به‌طور خودکار هدف مدیر سایت هستند).
    اگر فردی که اینجا اضافه می‌شود، هم‌زمان سرپرست یک واحد هم باشد، هیچ
    تداخلی ایجاد نمی‌شود - در فهرست نهایی اهداف مدیر سایت، این دو منبع
    ترکیب (Union بر اساس employee_id) می‌شوند، پس چنین فردی فقط یک‌بار
    ظاهر می‌شود، نه دوبار.
    """

    __tablename__ = "evaluation_other_managers"
    __table_args__ = (UniqueConstraint("site_id", "employee_id", name="uq_evaluation_other_manager"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)

    site: Mapped["Site"] = relationship()  # noqa: F821
    employee: Mapped["Employee"] = relationship()  # noqa: F821


class EvaluationShiftLead(Base, TimestampMixin):
    """
    سرشیفتِ یک واحد - قابلیت اختیاری. اگر برای یک واحد حداقل یک سرشیفت
    تعریف شود، رفتار ارزیابی آن واحد تغییر می‌کند: سرپرست دیگر همه پرسنل
    واحد را مستقیم ارزیابی نمی‌کند (فقط سرشیفت‌ها را)، و هر سرشیفت فقط
    زیرمجموعه‌ی خودش (طبق EvaluationShiftAssignment) را ارزیابی می‌کند.
    سرشیفت‌های یک واحد هرگز نمی‌توانند یکدیگر را ارزیابی کنند - این طبق
    طراحی خودِ داده تضمین می‌شود (EvaluationShiftAssignment.employee_id
    هرگز نمی‌تواند فردی باشد که خودش هم در همین جدول ثبت شده - این
    قانون در Service Layer enforce می‌شود، نه با یک Constraint دیتابیسی
    پیچیده).
    """

    __tablename__ = "evaluation_shift_leads"
    __table_args__ = (UniqueConstraint("department_id", "employee_id", name="uq_evaluation_shift_lead"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)

    department: Mapped["Department"] = relationship()  # noqa: F821
    employee: Mapped["Employee"] = relationship()  # noqa: F821


class EvaluationShiftAssignment(Base, TimestampMixin):
    """
    مشخص می‌کند هر پرسنل عادی (نه سرشیفت) زیرمجموعه کدام سرشیفت است -
    طبق تصمیم صریح کاربر، پرسنل باید بین سرشیفت‌های یک واحد تقسیم شوند
    (نه این‌که هر سرشیفت مستقل همه را ارزیابی کند)؛ برای همین هر پرسنل
    فقط زیرِ دقیقاً یک سرشیفت می‌تواند باشد (employee_id یکتا در این جدول).
    """

    __tablename__ = "evaluation_shift_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    shift_lead_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_shift_leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    shift_lead: Mapped["EvaluationShiftLead"] = relationship()
    employee: Mapped["Employee"] = relationship()  # noqa: F821
