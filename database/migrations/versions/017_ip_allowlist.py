"""add ip_allowlist_entries table (محدودکردن ورود به رنج‌های IP مجاز — مثلاً فقط شبکه دفتر)

Revision ID: 017
Revises: 016
Create Date: 2026-08-13

اگر این جدول خالی باشد، هیچ محدودیتی اعمال نمی‌شود (رفتار پیش‌فرض کاملاً باز
است) — فقط وقتی Admin حداقل یک رنج اضافه کند، ورود به همان رنج‌ها محدود
می‌شود. این طراحی عمداً است تا فعال‌سازی این قابلیت هرگز به‌طور تصادفی همه
را قفل نکند.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ip_allowlist_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cidr", sa.String(length=64), nullable=False, unique=True),
        sa.Column("label", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ip_allowlist_entries")
