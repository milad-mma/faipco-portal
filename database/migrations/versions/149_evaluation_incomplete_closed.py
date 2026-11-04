"""دوره‌ی ارزیابی: «بستن ارزیابی‌های انجام‌نشده» (غیرفعال‌سازی جزئی؛ نتایج ثبت‌شده برای پرسنل می‌ماند)

Revision ID: 149
Revises: 148
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "149"
down_revision: Union[str, None] = "148"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evaluation_periods",
        sa.Column("incomplete_closed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("evaluation_periods", "incomplete_closed")
