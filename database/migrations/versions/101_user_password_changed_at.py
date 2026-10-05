"""ستون users.password_changed_at برای ابطال توکن‌های صادرشده پیش از تغییر رمز/خروج

Revision ID: 101
Revises: 100
Create Date: 2026-10-05

توکن‌های JWT از این نسخه claim iat (زمان صدور) دارند؛ اگر iat توکن قبل از password_changed_at کاربر باشد،
نشست منقضی تلقی می‌شود. ستون nullable و بدون مقدار پیش‌فرض است تا توکن‌های فعلی کاربران تا انقضای
طبیعی معتبر بمانند و هیچ‌کس مجبور به ورود مجدد نشود.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "101"
down_revision: Union[str, None] = "100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_changed_at")
