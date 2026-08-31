from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FeedbackSubmitIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1, max_length=5000)
    is_anonymous: bool = False


class FeedbackMessageOut(BaseModel):
    """
    sender_name/sender_id عمداً Optional هستند - بسته به این‌که بیننده
    (Admin واقعی یا دارنده مجوز feedback.view/view_all) اجازه دیدن فرستنده
    این پیام مشخص را دارد یا نه، این‌ها یا پر می‌شوند یا None می‌مانند
    (توسط feedback_service.py، نه اینجا).
    """

    id: int
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
    phrase: str = Field(min_length=1, max_length=256)


class ProhibitedPhraseOut(BaseModel):
    id: int
    phrase: str

    model_config = ConfigDict(from_attributes=True)
