"""
Schema های «انتقادات و پیشنهادات»: ثبت پیام، خروجی پیام برای بیننده‌ها،
فهرست صفحه‌بندی‌شده و مدیریت عبارات نامناسب (مورد استفاده در endpointهای /feedback).
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.feedback import FeedbackCategory


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

    model_config = ConfigDict(from_attributes=True)


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
