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

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin


class FeedbackCategory(str, enum.Enum):
    """دسته‌بندی پیام بازخورد."""
    complaint = "complaint"  # انتقاد
    suggestion = "suggestion"  # پیشنهاد
    comment = "comment"  # نظر


class FeedbackStatus(str, enum.Enum):
    """وضعیت پیگیری یک پیام (توسط بازبین دارنده‌ی feedback.reply تغییر می‌کند)."""
    new = "new"  # جدید، هنوز پاسخی ندارد
    in_review = "in_review"  # در دست بررسی
    answered = "answered"  # بازبین پاسخ داده (خودکار با اولین پاسخ)
    closed = "closed"  # بسته؛ فرستنده دیگر نمی‌تواند بنویسد


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
    # گفتگو (Migration 099): وضعیت پیگیری و آخرین زمانی که فرستنده گفتگوی این پیام را دیده
    # (برای نشانگر «پاسخ جدید» خودِ فرستنده؛ به بازبین هرگز نشان داده نمی‌شود)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=FeedbackStatus.new.value, server_default="new")
    sender_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FeedbackReply(Base, TimestampMixin):
    """
    یک پاسخ در گفتگوی یک پیام؛ هر دو طرف (بازبین با مجوز feedback.reply، و فرستنده‌ی پیام) می‌نویسند.
    ناشناس بودن فرستنده در نمایش حفظ می‌شود (feedback_service): پاسخ‌های فرستنده با برچسب «فرستنده» می‌آیند،
    پاسخ‌های بازبین با نام خودش. is_from_sender مستقل از author_user_id ذخیره می‌شود تا با حذف کاربر طرف گفتگو معلوم بماند.
    """

    __tablename__ = "feedback_replies"
    __table_args__ = (Index("ix_feedback_replies_feedback_created", "feedback_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedback_messages.id", ondelete="CASCADE"), nullable=False)
    author_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_from_sender: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # فقط برای پاسخ فرستنده معنا دارد؛ مثل پیام اصلی، در لحظه‌ی ثبت محاسبه می‌شود و روی پیام اصلی هم اثر می‌گذارد
    contains_profanity: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ProhibitedPhrase(Base, TimestampMixin):
    """
    یک کلمه/عبارت نامناسب. فقط Admin واقعی (superuser) می‌تواند این فهرست را مدیریت کند
    (نه دارنده مجوز feedback.view/view_all)، چون این فهرست تعیین می‌کند چه زمانی
    محرمانگی پیام برای همان دارنده مجوز شکسته شود.
    """

    __tablename__ = "prohibited_phrases"

    id: Mapped[int] = mapped_column(primary_key=True)
    phrase: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
