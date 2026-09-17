"""add leave_request_type_viewers for per-type view permission

Revision ID: 064
Revises: 063
Create Date: 2026-09-17

طبق درخواست صریح کاربر: مجوز مشاهده به تفکیک نوع درخواست - مثلاً حراست
فقط اجازه دیدن درخواست‌های «مرخصی» یا «ماموریت ساعتی» داشته باشد، نه
همه‌ی درخواست‌های سایت. این جدول کاملاً مستقل و مکمل مجوزهای سراسری
leave_requests.view/leave_requests.manage است.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "064"
down_revision: Union[str, None] = "063"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "leave_request_type_viewers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "leave_type_id",
            sa.Integer(),
            sa.ForeignKey("leave_request_types.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_leave_request_type_viewers_leave_type_id", "leave_request_type_viewers", ["leave_type_id"]
    )
    op.create_index(
        "ix_leave_request_type_viewers_employee_id", "leave_request_type_viewers", ["employee_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_leave_request_type_viewers_employee_id", table_name="leave_request_type_viewers")
    op.drop_index("ix_leave_request_type_viewers_leave_type_id", table_name="leave_request_type_viewers")
    op.drop_table("leave_request_type_viewers")
