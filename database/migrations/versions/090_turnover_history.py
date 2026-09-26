"""employee_mappings: جدول تاریخچه‌ی پرسنل برای دوره‌های استخدام مجدد در گزارش جذب و ترک کار

Revision ID: 090
Revises: 089
Create Date: 2026-09-26

کاراوب برای استخدام مجدد رکورد جدید نمی‌سازد: همان رکورد پرسنل دوباره فعال، تاریخ استخدام عوض و تاریخ
ترک کار پاک می‌شود؛ دوره‌ی قبلی فقط در جدول تاریخچه (LogEmployee، یک ردیف به ازای هر تغییر با ستون
ChangeDate) می‌ماند. با این دو ستون، گزارش دوره‌های خاتمه‌یافته‌ی قبلی را هم می‌شمارد.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "090"
down_revision: Union[str, None] = "089"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("employee_mappings", sa.Column("history_table", sa.String(128), nullable=True))
    op.add_column("employee_mappings", sa.Column("history_order_column", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("employee_mappings", "history_order_column")
    op.drop_column("employee_mappings", "history_table")
