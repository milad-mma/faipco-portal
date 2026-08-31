"""
مدل‌های «انتقادات و پیشنهادات» — پیام‌هایی که پرسنل می‌فرستند (با امکان
درخواست ناشناس‌ماندن)، و فهرست کلمات/عبارات نامناسب که تعیین می‌کند یک
پیام از حالت محرمانه/ناشناس خارج شود یا نه.

منطق محرمانگی (پیاده‌سازی در feedback_service.py، نه اینجا):
    - Admin واقعی (is_superuser) از پنل ادمین: همیشه فرستنده واقعی همه
      پیام‌ها را می‌بیند - صرف‌نظر از درخواست ناشناس‌ماندن - ولی می‌بیند
      که کاربر تیک ناشناس را زده یا نه.
    - هر نقش دیگری با مجوز feedback.view (سایت‌محور) یا feedback.view_all
      (سراسری): اگر is_anonymous_requested=True و contains_profanity=False
      باشد، فرستنده برایش نمایش داده نمی‌شود؛ در غیر این صورت (پیام حاوی
      الفاظ نامناسب بود)، فرستنده کاملاً قابل‌مشاهده می‌شود.
"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin


class FeedbackMessage(Base, TimestampMixin):
    __tablename__ = "feedback_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    # فرستنده همیشه ثبت می‌شود (حتی اگر ناشناس درخواست شده) - چون Admin
    # واقعی همیشه باید بتواند ببیند، و اگر پیام حاوی الفاظ نامناسب باشد،
    # باید بتوان هویت را برای دارنده مجوز هم آشکار کرد.
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_anonymous_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # در لحظه ارسال، بر اساس فهرست ProhibitedPhrase همان لحظه محاسبه و
    # ذخیره می‌شود (نه هر بار در زمان نمایش) - یعنی اگر بعداً یک عبارت به
    # فهرست اضافه/حذف شود، روی پیام‌های قبلاً ارسال‌شده اثر نمی‌گذارد.
    contains_profanity: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ProhibitedPhrase(Base, TimestampMixin):
    """
    فهرست کلمات/عبارات نامناسب - فقط توسط Admin واقعی (superuser) قابل‌مدیریت
    است (نه حتی دارنده مجوز feedback.view/view_all)، چون این فهرست مستقیماً
    تعیین می‌کند چه زمانی محرمانگی یک پیام برای همان دارنده مجوز شکسته
    می‌شود - اگر خودِ او می‌توانست این فهرست را ویرایش کند، می‌توانست
    عملاً محرمانگی را برای پیام‌های دلخواه دور بزند.
    """

    __tablename__ = "prohibited_phrases"

    id: Mapped[int] = mapped_column(primary_key=True)
    phrase: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
