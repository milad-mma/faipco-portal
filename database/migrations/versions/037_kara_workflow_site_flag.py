"""add kara_workflow_enabled to sites (monthly attendance report)

Revision ID: 037
Revises: 036
Create Date: 2026-08-29

قابلیت «گزارش تردد ماهانه» — می‌خواند از جدول DataFile نرم‌افزار «کاراوب»
(Kara WorkFlow)، در همان SQL Server هر سایت که برای Sync پرسنل وصل شده.
چون همه سایت‌ها الزاماً از این نرم‌افزار استفاده نمی‌کنند، یک فلگ سطح
Site (پیش‌فرض خاموش) اضافه شد — فقط برای سایت‌هایی که این فلگ روشن است،
پرسنلشان این گزارش را در داشبورد می‌بینند.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "037"
down_revision: Union[str, None] = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sites",
        sa.Column("kara_workflow_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("sites", "kara_workflow_enabled")
