"""مساعده: قانون «در ماه شروع به کار درخواست ممکن نیست» قابل فعال/غیرفعال‌سازی برای هر سایت

Revision ID: 125
Revises: 124

پیش‌فرض روشن (همان رفتار فعلی).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "125"
down_revision: Union[str, None] = "124"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "advance_settings",
        sa.Column("block_hire_month", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("advance_settings", "block_hire_month")
