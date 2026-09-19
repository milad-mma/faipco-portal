"""add announcement dismissal tracking to users

Revision ID: 071
Revises: 070
Create Date: 2026-09-18

طبق درخواست صریح کاربر: دیالوگ «تغییرات اخیر پرتال» هنگام ورود نمایش
داده می‌شود و کاربر می‌تواند «دیگر نمایش نده» را بزند.

چرا روی خودِ کاربر (نه localStorage): با عوض‌کردن مرورگر یا دستگاه،
اعلانی که قبلاً رد شده نباید دوباره ظاهر شود.

چرا «نسخه» و نه یک Boolean ساده: وقتی ادمین متن اعلان را عوض می‌کند
نسخه بالا می‌رود، پس کاربری که قبلاً رد کرده، اعلان **جدید** را دوباره
می‌بیند - وگرنه یک‌بار رد کردن یعنی هرگز ندیدن هیچ اعلان بعدی.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "071"
down_revision: Union[str, None] = "070"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("dismissed_announcement_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "dismissed_announcement_version")
