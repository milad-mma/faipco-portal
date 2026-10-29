"""مهلت ثبت هر نوع درخواست مرخصی/ماموریت: چند روز بعد از تاریخ (گذشته) و چند روز جلوتر (آینده)

Revision ID: 126
Revises: 125

خالی = بدون محدودیت (رفتار فعلی).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "126"
down_revision: Union[str, None] = "125"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leave_request_types", sa.Column("max_past_days", sa.Integer(), nullable=True))
    op.add_column("leave_request_types", sa.Column("max_future_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("leave_request_types", "max_future_days")
    op.drop_column("leave_request_types", "max_past_days")
