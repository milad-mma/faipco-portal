"""add soft-delete columns to notices

Revision ID: 007
Revises: 006
Create Date: 2026-08-09

حذف اطلاعیه به‌صورت Soft-Delete: هیچ رکوردی از notices/notice_targets/notice_reads
فیزیکی پاک نمی‌شود (تا آمار و گزارش‌ها دست‌نخورده بمانند)، فقط is_deleted=True
می‌شود. اطلاعیه حذف‌شده از لیست دریافتی مخاطبان (notices/me) کاملاً کنار گذاشته
می‌شود، ولی در گزارش «ارسالی من» و «گزارش کامل Admin» با برچسب «حذف شده» باقی می‌ماند.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notices",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "notices",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notices", "deleted_at")
    op.drop_column("notices", "is_deleted")
