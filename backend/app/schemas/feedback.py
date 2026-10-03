"""
Schema های «انتقادات و پیشنهادات»: ثبت پیام، خروجی پیام برای بیننده‌ها،
فهرست صفحه‌بندی‌شده و مدیریت عبارات نامناسب (مورد استفاده در endpointهای /feedback).
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.feedback import FeedbackCategory, FeedbackStatus


class FeedbackSubmitIn(BaseModel):
    """ورودی POST /feedback برای ارسال پیام توسط کاربر."""
    category: FeedbackCategory
    title: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1, max_length=5000)
    is_anonymous: bool = False  # درخواست ناشناس‌ماندن فرستنده


class FeedbackMessageOut(BaseModel):
    """
    یک پیام در خروجی GET /feedback. فیلدهای sender_name/sender_id اختیاری‌اند:
    بسته به این‌که بیننده (Admin واقعی یا دارنده مجوز feedback.view/view_all) اجازه دیدن
    فرستنده این پیام را دارد یا نه، feedback_service.py آن‌ها را پر می‌کند یا None می‌گذارد.
    """

    id: int
    category: FeedbackCategory
    title: str | None = None
    message: str
    is_anonymous_requested: bool
    contains_profanity: bool
    created_at: datetime
    sender_id: int | None = None
    sender_name: str | None = None
    site_id: int | None = None
    site_name: str | None = None
    # گفتگو
    status: FeedbackStatus = FeedbackStatus.new
    reply_count: int = 0
    last_reply_at: datetime | None = None
    awaiting_reviewer: bool = False  # آخرین نوشته از فرستنده است (یا پیام هنوز پاسخی ندارد) → بازبین باید اقدام کند
    can_reply: bool = False  # بیننده مجوز feedback.reply برای سایت این پیام دارد

    model_config = ConfigDict(from_attributes=True)


class FeedbackReplyIn(BaseModel):
    """بدنه‌ی ثبت پاسخ (بازبین: POST /feedback/{id}/replies — فرستنده: POST /feedback/mine/{id}/replies)."""
    body: str = Field(min_length=1, max_length=5000)

    @field_validator("body")
    @classmethod
    def _strip_body(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("متن پاسخ خالی است")
        return text


class FeedbackReplyOut(BaseModel):
    """
    یک پاسخ در گفتگو. برای پاسخ فرستنده، author_name فقط وقتی پر است که بیننده اجازه‌ی دیدن هویت او را دارد
    (superuser، پیام غیرناشناس، یا آشکارشده با الفاظ نامناسب)؛ وگرنه None و فرانت‌اند «فرستنده» نشان می‌دهد.
    پاسخ بازبین همیشه با نام خودش می‌آید.
    """
    id: int
    is_from_sender: bool
    is_mine: bool  # نویسنده همین بیننده است (برای چیدمان چپ/راست)
    author_name: str | None = None
    body: str
    created_at: datetime


class FeedbackThreadOut(BaseModel):
    """خروجی گفتگوی یک پیام: پیام اصلی (با قواعد محرمانگی بیننده) + پاسخ‌ها به ترتیب زمان."""
    message: FeedbackMessageOut
    replies: list[FeedbackReplyOut]


class FeedbackStatusIn(BaseModel):
    """بدنه‌ی PUT /feedback/{id}/status (بازبین با feedback.reply)؛ answered فقط خودکار با پاسخ تنظیم می‌شود."""
    status: FeedbackStatus


class MyFeedbackItemOut(BaseModel):
    """یک پیام خودِ کاربر در GET /feedback/mine (بدون فیلدهای هویتی، چون صاحب پیام است)."""
    id: int
    category: FeedbackCategory
    title: str | None = None
    message: str
    is_anonymous_requested: bool
    status: FeedbackStatus
    created_at: datetime
    reply_count: int = 0
    last_reply_at: datetime | None = None
    has_new_reply: bool = False  # پاسخ بازبین بعد از آخرین مشاهده‌ی فرستنده


class ProhibitedPhraseIn(BaseModel):
    """ورودی POST /feedback/prohibited-phrases برای افزودن عبارت نامناسب."""
    phrase: str = Field(min_length=1, max_length=256)


class ProhibitedPhraseOut(BaseModel):
    """خروجی فهرست و افزودن عبارات نامناسب در /feedback/prohibited-phrases."""
    id: int
    phrase: str

    model_config = ConfigDict(from_attributes=True)


class FeedbackListOut(BaseModel):
    """خروجی صفحه‌بندی‌شده GET /feedback (فهرست انتقادات/پیشنهادات)."""

    items: list[FeedbackMessageOut]
    total: int
    page: int
    page_size: int
