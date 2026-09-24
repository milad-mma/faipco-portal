"""
مدل «ری‌اکشن تبریک تولد»: پرسنل می‌توانند برای همکاری که امروز روز
تولدش است، یک ایموجی تبریک ثبت کنند.

قواعد:
    - هر فرد برای هر متولد فقط یک ری‌اکشن دارد؛ انتخاب ایموجی دیگر،
      ری‌اکشن قبلی را جایگزین می‌کند.
    - ری‌اکشن به سال شمسی تولد (jalali_year) گره می‌خورد تا ری‌اکشن‌های
      سال‌های قبل در سال بعد نمایش داده نشوند.
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
    فهرست بسته و ثابت ایموجی‌های مجاز؛ ایموجی دلخواه پذیرفته نمی‌شود.
    معنای هر کدام در UI به کاربر نمایش داده می‌شود.
    """

    party = "party"  # 🎉 تبریک پرانرژی و ایجاد نشاط تیمی
    cake = "cake"  # 🎂 استانداردترین تبریک اداری، رسمی و خنثی
    white_heart = "white_heart"  # 🤍 احترام، پاکی و آرزوی سلامتی
    blue_heart = "blue_heart"  # 💙 وفاداری سازمانی و روحیه تیمی


class BirthdayReaction(Base, TimestampMixin):
    """یک ری‌اکشن ثبت‌شده: چه کاربری، برای تولد کدام پرسنل، در کدام سال، با چه ایموجی."""
    __tablename__ = "birthday_reactions"
    __table_args__ = (
        # کلید یکتا: هر کاربر برای هر متولد در هر سال فقط یک ردیف دارد؛
        # این قاعده در سطح دیتابیس تضمین می‌شود تا درخواست‌های هم‌زمان هم نتوانند آن را دور بزنند.
        UniqueConstraint(
            "reactor_user_id",
            "birthday_employee_id",
            "jalali_year",
            name="uq_birthday_reaction_per_year",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # کاربری که ری‌اکشن را ثبت کرده
    reactor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # پرسنلی که تولدش است
    birthday_employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # سال شمسیِ همان روز تولد - تا ری‌اکشن‌های سال‌های مختلف با هم قاطی نشوند
    jalali_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    emoji: Mapped[BirthdayReactionEmoji] = mapped_column(
        Enum(BirthdayReactionEmoji, name="birthday_reaction_emoji"), nullable=False
    )
