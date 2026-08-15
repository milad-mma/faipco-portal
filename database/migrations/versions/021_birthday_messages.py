"""add birthday_message_templates table (پیام‌های تبریک تولد — ارسال خودکار تصادفی)

Revision ID: 021
Revises: 020
Create Date: 2026-08-16

پول متن‌های آماده تبریک تولد که مدیر منابع انسانی (و ادمین) مدیریت می‌کنند.
هر روز، در ساعتی که تنظیم شده (system_settings key: birthday_send_time)،
یک متن تصادفی از این پول برای هر پرسنلی که امروز تولدش است فرستاده می‌شود.
اگر این جدول خالی باشد، هیچ پیامی فرستاده نمی‌شود (رفتار پیش‌فرض امن).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "birthday_message_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("birthday_message_templates")
