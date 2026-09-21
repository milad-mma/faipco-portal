"""attendance_mappings.calendar_branch_column

Revision ID: 082
Revises: 081
Create Date: 2026-09-21

چند سایت روی یک کاراوب: جدول تقویم تعطیلات (Calen) روی BranchCode+Year+Month
یکتاست؛ بدون فیلتر شعبه، تقویم یک شعبه دیگر برمی‌گشت. برای سایت‌هایی که تقویم
Calen را نگاشت کرده‌اند، ستون شعبه BranchCode تنظیم می‌شود (مقدار از «کد شعبه
این سایت» در نگاشت پرسنل؛ تا آن خالی است فیلتری اعمال نمی‌شود).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "082"
down_revision: Union[str, None] = "081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("attendance_mappings", sa.Column("calendar_branch_column", sa.String(128), nullable=True))
    op.execute(
        "UPDATE attendance_mappings SET calendar_branch_column = 'BranchCode' "
        "WHERE lower(calendar_table_name) = 'calen'"
    )


def downgrade() -> None:
    op.drop_column("attendance_mappings", "calendar_branch_column")
