"""add server_stats table (نمودار مصرف CPU/RAM/دیسک سرور در پنل Admin)

Revision ID: 027
Revises: 026
Create Date: 2026-08-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "server_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cpu_percent", sa.Float(), nullable=False),
        sa.Column("ram_percent", sa.Float(), nullable=False),
        sa.Column("ram_used_mb", sa.Integer(), nullable=False),
        sa.Column("ram_total_mb", sa.Integer(), nullable=False),
        sa.Column("disk_percent", sa.Float(), nullable=False),
        sa.Column("disk_used_gb", sa.Float(), nullable=False),
        sa.Column("disk_total_gb", sa.Float(), nullable=False),
    )
    op.create_index("ix_server_stats_recorded_at", "server_stats", ["recorded_at"])


def downgrade() -> None:
    op.drop_index("ix_server_stats_recorded_at", table_name="server_stats")
    op.drop_table("server_stats")
