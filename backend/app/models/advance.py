"""
مدل‌های ماژول «درخواست مساعده» (Migration 114؛ docs/advances.md). همه در دیتابیس پورتال.

- AdvanceSettings: تنظیمات هر سایت (فعال/غیرفعال، مدیر سایت مساعده، بازه‌ی روزهای مجاز ثبت، حداکثر دفعات در ماه، متن قوانین)
- AdvanceTier: پله‌ی سابقه ← مبلغ ثابت، جدا برای هر گروه (staff/supervisor/manager)؛ گروه بدون پله = پله‌های پرسنل
- AdvanceGroupMember: تعیین دستی گروه یک پرسنل (مدیر، یا سرپرستی که در زنجیره‌ی تأییدکننده‌ی مرخصی نیست)
- AdvanceRequest: درخواست با snapshot مسیر (مدیر واحد ← مدیر سایت ← مالی) و پرداخت
- AdvanceRequestEvent: تاریخچه
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class AdvanceSettings(Base, TimestampMixin):
    __tablename__ = "advance_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), unique=True, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    site_manager_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    # بازه‌ی روزهای مجاز ثبت در هر ماه شمسی (شامل هر دو سر)؛ اگر from > to باشد بازه از آخر ماه به اول ماه بعد می‌چرخد
    window_from_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    window_to_day: Mapped[int] = mapped_column(Integer, nullable=False, default=31)
    max_per_month: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # حداکثر درخواست (غیر از رد/لغو) در ماه
    rules_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # متن قوانین که بالای فرم به پرسنل نشان داده می‌شود
    # نوع مبلغ: fixed = مبلغ ثابت پله؛ range = مبلغ دلخواه پرسنل بین حداقل و سقف پله (Migration 119)
    amount_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="fixed", server_default="fixed")
    amount_step: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # مضرب مبلغ دلخواه (ریال)؛ خالی = آزاد


class AdvanceTier(Base):
    __tablename__ = "advance_tiers"
    __table_args__ = (UniqueConstraint("site_id", "group", "min_months", name="uq_advance_tier_site_group_months"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    group: Mapped[str] = mapped_column(String(20), nullable=False, default="staff")  # staff | supervisor | manager
    min_months: Mapped[int] = mapped_column(Integer, nullable=False)  # از این سابقه (ماه کامل) به بالا
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # مبلغ ثابت مساعده (ریال)؛ در حالت دلخواه = سقف
    min_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # حداقل مبلغ دلخواه (فقط حالت range)


class AdvanceGroupMember(Base):
    __tablename__ = "advance_group_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True)
    group: Mapped[str] = mapped_column(String(20), nullable=False)  # supervisor | manager


class AdvanceRequest(Base, TimestampMixin):
    __tablename__ = "advance_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    employee_group: Mapped[str] = mapped_column(String(20), nullable=False, default="staff")  # گروه هنگام ثبت
    service_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # YYYY/MM شمسی
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # ["unit_manager","site_manager","finance"]
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_manager_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    site_manager_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    # تأییدکننده‌ی مرحله‌ی جاری (مدیر واحد/مدیر سایت)؛ در مرحله‌ی مالی خالی
    current_approver_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    paid_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY/MM/DD شمسی
    paid_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    employee: Mapped["Employee"] = relationship(foreign_keys=[employee_id])  # noqa: F821
    events: Mapped[list["AdvanceRequestEvent"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="AdvanceRequestEvent.id"
    )


class AdvanceRequestEvent(Base):
    __tablename__ = "advance_request_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("advance_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    request: Mapped[AdvanceRequest] = relationship(back_populates="events")
