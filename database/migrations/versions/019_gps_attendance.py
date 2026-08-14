"""add GPS geofence fields to sites + gps_activity_logs table (حضور مبتنی بر موقعیت مکانی و ثبت ورود/خروج آزمایشی)

Revision ID: 019
Revises: 018
Create Date: 2026-08-14

هر Site می‌تواند (اختیاری) یک موقعیت GPS + شعاع مجاز داشته باشد. اگر برای
یک سایت مقداری تنظیم نشده باشد (NULL)، هیچ محدودیتی برای پرسنل همان سایت
اعمال نمی‌شود — این قابلیت به‌طور پیش‌فرض برای هیچ‌کس فعال نیست.

gps_activity_logs هم «حضور دوره‌ای» (وقتی اپ باز است) هم «ثبت ورود/خروج
آزمایشی» را با یک جدول مشترک ثبت می‌کند (log_type تفاوت را مشخص می‌کند).

نکته مهم (اصلاح‌شده): نسخه اول این Migration یک باگ شناخته‌شده SQLAlchemy/
PostgreSQL داشت — وقتی یک Enum هم دستی Create می‌شود هم به‌عنوان نوع یک
ستون داخل op.create_table() استفاده می‌شود، خودِ create_table() دوباره
تلاش می‌کند همان Type را بسازد (بدون توجه به checkfirst قبلی) و با خطای
"type already exists" شکست می‌خورد. این نسخه هم آن باگ را با
create_type=False روی ستون رفع می‌کند، هم کاملاً Idempotent است — یعنی
حتی اگر قبلاً به‌صورت ناقص اجرا شده باشد (مثلاً ستون‌های sites اضافه شده
ولی جدول gps_activity_logs ساخته نشده)، اجرای دوباره‌اش بدون خطا از همان
جایی که متوقف شده ادامه می‌دهد.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ENUM_NAME = "gps_log_type_enum"
_ENUM_VALUES = ("presence", "check_in", "check_out")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_site_columns = {col["name"] for col in inspector.get_columns("sites")}
    if "gps_latitude" not in existing_site_columns:
        op.add_column("sites", sa.Column("gps_latitude", sa.Float(), nullable=True))
    if "gps_longitude" not in existing_site_columns:
        op.add_column("sites", sa.Column("gps_longitude", sa.Float(), nullable=True))
    if "gps_radius_meters" not in existing_site_columns:
        op.add_column("sites", sa.Column("gps_radius_meters", sa.Integer(), nullable=True))

    # این Type را جدا و صریح می‌سازیم (checkfirst=True یعنی اگر از اجرای
    # ناقص قبلی از قبل ساخته شده، خطا نمی‌دهد و رد می‌شود)
    gps_log_type = sa.Enum(*_ENUM_VALUES, name=_ENUM_NAME)
    gps_log_type.create(bind, checkfirst=True)

    if not inspector.has_table("gps_activity_logs"):
        op.create_table(
            "gps_activity_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
            ),
            # create_type=False حیاتی است: Type را همین بالا صریح ساختیم؛
            # اگر این False نباشد، create_table() دوباره سعی می‌کند بسازدش
            # و با «type already exists» شکست می‌خورد — دقیقاً همان باگی که
            # این نسخه دارد رفعش می‌کند.
            sa.Column(
                "log_type",
                postgresql.ENUM(*_ENUM_VALUES, name=_ENUM_NAME, create_type=False),
                nullable=False,
            ),
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

    existing_indexes = (
        {idx["name"] for idx in inspector.get_indexes("gps_activity_logs")}
        if inspector.has_table("gps_activity_logs")
        else set()
    )
    if "ix_gps_activity_logs_employee_id" not in existing_indexes:
        op.create_index("ix_gps_activity_logs_employee_id", "gps_activity_logs", ["employee_id"])
    if "ix_gps_activity_logs_created_at" not in existing_indexes:
        op.create_index("ix_gps_activity_logs_created_at", "gps_activity_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_gps_activity_logs_created_at", table_name="gps_activity_logs")
    op.drop_index("ix_gps_activity_logs_employee_id", table_name="gps_activity_logs")
    op.drop_table("gps_activity_logs")
    sa.Enum(name=_ENUM_NAME).drop(op.get_bind(), checkfirst=True)
    op.drop_column("sites", "gps_radius_meters")
    op.drop_column("sites", "gps_longitude")
    op.drop_column("sites", "gps_latitude")
