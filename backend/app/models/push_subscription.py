"""
مدل PushSubscription: هر دستگاه/مرورگری که کاربر روی آن «فعال‌سازی اعلان» را زده،
یک رکورد اینجا دارد. اطلاعات endpoint/p256dh/auth همان چیزی است که
Web Push API مرورگر برمی‌گرداند و برای ارسال بعدی Push به همان دستگاه لازم است.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class PushSubscription(Base):
    """اشتراک Web Push یک دستگاه/مرورگر برای یک کاربر؛ endpoint یکتاست."""
    __tablename__ = "push_subscriptions"
    __table_args__ = (UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    endpoint: Mapped[str] = mapped_column(Text, nullable=False)  # آدرس سرویس Push مرورگر برای این دستگاه
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)  # کلید عمومی رمزنگاری payload
    auth: Mapped[str] = mapped_column(String(255), nullable=False)  # رمز احراز هویت اشتراک

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship()
