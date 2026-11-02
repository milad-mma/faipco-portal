"""
درخواست تغییر عکس پرسنلی (آپلود یا حذف) — بعد از تأیید منابع انسانی در جدول عکس کاراوب
(EmployeeExtendedInfo طبق نگاشت سایت) نوشته می‌شود. docs: claude/profile-photo-upload.md
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ProfilePhotoRequest(Base):
    __tablename__ = "profile_photo_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(8), nullable=False)  # upload / delete
    # pending / approved / rejected / cancelled
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    # فقط برای upload: عکس آماده‌ی نوشتن در کاراوب (JPEG زیر ۱۰۰ کیلوبایت) و عکس کوچک GIF ۸۸×۸۸
    image: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    thumbnail: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    image_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_by_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)  # به خود پرسنل نمایش داده می‌شود
