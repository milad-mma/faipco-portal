"""add photo_thumbnail to employees + photo mapping columns (برای نمایش عکس پرسنل از جدول EmployeeExtendedInfo)

Revision ID: 014
Revises: 013
Create Date: 2026-08-12

فقط تصویر بندانگشتی (ThumbnailImg، معمولاً GIF و کوچک) ذخیره می‌شود، نه تصویر
اصلی (Img، JPEG با حجم بالا) — چون این فقط برای نمایش آواتار کوچک در پنل لازم
است، نه یک گالری تصویر با کیفیت بالا. ذخیره تصویر اصلی برای همه پرسنل در هر
چرخه Sync حجم دیتابیس را بی‌دلیل چند برابر می‌کرد.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("photo_thumbnail", sa.LargeBinary(), nullable=True))
    op.add_column(
        "employee_mappings", sa.Column("photo_table", sa.String(length=128), nullable=True)
    )
    op.add_column(
        "employee_mappings", sa.Column("photo_emp_no_column", sa.String(length=128), nullable=True)
    )
    op.add_column(
        "employee_mappings", sa.Column("photo_thumbnail_column", sa.String(length=128), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("employee_mappings", "photo_thumbnail_column")
    op.drop_column("employee_mappings", "photo_emp_no_column")
    op.drop_column("employee_mappings", "photo_table")
    op.drop_column("employees", "photo_thumbnail")
