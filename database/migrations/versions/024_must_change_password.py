"""add must_change_password to users (اجبار به تغییر رمز عبور ضعیف/پیش‌فرض)

Revision ID: 024
Revises: 023
Create Date: 2026-08-19

قانون جدید قدرت رمز عبور (حداقل ۱۰ کاراکتر + حرف کوچک + حرف بزرگ + عدد)
معرفی شد. چون هش رمزهای موجود یک‌طرفه است (نمی‌شود از رمز فعلی فهمید ضعیف
بوده یا نه)، این Migration به‌جای حدس‌زدن، صرفاً همه حساب‌هایی که واقعاً یک
رمز عبور کاربر-تعیین‌شده دارند (is_superuser یا has_custom_password) را
علامت می‌زند تا بار بعد که وارد می‌شوند، مجبور به تعیین یک رمز جدید مطابق
قانون تازه شوند — شامل نصب‌های موجود، نه فقط نصب‌های تازه.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        "UPDATE users SET must_change_password = true "
        "WHERE is_superuser = true OR has_custom_password = true"
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
