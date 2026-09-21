"""evaluation_periods.is_disabled

Revision ID: 080
Revises: 079
Create Date: 2026-09-20

طبق درخواست کاربر: ارزیابی‌های منتشرشده یک دوره قابل غیرفعال‌شدن باشند تا
دیگر برای ارزیاب‌ها و پرسنل در دسترس نباشند (برگشت‌پذیر).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "080"
down_revision: Union[str, None] = "079"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evaluation_periods",
        sa.Column("is_disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("evaluation_periods", "is_disabled")
