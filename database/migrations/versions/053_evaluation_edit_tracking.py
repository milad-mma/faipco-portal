"""add was_edited tracking to evaluations for one-time edit rule

Revision ID: 053
Revises: 052
Create Date: 2026-09-07

طبق درخواست صریح: ارزیاب فقط یک‌بار می‌تواند یک ارزیابی ثبت‌نهایی‌شده را
(تا وقتی دوره هنوز بسته/بایگانی نشده) دوباره باز و ویرایش کند. این
ستون همان «یک‌بار مصرف بودن» را رهگیری می‌کند - بعد از اولین ویرایش،
True می‌شود و دیگر امکان بازکردن دوباره وجود ندارد.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "053"
down_revision: Union[str, None] = "052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evaluations",
        sa.Column("was_edited", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('performance.reports.view', 'مشاهده گزارش‌های مدیریتی ارزیابی عملکرد (میانگین واحد/سایت، مقایسه دوره‌ها)')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_column("evaluations", "was_edited")
    op.execute("DELETE FROM permissions WHERE code = 'performance.reports.view'")
