"""add notice reads tracking

Revision ID: 006
Revises: 005
Create Date: 2026-08-03

جدول notice_reads برای ثبت مشاهده هر اطلاعیه توسط هر کاربر — پایه گزارش‌های
«چه کسانی دیدند» برای فرستنده و Admin.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notice_reads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("notice_id", sa.Integer(), sa.ForeignKey("notices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("notice_id", "user_id", name="uq_notice_read_once"),
    )


def downgrade() -> None:
    op.drop_table("notice_reads")
