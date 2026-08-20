"""add is_manual flag to gps_activity_logs, make lat/long nullable for manual entries

Revision ID: 025
Revises: 024
Create Date: 2026-08-20

پنل ادمین و نقش hr-manager حالا می‌توانند رکورد ورود/خروج به‌صورت دستی
اضافه/ویرایش/حذف کنند — چون این رکوردها مختصات GPS واقعی ندارند (خودِ
پرسنل آنجا نبوده که ثبت کند)، latitude/longitude باید Nullable شوند.
is_manual مشخص می‌کند این رکورد توسط خودِ پرسنل ثبت شده یا دستی توسط
Admin/hr-manager — در گزارش با یک ستاره (*) کنار زمان نشان داده می‌شود.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gps_activity_logs",
        sa.Column("is_manual", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("gps_activity_logs", "latitude", existing_type=sa.Float(), nullable=True)
    op.alter_column("gps_activity_logs", "longitude", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    op.alter_column("gps_activity_logs", "longitude", existing_type=sa.Float(), nullable=False)
    op.alter_column("gps_activity_logs", "latitude", existing_type=sa.Float(), nullable=False)
    op.drop_column("gps_activity_logs", "is_manual")
