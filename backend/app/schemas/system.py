"""Schema های مربوط به تنظیمات کلی سیستم (پنل Admin → System)."""
from __future__ import annotations

import ipaddress
from datetime import datetime

from pydantic import BaseModel, field_validator


class IpAllowlistEntryIn(BaseModel):
    cidr: str
    label: str | None = None

    @field_validator("cidr")
    @classmethod
    def validate_cidr(cls, value: str) -> str:
        value = value.strip()
        try:
            ipaddress.ip_network(value, strict=False)
        except ValueError as e:
            raise ValueError(
                'فرمت IP/رنج نامعتبر است — مثال درست: "203.0.113.5/32" (یک IP تکی) یا "192.168.1.0/24" (یک رنج)'
            ) from e
        return value


class IpAllowlistEntryOut(BaseModel):
    id: int
    cidr: str
    label: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class IpAllowlistBulkImportIn(BaseModel):
    """متن خام (مثلاً محتوای یک فایل txt/لاگ Copy-Paste شده) — هر چیزی که شبیه
    IP یا CIDR باشد استخراج می‌شود؛ چون همیشه امکان تشخیص اشتباه وجود دارد
    (مثلاً یک عدد نسخه مرورگر شبیه IP)، این فقط استخراج/پیش‌نمایش است، هنوز
    چیزی ذخیره نمی‌شود — کاربر باید فهرست را ببیند و تأیید کند."""

    text: str


class IpAllowlistCandidate(BaseModel):
    cidr: str
    already_exists: bool


class IpAllowlistExtractResult(BaseModel):
    candidates: list[IpAllowlistCandidate]


class IpAllowlistBulkAddIn(BaseModel):
    """فهرست نهایی CIDR هایی که کاربر بعد از دیدن پیش‌نمایش تأیید کرده."""

    cidrs: list[str]
    label: str | None = None


class IpAllowlistBulkAddResult(BaseModel):
    added: list[IpAllowlistEntryOut]
    added_count: int
    duplicate_count: int


class IpBlockedMessageIn(BaseModel):
    message: str


class IpBlockedMessageOut(BaseModel):
    message: str
