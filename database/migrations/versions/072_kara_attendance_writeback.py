"""add kara_writeback_enabled to leave_request_mappings

Revision ID: 072
Revises: 071
Create Date: 2026-09-19

طبق آزمایش مستقیم روی کاراوب: تأیید نهایی درخواست در کاراوب فقط
WF_Requests را عوض نمی‌کند - مرخصی/ماموریت روزانه یک ردیف Mor_Mam می‌سازد
و درخواست ساعتی روی تردد مطابق (DataFile.Status) اعمال می‌شود. پرتال حالا
همین کار را می‌کند؛ این ستون امکان خاموش‌کردنش را از تنظیمات سایت می‌دهد.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "072"
down_revision: Union[str, None] = "071"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leave_request_mappings",
        sa.Column("kara_writeback_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("leave_request_mappings", "kara_writeback_enabled")
