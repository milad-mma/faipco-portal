"""
مدل‌های «ساختار ارزیابی عملکرد» - مشخص می‌کنند چه کسی مجاز به ارزیابی چه
کسی است، بر اساس یک انتساب صریح و مخصوص همین ماژول (نه بر اساس نام/مجوز
نقش‌های RBAC، که طبق تصمیم صریح کاربر قابل تغییر نام/دسترسی هستند و برای
این منظور قابل‌اتکا نیستند؛ و نه با استفاده مجدد از Department.supervisor_user_id
موجود، چون آن برای هدف‌گیری اطلاعیه‌ها استفاده می‌شود و باید کاملاً مستقل
از سرپرستِ ارزیابی باشد).

⚠️ همه این جدول‌ها به Employee (نه مستقیماً User) وصل می‌شوند - چون
انتخاب از پنل مدیریت همیشه از بین «پرسنل» انجام می‌شود.

⚠️ بازطراحی دور دوم (طبق بازخورد صریح کاربر): طراحی قبلی فرض می‌کرد
«مدیر سایت» همیشه *همه* سرپرست‌های واحدها را خودکار ارزیابی می‌کند - ولی
چارت سازمانی واقعی شرکت‌ها این‌قدر ساده نیست: ممکن است مدیر سایت فقط
چند سرپرست خاص را مستقیم ارزیابی کند، و بقیه زیر نظر یک مدیر میانی
(مثلاً «مدیر تولید») باشند که خودش هم یک سطح ارزیابی مستقل است. برای
همین «مدیر سایت» به یک مفهوم عمومی‌تر تبدیل شد: EvaluationManager - هر
مدیری (سایت، تولید، فنی، هرچی) که اهداف ارزیابی‌اش کاملاً صریح و دستی
مشخص می‌شود (EvaluationManagerAssignment) - نه با یک قانون خودکار.
یک مدیر می‌تواند هر پرسنلی را هدف بگیرد؛ سرپرست واحد، مدیر دیگر، یا حتی
یک پرسنل عادی از هر واحد/سایتی - دقیقاً طبق چارت واقعی سازمان، نه یک
فرض از پیش تعیین‌شده.

سلسله‌مراتب نتیجه (جدید، منعطف):
    مدیر (هر تعداد، هر عنوانی)  →  ارزیابی: هر لیستی از افراد که صریحاً
                                     به او اختصاص داده شده (EvaluationManagerAssignment)
    سرپرست واحد                 →  ارزیابی: پرسنل واحد خودش
                                     (اگر آن واحد سرشیفت هم داشته باشد، فقط سرشیفت‌ها)
    سرشیفت واحد                  →  ارزیابی: فقط زیرمجموعه‌ی خودش (نه کل واحد،
                                     نه سرشیفت‌های دیگر همان واحد)
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
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


class EvaluationManager(Base, TimestampMixin):
    """
    یک «مدیر» در سلسله‌مراتب ارزیابی یک سایت - می‌تواند مدیر سایت، مدیر
    تولید، مدیر فنی، یا هر نقش مدیریتی میانی دیگری باشد؛ یک سایت می‌تواند
    هم‌زمان چند مدیر (در سطوح مختلف یا هم‌سطح) داشته باشد. برخلاف طراحی
    قبلی، این مدیر به‌طور خودکار هیچ‌کس را ارزیابی نمی‌کند - چه کسانی را
    ارزیابی می‌کند، کاملاً از طریق EvaluationManagerAssignment و به‌صورت
    صریح مشخص می‌شود.
    """

    __tablename__ = "evaluation_managers"
    __table_args__ = (UniqueConstraint("site_id", "employee_id", name="uq_evaluation_manager"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    # فقط برای نمایش/تشخیص در پنل مدیریت (مثلاً «مدیر تولید») - هیچ منطقی
    # به این مقدار وابسته نیست
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    site: Mapped["Site"] = relationship()  # noqa: F821
    employee: Mapped["Employee"] = relationship()  # noqa: F821
    assignments: Mapped[list["EvaluationManagerAssignment"]] = relationship(
        back_populates="manager", cascade="all, delete-orphan"
    )


class EvaluationManagerAssignment(Base, TimestampMixin):
    """
    این مدیر (EvaluationManager) دقیقاً چه کسانی را ارزیابی می‌کند - هدف
    می‌تواند سرپرست یک واحد، مدیر دیگر، یا هر پرسنل دیگری (حتی از واحد یا
    حتی سایت دیگر - طبق درخواست صریح کاربر) باشد. کاملاً دستی و صریح -
    هیچ قانون خودکاری («مدیر سایت = همه سرپرست‌ها») دیگر اعمال نمی‌شود.
    """

    __tablename__ = "evaluation_manager_assignments"
    __table_args__ = (UniqueConstraint("manager_id", "target_employee_id", name="uq_evaluation_manager_target"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    manager_id: Mapped[int] = mapped_column(ForeignKey("evaluation_managers.id", ondelete="CASCADE"), nullable=False)
    target_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)

    manager: Mapped["EvaluationManager"] = relationship(back_populates="assignments")
    target_employee: Mapped["Employee"] = relationship()  # noqa: F821


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
