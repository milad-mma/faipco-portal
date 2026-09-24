"""
مدل‌های «انتقادات و پیشنهادات»: پیام‌هایی که پرسنل می‌فرستند (با امکان
درخواست ناشناس‌ماندن) و فهرست کلمات/عبارات نامناسب که تعیین می‌کند یک
پیام از حالت محرمانه/ناشناس خارج شود یا نه.

منطق محرمانگی (پیاده‌سازی در feedback_service.py):
    - Admin واقعی (is_superuser) از پنل ادمین: همیشه فرستنده واقعی همه
      پیام‌ها را می‌بیند - صرف‌نظر از درخواست ناشناس‌ماندن - و می‌بیند
      که کاربر تیک ناشناس را زده یا نه.
    - هر نقش دیگری با مجوز feedback.view (سایت‌محور) یا feedback.view_all
      (سراسری): اگر is_anonymous_requested=True و contains_profanity=False
      باشد، فرستنده برایش نمایش داده نمی‌شود؛ اگر پیام حاوی الفاظ نامناسب
      باشد، فرستنده کاملاً قابل‌مشاهده می‌شود.
"""
from __future__ import annotations

import enum

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin


class FeedbackCategory(str, enum.Enum):
    """دسته‌بندی پیام بازخورد."""
    complaint = "complaint"  # انتقاد
    suggestion = "suggestion"  # پیشنهاد
    comment = "comment"  # نظر


class FeedbackMessage(Base, TimestampMixin):
    """یک پیام انتقاد/پیشنهاد/نظر ارسال‌شده توسط یک کاربر."""
    __tablename__ = "feedback_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    # فرستنده همیشه ثبت می‌شود (حتی اگر ناشناس درخواست شده) تا Admin واقعی
    # همیشه آن را ببیند و در صورت وجود الفاظ نامناسب، هویت برای دارنده مجوز هم آشکار شود.
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[FeedbackCategory] = mapped_column(
        Enum(FeedbackCategory, name="feedback_category"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_anonymous_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # کاربر تیک «ناشناس» را زده است
    # در لحظه ارسال، بر اساس فهرست ProhibitedPhrase همان لحظه محاسبه و
    # ذخیره می‌شود (نه در زمان نمایش)؛ تغییرات بعدی فهرست روی پیام‌های
    # ارسال‌شده اثر نمی‌گذارد.
    contains_profanity: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # حذف نرم: رکورد از دیتابیس پاک نمی‌شود، فقط علامت‌گذاری شده و از
    # فهرست‌ها کنار می‌رود؛ داده باقی می‌ماند و قابل‌بازیابی است.
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # کاربری که پیام را حذف (نرم) کرده است
    deleted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ProhibitedPhrase(Base, TimestampMixin):
    """
    یک کلمه/عبارت نامناسب. فقط Admin واقعی (superuser) می‌تواند این فهرست را مدیریت کند
    (نه دارنده مجوز feedback.view/view_all)، چون این فهرست تعیین می‌کند چه زمانی
    محرمانگی پیام برای همان دارنده مجوز شکسته شود.
    """

    __tablename__ = "prohibited_phrases"

    id: Mapped[int] = mapped_column(primary_key=True)
    phrase: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
