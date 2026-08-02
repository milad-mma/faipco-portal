"""add is_active_inverted flag

Revision ID: 005
Revises: 004
Create Date: 2026-08-02

اضافه کردن ستون is_active_inverted به employee_mappings — برای پشتیبانی از
ستون‌هایی مثل IsCut که منطقشان برعکس «فعال بودن» است (۱=غیرفعال، ۰=فعال).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "employee_mappings",
        sa.Column("is_active_inverted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("employee_mappings", "is_active_inverted")
