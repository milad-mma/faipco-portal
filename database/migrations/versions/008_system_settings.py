"""add system_settings table

Revision ID: 008
Revises: 007
Create Date: 2026-08-09

جدول کلید/مقدار ساده برای تنظیماتی که باید بدون Restart سرور و بدون ویرایش
دستی .env، از داخل پنل قابل تغییر باشند. اولین استفاده: فاصله زمانی Sync
خودکار (sync_interval_minutes) — اگر رکوردی برای یک کلید وجود نداشته باشد،
مقدار پیش‌فرض همان از .env خوانده می‌شود (سازگار با نصب‌های قبلی).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("value", sa.String(length=500), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
