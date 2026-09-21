"""employee_mappings: branch_code_column / branch_code_value

Revision ID: 081
Revises: 080
Create Date: 2026-09-21

طبق درخواست کاربر: ستون BranchCode جدول Employee مبنای Sync پرسنل هر سایت باشد
(دیتابیس پرسنل مشترک بین چند سایت). اختیاری - خالی یعنی بدون فیلتر (رفتار قبلی).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "081"
down_revision: Union[str, None] = "080"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("employee_mappings", sa.Column("branch_code_column", sa.String(128), nullable=True))
    op.add_column("employee_mappings", sa.Column("branch_code_value", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("employee_mappings", "branch_code_value")
    op.drop_column("employee_mappings", "branch_code_column")
