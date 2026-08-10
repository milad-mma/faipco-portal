"""add is_enabled column to employees (manual admin override, independent of Sync)

Revision ID: 009
Revises: 008
Create Date: 2026-08-09

این ستون کاملاً مجزا از is_active است:
- is_active   → همیشه توسط Sync Engine از روی دیتابیس مبدأ هر Site محاسبه می‌شود
                (مثلاً از روی ستون IsCut طبق Mapping). Sync Engine در هر اجرا آن را
                بازنویسی می‌کند — دست‌کاری مستقیمش از پنل معنا ندارد.
- is_enabled  → فقط و فقط توسط Admin از پنل «پرسنل» تغییر می‌کند. Sync Engine
                هرگز این ستون را نمی‌خواند و نمی‌نویسد؛ پس با هیچ همگام‌سازی
                جدیدی از بین نمی‌رود.

وضعیت واقعی «آیا این پرسنل مجاز به ورود/دریافت اطلاعیه است» ترکیب هر دو است:
is_active AND is_enabled.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("employees", "is_enabled")
