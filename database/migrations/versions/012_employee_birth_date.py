"""add birth_month/birth_day to employees + birth_date_column mapping (برای کارت «متولدین روز جاری» در داشبورد)

Revision ID: 012
Revises: 011
Create Date: 2026-08-12

birth_month/birth_day عمداً به‌جای یک ستون Date کامل ذخیره می‌شوند: تاریخ تولد
در دیتابیس‌های منبع HR معمولاً شمسی است، و برای این قابلیت فقط «روز/ماه»
لازم است (نه سال) — پس در لحظه Sync همان‌جا از رشته خام تاریخ شمسی مبدأ
استخراج می‌شود، بدون نیاز به تبدیل تقویم شمسی/میلادی برای کل رکورد.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("birth_month", sa.Integer(), nullable=True))
    op.add_column("employees", sa.Column("birth_day", sa.Integer(), nullable=True))
    op.add_column(
        "employee_mappings",
        sa.Column("birth_date_column", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("employee_mappings", "birth_date_column")
    op.drop_column("employees", "birth_day")
    op.drop_column("employees", "birth_month")
