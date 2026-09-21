"""leave_request_mappings.is_disabled

Revision ID: 083
Revises: 082
Create Date: 2026-09-21

غیرفعال‌سازی ماژول «درخواست مرخصی/ماموریت» برای یک سایت از صفحه تنظیمات همین
ماژول. تا وقتی غیرفعال است، صفحه درخواست پرسنل آن سایت بسته است و کارت داشبورد
«غیرفعال» نشان می‌دهد؛ نگاشت‌ها و تنظیمات دست‌نخورده می‌مانند.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "083"
down_revision: Union[str, None] = "082"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leave_request_mappings",
        sa.Column("is_disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("leave_request_mappings", "is_disabled")
