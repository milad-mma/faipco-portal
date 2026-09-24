"""
مدل‌های «ساختار ارزیابی عملکرد»: مشخص می‌کنند چه کسی مجاز به ارزیابی چه کسی است.
این انتساب‌ها مخصوص همین ماژول‌اند و به نام/مجوز نقش‌های RBAC (که قابل تغییرند)
یا Department.supervisor_user_id (که برای هدف‌گیری اطلاعیه‌هاست) وابسته نیستند.

همه جدول‌ها به Employee (نه User) وصل می‌شوند، چون انتخاب در پنل مدیریت از بین پرسنل است.

سلسله‌مراتب ارزیابی:
    مدیر (EvaluationManager)     →  هر پرسنلی که صریحاً در EvaluationManagerAssignment
                                     به او اختصاص داده شده (سرپرست، مدیر دیگر یا پرسنل عادی،
                                     از هر واحد/سایتی)
    سرپرست واحد                 →  پرسنل واحد خودش
                                     (اگر واحد سرشیفت داشته باشد، فقط سرشیفت‌ها)
    سرشیفت واحد                  →  فقط زیرمجموعه‌ی خودش (نه کل واحد،
                                     نه سرشیفت‌های دیگر همان واحد)
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class EvaluationDepartmentSupervisor(Base, TimestampMixin):
    """
    سرپرستِ ارزیابی یک واحد سازمانی؛ مستقل از Department.supervisor_user_id
    (که برای هدف‌گیری اطلاعیه‌هاست). هر واحد حداکثر یک سرپرست ارزیابی دارد.
    """

    __tablename__ = "evaluation_department_supervisors"

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), unique=True, nullable=False
    )  # یکتا: هر واحد فقط یک سرپرست ارزیابی
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)

    department: Mapped["Department"] = relationship()  # noqa: F821
    employee: Mapped["Employee"] = relationship()  # noqa: F821


class EvaluationManager(Base, TimestampMixin):
    """
    یک «مدیر» در سلسله‌مراتب ارزیابی یک سایت (مدیر سایت، تولید، فنی و ...)؛ هر سایت
    می‌تواند چند مدیر داشته باشد. مدیر به‌طور خودکار کسی را ارزیابی نمی‌کند و اهدافش
    فقط از طریق EvaluationManagerAssignment مشخص می‌شوند.
    """

    __tablename__ = "evaluation_managers"
    __table_args__ = (UniqueConstraint("site_id", "employee_id", name="uq_evaluation_manager"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    # عنوان نمایشی در پنل مدیریت (مثلاً «مدیر تولید»)؛ هیچ منطقی به آن وابسته نیست
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    site: Mapped["Site"] = relationship()  # noqa: F821
    employee: Mapped["Employee"] = relationship()  # noqa: F821
    assignments: Mapped[list["EvaluationManagerAssignment"]] = relationship(
        back_populates="manager", cascade="all, delete-orphan"
    )  # با حذف مدیر، اهداف او هم حذف می‌شوند


class EvaluationManagerAssignment(Base, TimestampMixin):
    """
    یک هدف ارزیابی برای یک مدیر: مدیر (manager_id) این پرسنل (target_employee_id) را
    ارزیابی می‌کند. هدف می‌تواند سرپرست، مدیر دیگر یا هر پرسنلی از هر واحد/سایتی باشد.
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
    سرشیفتِ یک واحد (اختیاری). اگر واحدی حداقل یک سرشیفت داشته باشد، سرپرست فقط
    سرشیفت‌ها را ارزیابی می‌کند و هر سرشیفت فقط زیرمجموعه‌ی خودش (EvaluationShiftAssignment) را.
    این‌که سرشیفت‌ها زیرمجموعه‌ی هم نشوند در Service Layer کنترل می‌شود، نه با Constraint دیتابیس.
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
    مشخص می‌کند هر پرسنل عادی (غیر سرشیفت) زیرمجموعه کدام سرشیفت است.
    پرسنل بین سرشیفت‌های واحد تقسیم می‌شوند و هر پرسنل فقط زیر یک سرشیفت است.
    """

    __tablename__ = "evaluation_shift_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    shift_lead_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_shift_leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), unique=True, nullable=False
    )  # یکتا: هر پرسنل فقط زیر یک سرشیفت

    shift_lead: Mapped["EvaluationShiftLead"] = relationship()
    employee: Mapped["Employee"] = relationship()  # noqa: F821
