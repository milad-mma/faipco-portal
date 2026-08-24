"""add hide_birthday_in_dashboard to employees

Revision ID: 031
Revises: 030
Create Date: 2026-08-24

فقط روی کارت «متولدین امروز» در داشبورد شخصی پرسنل اثر دارد — نه پنل Admin،
نه ابزار ارسال پیام تبریک تولد. دقیقاً مثل is_enabled، Sync Engine هرگز
این ستون را نمی‌خواند/نمی‌نویسد.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column("hide_birthday_in_dashboard", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("employees", "hide_birthday_in_dashboard")
