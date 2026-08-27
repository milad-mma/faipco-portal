"""add system.settings permission for «تنظیمات سامانه»

Revision ID: 034
Revises: 033
Create Date: 2026-08-27

قابلیت «تنظیمات سامانه» (فعلاً فقط عکس پس‌زمینه صفحه ورود) — طبق همان
الگوی همیشگی این پروژه، مجوز جدید مستقیماً داخل Migration ساخته می‌شود
(نه از پنل، چون هیچ Endpoint ای برای «ساخت مجوز جدید» وجود ندارد).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('system.settings', 'تنظیمات سراسری سامانه (مثل عکس پس‌زمینه صفحه ورود)')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code = 'system.settings'")
