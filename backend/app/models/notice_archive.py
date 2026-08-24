"""
مدل NoticeArchive: ثبت این‌که کدام کاربر، کدام اطلاعیه را آرشیو کرده.

دقیقاً هم‌الگو با NoticeRead — وجود یک ردیف یعنی «این کاربر این اطلاعیه را
آرشیو کرده»، نبودش یعنی آرشیو نشده. آرشیو کاملاً شخصی/به‌ازای هر کاربر است
(نه یک وضعیت سراسری روی خودِ Notice) — یعنی اگر یک اطلاعیه به چند نفر
رسیده، هرکدام مستقل می‌توانند آرشیوش کنند یا نکنند، بدون تأثیر روی بقیه.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class NoticeArchive(Base):
    __tablename__ = "notice_archives"
    __table_args__ = (UniqueConstraint("notice_id", "user_id", name="uq_notice_archive_once"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    notice_id: Mapped[int] = mapped_column(ForeignKey("notices.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship()
