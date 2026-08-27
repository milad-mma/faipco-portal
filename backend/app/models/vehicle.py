"""
مدل Vehicle: خودروهای ثبت‌شده توسط پرسنل (قابلیت «خودروهای من»).

هر پرسنل می‌تواند یک یا چند خودرو برای خودش ثبت کند. پلاک ایرانی در چهار
بخش جدا ذخیره می‌شود (نه یک رشته واحد) — دقیقاً منطبق با ساختار واقعی پلاک
ایران، و برای این‌که فرانت‌اند بتواند ورودی گرافیکی پلاک را دقیقاً بازسازی
کند (نه فقط یک متن آزاد که ممکن است فرمتش نادرست باشد).

فرمت واقعی پلاک ایران: [۲ رقم] [یک حرف فارسی] [۳ رقم] — ایران [۲ رقم]
مثال: ۱۲ ب ۳۴۵ ایران ۶۷
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )

    vehicle_type: Mapped[str] = mapped_column(String(100), nullable=False)  # نوع/مدل خودرو (مثلاً پراید، ۲۰۶)
    color: Mapped[str] = mapped_column(String(50), nullable=False)  # رنگ خودرو

    # پلاک ایرانی — چهار بخش جدا، دقیقاً مطابق فرمت واقعی
    plate_digits1: Mapped[str] = mapped_column(String(2), nullable=False)  # ۲ رقم سمت راست
    plate_letter: Mapped[str] = mapped_column(String(1), nullable=False)  # حرف فارسی وسط
    plate_digits2: Mapped[str] = mapped_column(String(3), nullable=False)  # ۳ رقم سمت چپ حرف
    plate_iran_code: Mapped[str] = mapped_column(String(2), nullable=False)  # ۲ رقم کد ایران (سمت چپ پلاک)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    employee: Mapped["Employee"] = relationship()
