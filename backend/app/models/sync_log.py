"""
تاریخچه اجرای Sync برای هر Site — در پنل «Sync Management» برای نمایش
خطاها و آمار هر اجرا استفاده می‌شود.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class SyncRunStatus(str, enum.Enum):
    """وضعیت یک اجرای Sync: در حال اجرا، موفق، ناموفق یا نیمه‌موفق (partial)."""

    running = "running"
    success = "success"
    failed = "failed"
    partial = "partial"


class SyncLog(Base):
    """یک رکورد به‌ازای هر اجرای Sync یک سایت، با زمان شروع/پایان، وضعیت و آمار تغییرات."""

    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # تا پایان اجرا NULL است

    status: Mapped[SyncRunStatus] = mapped_column(
        Enum(SyncRunStatus, name="sync_run_status_enum"), default=SyncRunStatus.running, nullable=False
    )

    inserted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # پرسنل جدید اضافه‌شده
    updated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # پرسنل موجود به‌روزشده
    deactivated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # پرسنل فعالی که در این اجرا غیرفعال شدند
    # پرسنلی که در همین اجرا Import نشدند چون در منبع از قبل غیرفعال/کات بودند
    # (پرسنل فعالی که در این اجرا کات شده‌اند در deactivated_count شمرده می‌شوند)
    skipped_inactive_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # پرسنلی که واحدشان زیر هیچ ریشه‌ای از سایت‌های هم‌منبع نیست و وارد نشدند
    skipped_unassigned_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # پرسنلی که در این اجرا از سایت دیگری به این سایت منتقل شدند
    transferred_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # هشدارهای غیرخطای اجرا (مثلاً فهرست واحدهای بی‌سایت)
    warning_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    site: Mapped["Site"] = relationship()
