"""
مدل «ری‌اکشن تبریک تولد» — پرسنل می‌توانند برای همکاری که امروز روز
تولدش است، یک ایموجی تبریک ثبت کنند.

⚠️ چند تصمیم طراحی مهم (طبق تصمیم صریح کاربر):
    - هر فرد برای هر متولد، فقط **یک** ری‌اکشن دارد (نه چند تا) - با
      کلیک روی ایموجی دیگر، ری‌اکشن قبلی جایگزین می‌شود.
    - ری‌اکشن به یک **تاریخ مشخص** گره می‌خورد (jalali_year)، نه فقط به
      شخص - وگرنه سال بعد، ری‌اکشن‌های پارسال هم نمایش داده می‌شدند.
    - خودِ متولد نمی‌تواند به تولد خودش ری‌اکشن بزند (در لایه سرویس
      اعتبارسنجی می‌شود).
"""
from __future__ import annotations

import enum

from sqlalchemy import Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin


class BirthdayReactionEmoji(str, enum.Enum):
    """
    ⚠️ فهرست بسته و ثابت - عمداً ایموجی دلخواه پذیرفته نمی‌شود. هر کدام
    معنای مشخصی در فضای اداری دارند که در UI هم به کاربر نمایش داده
    می‌شود (تا انتخاب آگاهانه باشد، نه سلیقه‌ای).
    """

    party = "party"  # 🎉 تبریک پرانرژی و ایجاد نشاط تیمی
    cake = "cake"  # 🎂 استانداردترین تبریک اداری، رسمی و خنثی
    white_heart = "white_heart"  # 🤍 احترام، پاکی و آرزوی سلامتی
    blue_heart = "blue_heart"  # 💙 وفاداری سازمانی و روحیه تیمی


class BirthdayReaction(Base, TimestampMixin):
    __tablename__ = "birthday_reactions"
    __table_args__ = (
        # ⚠️ کلید یکتا: هر کاربر برای هر متولد در هر سال، فقط یک ردیف -
        # تضمین «یک ری‌اکشن به ازای هر نفر» در سطح خودِ دیتابیس، نه فقط
        # در کد (که با درخواست‌های هم‌زمان قابل دور زدن بود).
        UniqueConstraint(
            "reactor_user_id",
            "birthday_employee_id",
            "jalali_year",
            name="uq_birthday_reaction_per_year",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reactor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    birthday_employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # سال شمسیِ همان روز تولد - تا ری‌اکشن‌های سال‌های مختلف با هم قاطی نشوند
    jalali_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    emoji: Mapped[BirthdayReactionEmoji] = mapped_column(
        Enum(BirthdayReactionEmoji, name="birthday_reaction_emoji"), nullable=False
    )
