"""بکاپ: رمز فایل ZIP (AES-256) در تنظیمات بکاپ

ساده‌سازی بکاپ به درخواست کاربر: همان ZIP قبلی + فایل‌های آپلودی اتوماسیون، با رمز اختیاری. جدول‌های backup_keys و
backup_runs (Migration 132) می‌مانند (کلیدها دیگر استفاده نمی‌شوند؛ backup_runs تاریخچه‌ی داخلی است).

Revision ID: 133
Revises: 132
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "133"
down_revision: Union[str, None] = "132"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("backup_settings", sa.Column("archive_password_encrypted", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("backup_settings", "archive_password_encrypted")
