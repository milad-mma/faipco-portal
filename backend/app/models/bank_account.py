"""
جدول‌های ماژول «اطلاعات بانکی» پرسنل (docs/bank-accounts.md):
- BankDefinition: بانک‌هایی که پرسنل هر سایت باید/می‌توانند اطلاعاتشان را وارد کنند (از پنل ادمین)، با حالت هر فیلد
- EmployeeBankAccount: اطلاعات هر پرسنل برای هر بانک (یک ردیف به ازای پرسنل × بانک)
- EmployeeBankAccountHistory: سابقه‌ی هر ثبت/تغییر (مقادیر قدیم و جدید، چه کسی، چه زمانی)
- EmployeeBankTerms: پذیرش تعهد «حساب به نام خودِ پرسنل» قبل از اولین ثبت
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin


class BankDefinition(Base, TimestampMixin):
    __tablename__ = "bank_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # مثلاً «بانک ملت»
    # اجباری: پرسنلی که اطلاعات این بانک را کامل نکرده یادآوری «اطلاعات بانکی تکمیل نشده» می‌بیند
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # حالت هر فیلد: required / optional / hidden
    account_number_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="required")
    sheba_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="required")
    card_number_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="optional")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)  # غیرفعال: در فرم پرسنل نمی‌آید
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    @property
    def modes(self) -> dict[str, str]:
        return {
            "account_number": self.account_number_mode,
            "sheba": self.sheba_mode,
            "card_number": self.card_number_mode,
        }


class EmployeeBankAccount(Base, TimestampMixin):
    __tablename__ = "employee_bank_accounts"
    __table_args__ = (UniqueConstraint("employee_id", "bank_id", name="uq_employee_bank_account"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("bank_definitions.id", ondelete="CASCADE"), nullable=False)
    account_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sheba: Mapped[str | None] = mapped_column(String(26), nullable=True)  # IR + ۲۴ رقم
    card_number: Mapped[str | None] = mapped_column(String(16), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class EmployeeBankAccountHistory(Base):
    __tablename__ = "employee_bank_account_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    bank_id: Mapped[int | None] = mapped_column(ForeignKey("bank_definitions.id", ondelete="SET NULL"), nullable=True)
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)  # نام بانک در لحظه‌ی تغییر
    # {field: [قدیم, جدید]}
    changes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    changed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    changed_by_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    by_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # تغییر توسط مسئول، نه خودِ پرسنل
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EmployeeBankTerms(Base):
    """پذیرش تعهد «حساب به نام خودِ پرسنل» قبل از اولین ثبت اطلاعات بانکی (یک بار برای هر پرسنل)."""

    __tablename__ = "employee_bank_terms"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    accepted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    terms_text: Mapped[str] = mapped_column(String(1000), nullable=False)  # عین متن پذیرفته‌شده
