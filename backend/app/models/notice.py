"""
مدل‌های سیستم اطلاعیه سازمانی.

Notice: خود اطلاعیه (عنوان، متن، اولویت، وضعیت، نوع، زمان انتشار/انقضا).
NoticeTarget: مخاطب اطلاعیه — یک اطلاعیه می‌تواند چند Target داشته باشد
  (مثلاً هم به یک Site و هم به یک Role خاص ارسال شود).
  target_id بسته به target_type به یکی از جداول sites/departments/roles/employees اشاره دارد
  (Polymorphic ساده - بدون FK مستقیم چون به چند جدول مختلف اشاره می‌کند).
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class NoticePriority(str, enum.Enum):
    """سطح اولویت اطلاعیه."""
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class NoticeStatus(str, enum.Enum):
    """وضعیت چرخه عمر اطلاعیه: پیش‌نویس، منتشرشده، منقضی."""
    draft = "draft"
    published = "published"
    expired = "expired"


class NoticeTargetType(str, enum.Enum):
    """نوع مخاطب اطلاعیه؛ مشخص می‌کند target_id به کدام جدول اشاره دارد."""
    all = "all"
    site = "site"
    department = "department"
    role = "role"
    employee = "employee"


class NoticeType(str, enum.Enum):
    """
    normal          → اطلاعیه متنی معمولی.
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
    """یک اطلاعیه سازمانی به همراه فهرست مخاطبانش (targets)."""
    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # فقط برای اطلاعیه‌های نوع attendance_card: زیرعنوان ماه/سال که روی خودِ
    # کارت PDF چاپ می‌شود (مثلاً «تیر ماه 1405») — از title جدا است،
    # چون title برای نمایش در لیست اطلاعیه‌های دریافتی است.
    card_subtitle: Mapped[str | None] = mapped_column(String(128), nullable=True)

    priority: Mapped[NoticePriority] = mapped_column(
        Enum(NoticePriority, name="notice_priority_enum"), default=NoticePriority.normal, nullable=False
    )
    status: Mapped[NoticeStatus] = mapped_column(
        Enum(NoticeStatus, name="notice_status_enum"), default=NoticeStatus.draft, nullable=False, index=True
    )
    notice_type: Mapped[NoticeType] = mapped_column(
        Enum(NoticeType, name="notice_type_enum"), default=NoticeType.normal, nullable=False
    )

    # زمان شروع نمایش و زمان انقضا؛ NULL یعنی بدون محدودیت
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # حذف اطلاعیه همیشه Soft-Delete است: رکورد فیزیکی هرگز پاک نمی‌شود (تا آمار
    # بازدید و گزارش‌ها دست‌نخورده بمانند)، فقط از لیست دریافتی مخاطبان کنار
    # گذاشته می‌شود و در گزارش فرستنده/Admin با برچسب «حذف شده» نمایش داده می‌شود.
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    targets: Mapped[list["NoticeTarget"]] = relationship(
        back_populates="notice", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["NoticeAttachment"]] = relationship(
        back_populates="notice", cascade="all, delete-orphan", order_by="NoticeAttachment.id", passive_deletes=True
    )


class NoticeTarget(Base):
    """یک مخاطب اطلاعیه (همه / سایت / دپارتمان / نقش / پرسنل)."""
    __tablename__ = "notice_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    notice_id: Mapped[int] = mapped_column(
        ForeignKey("notices.id", ondelete="CASCADE"), nullable=False, index=True
    )

    target_type: Mapped[NoticeTargetType] = mapped_column(
        Enum(NoticeTargetType, name="notice_target_type_enum"), nullable=False
    )
    # برای target_type == "all" مقدار NULL است؛ در غیر این صورت شناسه رکورد مقصد (site/department/role/employee)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    notice: Mapped["Notice"] = relationship(back_populates="targets")


class NoticeAttachment(Base):
    """
    پیوست تصویر/PDF اطلاعیه‌ی متنی (Migration 103؛ فقط با مجوز notices.attachments).
    فقط تا پیش از انتشار اضافه/حذف می‌شود. بایت‌ها deferred اند تا فهرست‌ها سبک بمانند (فقط endpoint دانلود می‌خواند).
    """
    __tablename__ = "notice_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    notice_id: Mapped[int] = mapped_column(ForeignKey("notices.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(160), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    notice: Mapped["Notice"] = relationship(back_populates="attachments")
