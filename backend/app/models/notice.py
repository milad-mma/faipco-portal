"""
مدل‌های سیستم اطلاعیه سازمانی.

Notice: خود اطلاعیه
NoticeTarget: مخاطب اطلاعیه — یک اطلاعیه می‌تواند چند Target داشته باشد
  (مثلاً هم به یک Site و هم به یک Role خاص ارسال شود).
  target_id بسته به target_type به یکی از جداول sites/departments/roles/employees اشاره دارد
  (Polymorphic ساده - بدون FK مستقیم چون به چند جدول مختلف اشاره می‌کند).
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class NoticePriority(str, enum.Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class NoticeStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    expired = "expired"


class NoticeTargetType(str, enum.Enum):
    all = "all"
    site = "site"
    department = "department"
    role = "role"
    employee = "employee"


class NoticeType(str, enum.Enum):
    """
    normal          → اطلاعیه متنی معمولی (رفتار همیشگی).
    payroll         → اطلاعیه فیش حقوقی: هر مخاطب فقط PDF فیش خودش را می‌بیند
                      (payroll_receipts)، نه متن یکسان برای همه.
    attendance_card → اطلاعیه فیش کارکرد (کارت ماهانه کارکرد پرسنل): مثل
                      payroll، هر مخاطب فقط کارت خودش را می‌بیند
                      (attendance_card_receipts)، از روی آپلود اکسل توسط
                      مدیر منابع انسانی (hr-manager).
    """
    normal = "normal"
    payroll = "payroll"
    attendance_card = "attendance_card"


class Notice(Base, TimestampMixin):
    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # فقط برای اطلاعیه‌های نوع attendance_card: زیرعنوان ماه/سال که روی خودِ
    # کارت PDF چاپ می‌شود (مثلاً «تیر ماه 1405») — عمداً از title جدا است،
    # چون title برای نمایش در لیست اطلاعیه‌های دریافتی است، نه لزوماً همان
    # متنی که روی خودِ کارت باید بیاید.
    card_subtitle: Mapped[str | None] = mapped_column(String(128), nullable=True)

    priority: Mapped[NoticePriority] = mapped_column(
        Enum(NoticePriority, name="notice_priority_enum"), default=NoticePriority.normal, nullable=False
    )
    status: Mapped[NoticeStatus] = mapped_column(
        Enum(NoticeStatus, name="notice_status_enum"), default=NoticeStatus.draft, nullable=False
    )
    notice_type: Mapped[NoticeType] = mapped_column(
        Enum(NoticeType, name="notice_type_enum"), default=NoticeType.normal, nullable=False
    )

    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # حذف اطلاعیه همیشه Soft-Delete است: رکورد فیزیکی هرگز پاک نمی‌شود (تا آمار
    # بازدید و گزارش‌ها دست‌نخورده بمانند)، فقط از لیست دریافتی مخاطبان کنار
    # گذاشته می‌شود و در گزارش فرستنده/Admin با برچسب «حذف شده» نمایش داده می‌شود.
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    targets: Mapped[list["NoticeTarget"]] = relationship(
        back_populates="notice", cascade="all, delete-orphan"
    )


class NoticeTarget(Base):
    __tablename__ = "notice_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    notice_id: Mapped[int] = mapped_column(ForeignKey("notices.id", ondelete="CASCADE"), nullable=False)

    target_type: Mapped[NoticeTargetType] = mapped_column(
        Enum(NoticeTargetType, name="notice_target_type_enum"), nullable=False
    )
    # برای target_type == "all" مقدار NULL است؛ در غیر این صورت شناسه رکورد مقصد (site/department/role/employee)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    notice: Mapped["Notice"] = relationship(back_populates="targets")
