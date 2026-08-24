"""add notice archives tracking

Revision ID: 030
Revises: 029
Create Date: 2026-08-24

جدول notice_archives — دقیقاً هم‌الگو با notice_reads (migration 006):
آرشیو کاملاً شخصی/به‌ازای هر کاربر است، نه یک وضعیت سراسری روی خودِ Notice.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "030"
down_revision: Union[str, None] = "029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notice_archives",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("notice_id", sa.Integer(), sa.ForeignKey("notices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("notice_id", "user_id", name="uq_notice_archive_once"),
    )
    op.create_index("ix_notice_archives_user_id", "notice_archives", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_notice_archives_user_id", table_name="notice_archives")
    op.drop_table("notice_archives")
