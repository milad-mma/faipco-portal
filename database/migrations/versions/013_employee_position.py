"""add position_title to employees + position lookup mapping columns (برای نمایش سمت در باکس اطلاعات پرسنل)

Revision ID: 013
Revises: 012
Create Date: 2026-08-12

سمت مستقیماً به‌صورت متن (نه یک جدول جدا مثل Department) ذخیره می‌شود، چون فقط
برای نمایش اطلاعاتی لازم است و نیازی مثل هدف‌گیری اطلاعیه یا تعیین سرپرست ندارد.
الگوی Mapping دقیقاً کپی همان الگوی Lookup واحد سازمانی است (جدول Position با
ستون‌های Pos_No/Title، و ستون Pos_No روی جدول اصلی پرسنل).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("position_title", sa.String(length=128), nullable=True))
    op.add_column(
        "employee_mappings", sa.Column("position_column", sa.String(length=128), nullable=True)
    )
    op.add_column(
        "employee_mappings", sa.Column("position_lookup_table", sa.String(length=128), nullable=True)
    )
    op.add_column(
        "employee_mappings", sa.Column("position_lookup_id_column", sa.String(length=128), nullable=True)
    )
    op.add_column(
        "employee_mappings", sa.Column("position_lookup_name_column", sa.String(length=128), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("employee_mappings", "position_lookup_name_column")
    op.drop_column("employee_mappings", "position_lookup_id_column")
    op.drop_column("employee_mappings", "position_lookup_table")
    op.drop_column("employee_mappings", "position_column")
    op.drop_column("employees", "position_title")
