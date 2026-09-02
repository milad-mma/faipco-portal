"""add email delivery fields to backup_settings

Revision ID: 046
Revises: 045
Create Date: 2026-09-01

قابلیت «ارسال بکاپ به ایمیل» - از طریق تنظیمات SMTP سراسری موجود
(smtp_settings، Migration 045). چند گیرنده هم‌زمان پشتیبانی می‌شود (هر
آدرس در یک خط).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "046"
down_revision: Union[str, None] = "045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "backup_settings", sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("backup_settings", sa.Column("email_recipients", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("backup_settings", "email_recipients")
    op.drop_column("backup_settings", "email_enabled")
