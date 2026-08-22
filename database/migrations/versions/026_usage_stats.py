"""add usage_stats table (نمودار میزان استفاده از پرتال در پنل Admin)

Revision ID: 026
Revises: 025
Create Date: 2026-08-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usage_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("date", "hour", name="uq_usage_stats_date_hour"),
    )
    op.create_index("ix_usage_stats_date", "usage_stats", ["date"])


def downgrade() -> None:
    op.drop_index("ix_usage_stats_date", table_name="usage_stats")
    op.drop_table("usage_stats")
