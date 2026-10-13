"""مرحله‌ی «منابع انسانی» در مسیر تأیید وام: تأییدکننده در تنظیمات وام سایت + snapshot روی هر درخواست.

Revision ID: 113
Revises: 112
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "113"
down_revision: Union[str, None] = "112"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "loan_site_settings",
        sa.Column("hr_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "loan_requests",
        sa.Column("hr_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("loan_requests", "hr_employee_id")
    op.drop_column("loan_site_settings", "hr_employee_id")
