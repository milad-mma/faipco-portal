"""
مدل‌های ماژول «درخواست وام» (Migration 107؛ docs/loans.md). همه در دیتابیس پورتال؛ کاراوب و حسابداری دخالتی ندارند
(بدهی وام در کاراوب نیست، پس پرداخت/اقساط/تسویه را واحد مالی همین‌جا ثبت می‌کند).

- LoanSiteSettings: روشن/خاموش ماژول برای هر سایت + مدیر سایت (تأییدکننده‌ی مرحله‌ی «مدیر سایت»)
- LoanPolicy: «مقررات وام» هر سایت با تاریخ اجرا (نسخه‌ها؛ نسخه‌ی جاری = آخرین تاریخ اجرای گذشته)
- LoanType: انواع وام هر مقررات (سقف، حداقل سابقه، تعداد ضامن، مدرک اضافه، خارج از نوبت)
- LoanRequest: درخواست (snapshot مراحل و نوع)، LoanRequestGuarantor، LoanRequestEvent (تاریخچه)، LoanInstallment
- LoanServiceOverride: اصلاح دستی «تاریخ شروع سابقه» یک پرسنل توسط مالی
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class LoanSiteSettings(Base, TimestampMixin):
    __tablename__ = "loan_site_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), unique=True, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    site_manager_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    # آخرین شماره‌ی نوبت داده‌شده در این سایت (با قفل ردیف افزایش می‌یابد تا دو Worker شماره‌ی تکراری ندهند)
    last_queue_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class LoanPolicy(Base, TimestampMixin):
    __tablename__ = "loan_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    effective_from: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY/MM/DD شمسی
    rules_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # متن دستورالعمل برای پرسنل
    block_if_unsettled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    approval_steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # قواعد اختیاری ضامن (None/False = بدون محدودیت)
    guarantor_max_active: Mapped[int | None] = mapped_column(Integer, nullable=True)
    guarantor_min_service_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    guarantor_no_active_loan: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    types: Mapped[list["LoanType"]] = relationship(
        back_populates="policy", cascade="all, delete-orphan", order_by="LoanType.sort_order"
    )


class LoanType(Base):
    __tablename__ = "loan_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("loan_policies.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    max_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # ریال
    min_service_months: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    guarantor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra_requirement: Mapped[str | None] = mapped_column(String(500), nullable=True)  # مثلاً «سفته ۴۰۰ میلیون ریالی»
    out_of_queue: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    policy: Mapped[LoanPolicy] = relationship(back_populates="types")


class LoanRequest(Base, TimestampMixin):
    __tablename__ = "loan_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_id: Mapped[int | None] = mapped_column(ForeignKey("loan_policies.id", ondelete="SET NULL"), nullable=True)
    loan_type_id: Mapped[int | None] = mapped_column(ForeignKey("loan_types.id", ondelete="SET NULL"), nullable=True)
    # snapshot نوع در لحظه‌ی ثبت (تغییر بعدی مقررات روی درخواست ثبت‌شده اثر ندارد)
    type_title: Mapped[str] = mapped_column(String(200), nullable=False)
    out_of_queue: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extra_requirement: Mapped[str | None] = mapped_column(String(500), nullable=True)
    amount_requested: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    unit_manager_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    site_manager_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    # تأییدکننده‌ی مرحله‌ی جاری (مدیر واحد/سایت)؛ در مرحله‌ی ضامن و مالی خالی
    current_approver_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    queue_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount_approved: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    extra_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    finance_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # ثبت دستی مالی (نوبت‌های قبلی)

    employee: Mapped["Employee"] = relationship(foreign_keys=[employee_id])  # noqa: F821
    guarantors: Mapped[list["LoanRequestGuarantor"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="LoanRequestGuarantor.id"
    )
    events: Mapped[list["LoanRequestEvent"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="LoanRequestEvent.id"
    )
    installments: Mapped[list["LoanInstallment"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="LoanInstallment.seq"
    )


class LoanRequestGuarantor(Base):
    __tablename__ = "loan_request_guarantors"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("loan_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")  # pending/accepted/rejected
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    request: Mapped[LoanRequest] = relationship(back_populates="guarantors")
    employee: Mapped["Employee"] = relationship()  # noqa: F821


class LoanRequestEvent(Base):
    __tablename__ = "loan_request_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("loan_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    request: Mapped[LoanRequest] = relationship(back_populates="events")


class LoanInstallment(Base):
    __tablename__ = "loan_installments"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("loan_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    due_month: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY/MM
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    request: Mapped[LoanRequest] = relationship(back_populates="installments")


class LoanServiceOverride(Base, TimestampMixin):
    __tablename__ = "loan_service_overrides"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY/MM/DD
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    set_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
