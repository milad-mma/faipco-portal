"""add optional calendar mapping to attendance_mappings

Revision ID: 039
Revises: 038
Create Date: 2026-08-29

نگاشت اختیاری جدول تقویم/تعطیلات — برای رنگ‌آمیزی روزهای تعطیل در
«گزارش تردد ماهانه». کاملاً مستقل و اختیاری (Nullable) — اگر تنظیم
نشود، گزارش دقیقاً مثل قبل (بدون رنگ‌آمیزی تعطیلات) کار می‌کند.

ساختار مورد انتظار جدول تقویم: یک ردیف به‌ازای هر (سال، ماه شمسی)، با
ستون‌های روز شماره‌گذاری‌شده (مثلاً D1 تا D31) که هرکدام یا صفر (روز
عادی) یا یک عدد غیرصفر (تعطیل) هستند.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "039"
down_revision: Union[str, None] = "038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("attendance_mappings", sa.Column("calendar_table_name", sa.String(length=128), nullable=True))
    op.add_column("attendance_mappings", sa.Column("calendar_year_column", sa.String(length=128), nullable=True))
    op.add_column("attendance_mappings", sa.Column("calendar_month_column", sa.String(length=128), nullable=True))
    op.add_column(
        "attendance_mappings", sa.Column("calendar_day_column_prefix", sa.String(length=32), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("attendance_mappings", "calendar_day_column_prefix")
    op.drop_column("attendance_mappings", "calendar_month_column")
    op.drop_column("attendance_mappings", "calendar_year_column")
    op.drop_column("attendance_mappings", "calendar_table_name")
