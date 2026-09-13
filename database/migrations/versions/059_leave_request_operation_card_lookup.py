"""add WF_OperationTypes and Cards lookup configuration for leave requests

Revision ID: 059
Revises: 058
Create Date: 2026-09-10

طبق تأیید صریح کاربر:
    - OperationsID در WF_Requests از ستون OperationId جدول
      WF_OperationTypes می‌آید (عنوان فارسی در ستون Name) - نه صرفاً دو
      مقدار ثابت ۵/۳ که قبلاً حدس زده بودیم.
    - Card_No در WF_Requests از ستون Card_No جدول Cards می‌آید (عنوان
      فارسی در ستون DefaultTitle) - نه یک مقدار ثابت ۰.

این Migration دقیقاً همان الگوی جدول مرجع WF_Action (Migration 058) را
برای این دو جدول مرجع دیگر هم تکرار می‌کند - هم برای نگاشت ستون‌های
جدول مرجع (روی LeaveRequestMapping)، هم برای مقدار انتخاب‌شده هر نوع
درخواست خاص (روی LeaveRequestType) - کاملاً اختیاری، بدون شکست عقب‌رو.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "059"
down_revision: Union[str, None] = "058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leave_request_mappings",
        sa.Column(
            "operation_lookup_table_name", sa.String(length=128), nullable=True, server_default="WF_OperationTypes"
        ),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column("operation_lookup_id_column", sa.String(length=128), nullable=True, server_default="OperationId"),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column("operation_lookup_desc_column", sa.String(length=128), nullable=True, server_default="Name"),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column("card_lookup_table_name", sa.String(length=128), nullable=True, server_default="Cards"),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column("card_lookup_id_column", sa.String(length=128), nullable=True, server_default="Card_No"),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column("card_lookup_desc_column", sa.String(length=128), nullable=True, server_default="DefaultTitle"),
    )

    op.add_column("leave_request_types", sa.Column("operation_id", sa.Integer(), nullable=True))
    op.add_column("leave_request_types", sa.Column("card_no", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("leave_request_types", "card_no")
    op.drop_column("leave_request_types", "operation_id")

    op.drop_column("leave_request_mappings", "card_lookup_desc_column")
    op.drop_column("leave_request_mappings", "card_lookup_id_column")
    op.drop_column("leave_request_mappings", "card_lookup_table_name")
    op.drop_column("leave_request_mappings", "operation_lookup_desc_column")
    op.drop_column("leave_request_mappings", "operation_lookup_id_column")
    op.drop_column("leave_request_mappings", "operation_lookup_table_name")
