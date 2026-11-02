"""اتوماسیون اداری: پاک‌سازی باقی‌مانده‌ی تصمیم‌های کنار گذاشته‌شده

- oa_templates.site_id حذف شد (قالب برای همه‌ی سایت‌ها یکسان است — تصمیم ۱۴۰۵/۰۸/۱۱).
- رابطه‌های عطف/پیرو (اگر ساخته شده باشند) حذف می‌شوند؛ فقط «پاسخ» باقی است.

Revision ID: 140
Revises: 139
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "140"
down_revision: Union[str, None] = "139"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM oa_letter_relations WHERE type <> 'reply'")
    op.execute("DROP INDEX IF EXISTS ix_oa_templates_site_id")
    op.drop_column("oa_templates", "site_id")


def downgrade() -> None:
    op.add_column("oa_templates", sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=True))
