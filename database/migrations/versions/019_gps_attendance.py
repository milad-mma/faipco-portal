"""add GPS geofence fields to sites + gps_activity_logs table (حضور مبتنی بر موقعیت مکانی و ثبت ورود/خروج آزمایشی)

Revision ID: 019
Revises: 018
Create Date: 2026-08-14

هر Site می‌تواند (اختیاری) یک موقعیت GPS + شعاع مجاز داشته باشد. اگر برای
یک سایت مقداری تنظیم نشده باشد (NULL)، هیچ محدودیتی برای پرسنل همان سایت
اعمال نمی‌شود — این قابلیت به‌طور پیش‌فرض برای هیچ‌کس فعال نیست.

gps_activity_logs هم «حضور دوره‌ای» (وقتی اپ باز است) هم «ثبت ورود/خروج
آزمایشی» را با یک جدول مشترک ثبت می‌کند (log_type تفاوت را مشخص می‌کند).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

gps_log_type_enum = sa.Enum("presence", "check_in", "check_out", name="gps_log_type_enum")


def upgrade() -> None:
    op.add_column("sites", sa.Column("gps_latitude", sa.Float(), nullable=True))
    op.add_column("sites", sa.Column("gps_longitude", sa.Float(), nullable=True))
    op.add_column("sites", sa.Column("gps_radius_meters", sa.Integer(), nullable=True))

    gps_log_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "gps_activity_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("log_type", gps_log_type_enum, nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("accuracy_meters", sa.Float(), nullable=True),
        sa.Column(
            "matched_site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("distance_meters", sa.Float(), nullable=True),
        sa.Column("is_within_geofence", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_gps_activity_logs_employee_id", "gps_activity_logs", ["employee_id"])
    op.create_index("ix_gps_activity_logs_created_at", "gps_activity_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_gps_activity_logs_created_at", table_name="gps_activity_logs")
    op.drop_index("ix_gps_activity_logs_employee_id", table_name="gps_activity_logs")
    op.drop_table("gps_activity_logs")
    gps_log_type_enum.drop(op.get_bind(), checkfirst=True)
    op.drop_column("sites", "gps_radius_meters")
    op.drop_column("sites", "gps_longitude")
    op.drop_column("sites", "gps_latitude")
