"""سابقه‌ی انتقال درخواست مرخصی/ماموریت از تأییدکننده‌ی ترک‌کار یا تغییرکرده

Revision ID: 123
Revises: 122

مثل وام و مساعده: درخواست‌های بدون تصمیم کاراوب که پیش تأییدکننده‌ی ترک‌کار مانده‌اند به تأییدکننده‌ی امروز منتقل
می‌شوند (CurEmpNo)؛ این جدول سابقه‌ی هر انتقال را در پرتال نگه می‌دارد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "123"
down_revision: Union[str, None] = "122"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "leave_request_reassignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("from_emp_no", sa.Integer(), nullable=False),
        sa.Column("to_emp_no", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_leave_request_reassignments_site_id", "leave_request_reassignments", ["site_id"])
    op.create_index("ix_leave_request_reassignments_request_id", "leave_request_reassignments", ["request_id"])


def downgrade() -> None:
    op.drop_table("leave_request_reassignments")
