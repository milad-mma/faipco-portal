"""Durable dispatch metadata. No endpoint URLs, credentials or receipt content."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class PushDispatchJob(Base):
    __tablename__ = "push_dispatch_jobs"
    __table_args__ = (Index("ix_push_dispatch_jobs_due", "origin", "status", "next_attempt_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    origin: Mapped[str] = mapped_column(String(255), nullable=False)
    notice_id: Mapped[int | None] = mapped_column(ForeignKey("notices.id", ondelete="CASCADE"), nullable=True, index=True)
    user_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    notice_type: Mapped[str] = mapped_column(String(30), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    initialized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    target_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    no_device_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(120), nullable=True)


class PushDispatchDelivery(Base):
    __tablename__ = "push_dispatch_deliveries"
    __table_args__ = (
        UniqueConstraint("job_id", "subscription_id", "session_id", name="uq_push_dispatch_job_subscription"),
        Index("ix_push_dispatch_deliveries_due", "job_id", "status", "next_attempt_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("push_dispatch_jobs.id", ondelete="CASCADE"), nullable=False)
    # Historical IDs intentionally have no FK: revoking a session must not erase delivery history.
    subscription_id: Mapped[int] = mapped_column(Integer, nullable=False)
    session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(120), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OfficePushReceipt(Base):
    __tablename__ = "oa_push_receipts"
    event_id: Mapped[int] = mapped_column(ForeignKey("oa_notification_outbox.id", ondelete="CASCADE"), primary_key=True)
    subscription_id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
