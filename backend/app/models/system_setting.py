"""
مدل SystemSetting: ذخیره‌سازی ساده کلید/مقدار برای تنظیماتی که باید بدون
Restart سرور از داخل پنل قابل تغییر باشند (مثلاً فاصله زمانی Sync خودکار).

چرا یک جدول جدا به‌جای اضافه‌کردن ستون به جای دیگر؟ چون این تنظیمات سراسری‌اند
(نه مربوط به یک Site خاص) و ممکن است در آینده موارد بیشتری هم به همین شکل
اضافه شوند — یک جدول Key/Value ساده از تعریف Migration جداگانه برای هر
تنظیم جدید جلوگیری می‌کند.
"""
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
