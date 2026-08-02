"""add department lookup table mapping

Revision ID: 004
Revises: 003
Create Date: 2026-08-01

اضافه کردن سه ستون به employee_mappings برای پشتیبانی از جدول Lookup
واحدهای سازمانی در مبدأ (مثل dbo.Sections با ستون‌های Sec_No و Title).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("employee_mappings", sa.Column("department_lookup_table", sa.String(length=128), nullable=True))
    op.add_column("employee_mappings", sa.Column("department_lookup_id_column", sa.String(length=128), nullable=True))
    op.add_column("employee_mappings", sa.Column("department_lookup_name_column", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("employee_mappings", "department_lookup_name_column")
    op.drop_column("employee_mappings", "department_lookup_id_column")
    op.drop_column("employee_mappings", "department_lookup_table")
