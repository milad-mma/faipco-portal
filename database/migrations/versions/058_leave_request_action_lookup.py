"""add WF_Action lookup table configuration for leave request types

Revision ID: 058
Revises: 057
Create Date: 2026-09-10

طبق درخواست صریح کاربر: جدول WF_Action (در همان دیتابیس منبع سایت) دو
ستون دارد - ActionId و Fdesc (عنوان فارسی همان ActionId). این جدول
فهرست رسمی انواع درخواست را نگه می‌دارد؛ برای این‌که هنگام ساخت «نوع
درخواست» جدید در پنل ادمین، به‌جای حدس‌زدن دستی ActionId، از همین فهرست
واقعی (خوانده‌شده زنده از دیتابیس منبع) انتخاب شود.

کاملاً اختیاری و مستقل از تنظیمات اصلی Mapping - اگر
action_lookup_table_name خالی بماند، این قابلیت غیرفعال است.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "058"
down_revision: Union[str, None] = "057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leave_request_mappings",
        sa.Column("action_lookup_table_name", sa.String(length=128), nullable=True, server_default="WF_Action"),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column("action_lookup_id_column", sa.String(length=128), nullable=True, server_default="ActionId"),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column("action_lookup_desc_column", sa.String(length=128), nullable=True, server_default="Fdesc"),
    )


def downgrade() -> None:
    op.drop_column("leave_request_mappings", "action_lookup_desc_column")
    op.drop_column("leave_request_mappings", "action_lookup_id_column")
    op.drop_column("leave_request_mappings", "action_lookup_table_name")
