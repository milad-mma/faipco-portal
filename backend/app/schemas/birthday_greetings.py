"""Schema های مربوط به «پیام‌های تبریک تولد»."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BirthdayTemplateIn(BaseModel):
    text: str


class BirthdayTemplateOut(BaseModel):
    id: int
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BirthdaySendTimeIn(BaseModel):
    hour: int
    minute: int


class BirthdaySendTimeOut(BaseModel):
    hour: int
    minute: int


class BirthdayEnabledIn(BaseModel):
    enabled: bool


class BirthdayEnabledOut(BaseModel):
    enabled: bool
