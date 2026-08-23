"""add skipped_inactive_count to sync_logs

Revision ID: 028
Revises: 027
Create Date: 2026-08-23

پرسنلی که در دیتابیس مبدأ (طبق همان یک ستون قابل‌تنظیم is_active_column —
با یا بدون is_active_inverted، مثلاً IsActive عادی یا IsCut معکوس) غیرفعال
باشند، دیگر اصلاً به پرتال Import نمی‌شوند (نه فقط is_active=False) — اگر
قبلاً وارد شده باشند و بعداً غیرفعال شوند، رکورد و سوابقشان (فیش حقوقی و
...) دست‌نخورده می‌ماند، فقط is_active=False می‌شود؛ نگاه کنید
docs/sync-engine.md.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sync_logs", sa.Column("skipped_inactive_count", sa.Integer(), nullable=False, server_default="0")
    )


def downgrade() -> None:
    op.drop_column("sync_logs", "skipped_inactive_count")
