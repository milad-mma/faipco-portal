"""add kara_schema (table/column names) to leave_request_mappings

Revision ID: 073
Revises: 072
Create Date: 2026-09-19

طبق درخواست صریح کاربر: هر نام جدول/ستونی که در ثبت کارکرد کاراوب و
گزارش مرخصی/ماموریت استفاده می‌شود باید از تنظیمات سایت قابل‌نگاشت باشد
(نه مستقیم در کد). فقط مقادیری که با پیش‌فرض کاراوب فرق دارند ذخیره
می‌شوند - نصب‌های فعلی بدون هیچ تغییری همان رفتار قبلی را دارند.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "073"
down_revision: Union[str, None] = "072"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leave_request_mappings",
        sa.Column("kara_schema", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("leave_request_mappings", "kara_schema")
