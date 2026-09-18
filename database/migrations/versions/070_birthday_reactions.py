"""add birthday reactions

Revision ID: 070
Revises: 069
Create Date: 2026-09-18

طبق درخواست صریح کاربر: پرسنل می‌توانند برای همکاری که امروز روز تولدش
است، یک ایموجی تبریک ثبت کنند و فهرست کسانی که تبریک گفته‌اند (با نام و
واحد سازمانی) قابل‌مشاهده باشد.

کلید یکتای (reactor_user_id, birthday_employee_id, jalali_year):
    - «هر فرد یک ری‌اکشن» را در سطح خودِ دیتابیس تضمین می‌کند، نه فقط در
      کد - که با درخواست‌های هم‌زمان قابل دور زدن بود.
    - jalali_year در کلید هست تا ری‌اکشن‌های سال‌های مختلف با هم قاطی
      نشوند؛ سال بعد همان فرد دوباره می‌تواند تبریک بگوید.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "070"
down_revision: Union[str, None] = "069"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "birthday_reactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "reactor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "birthday_employee_id",
            sa.Integer(),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("jalali_year", sa.Integer(), nullable=False),
        sa.Column(
            "emoji",
            sa.Enum("party", "cake", "white_heart", "blue_heart", name="birthday_reaction_emoji"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "reactor_user_id",
            "birthday_employee_id",
            "jalali_year",
            name="uq_birthday_reaction_per_year",
        ),
    )
    op.create_index("ix_birthday_reactions_reactor_user_id", "birthday_reactions", ["reactor_user_id"])
    op.create_index(
        "ix_birthday_reactions_birthday_employee_id", "birthday_reactions", ["birthday_employee_id"]
    )
    op.create_index("ix_birthday_reactions_jalali_year", "birthday_reactions", ["jalali_year"])


def downgrade() -> None:
    op.drop_index("ix_birthday_reactions_jalali_year", table_name="birthday_reactions")
    op.drop_index("ix_birthday_reactions_birthday_employee_id", table_name="birthday_reactions")
    op.drop_index("ix_birthday_reactions_reactor_user_id", table_name="birthday_reactions")
    op.drop_table("birthday_reactions")
    sa.Enum(name="birthday_reaction_emoji").drop(op.get_bind(), checkfirst=True)
