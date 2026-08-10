"""add has_custom_password column to users

Revision ID: 010
Revises: 009
Create Date: 2026-08-09

وقتی True شود، یعنی این کاربر (پرسنل) یک رمز عبور واقعی دارد و از این پس
ورود با «کد پرسنلی + کد ملی» دیگر برایش معتبر نیست — فقط «کد پرسنلی + رمز
عبور تعیین‌شده». پیش‌فرض False (یعنی برای پرسنلی که هنوز رمز اختصاصی تعیین
نکرده‌اند، رفتار قبلی بدون تغییر باقی می‌ماند).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("has_custom_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "has_custom_password")
