"""add action_id mapping to leave requests

Revision ID: 057
Revises: 056
Create Date: 2026-09-10

طبق تحلیل دقیق داده واقعی WF_Requests (هر ۷ ردیف تستی کاربر): ستون
ActionId فقط به ترکیب مرخصی/مأموریت × ساعتی/روزانه بستگی دارد - نه به
زیرنوع دقیق (استحقاقی/استعلاجی/شرکتی). این Migration دو ستون جدید
اضافه می‌کند:
    - leave_request_mappings.action_id_column: نام ستون ActionId (اختیاری)
    - leave_request_types.action_id: مقدار ActionId این نوع خاص (اختیاری)
هردو اختیاری هستند - اگر خالی بمانند، اصلاً نوشته نمی‌شوند (رفتار قبلی
حفظ می‌شود).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "057"
down_revision: Union[str, None] = "056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leave_request_mappings",
        sa.Column("action_id_column", sa.String(length=128), nullable=True, server_default="ActionId"),
    )
    op.add_column("leave_request_types", sa.Column("action_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("leave_request_types", "action_id")
    op.drop_column("leave_request_mappings", "action_id_column")
