"""مشخصات خانوادگی: نفر منابع انسانی هر سایت که با ثبت فرم پرسنل اعلان می‌گیرد

Revision ID: 130
Revises: 129
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "130"
down_revision: Union[str, None] = "129"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "family_site_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("hr_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("family_site_settings")
