"""replace kara_workflow_enabled flag with attendance_mappings table

Revision ID: 038
Revises: 037
Create Date: 2026-08-29

طبق درخواست صریح، دو تغییر همزمان:

۱) دیگر هیچ نامی از نرم‌افزار خاص («کاراوب») در کد/دیتابیس نباشد — فلگ
   ساده `sites.kara_workflow_enabled` (Migration 037) حذف می‌شود.

۲) به‌جای یک فلگ روشن/خاموش ساده، دقیقاً مثل نگاشت پرسنل موجود
   (`employee_mappings`)، یک نگاشت واقعی جدول/ستون برای هر سایت اضافه
   می‌شود — چون نرم‌افزارهای مختلف حضور و غیاب دستگاهی، نام جدول/ستون‌های
   متفاوتی دارند. وجود یا نبود این رکورد برای یک سایت، خودِ «آیا این
   گزارش برای این سایت فعال است؟» را هم مشخص می‌کند.

⚠️ چون Migration 037 (که فلگ قبلی را اضافه می‌کرد) از قبل روی این
دیتابیس واقعاً اجرا شده، محتوای آن Migration دست‌نخورده نگه داشته شد —
این تغییر به‌جای ویرایش آن، در یک Migration کاملاً جدید انجام می‌شود.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "038"
down_revision: Union[str, None] = "037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("sites", "kara_workflow_enabled")

    op.create_table(
        "attendance_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_name", sa.String(length=128), nullable=False),
        sa.Column("personnel_code_column", sa.String(length=128), nullable=False),
        sa.Column("date_column", sa.String(length=128), nullable=False),
        sa.Column("time_column", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("site_id", name="uq_attendance_mappings_site_id"),
    )


def downgrade() -> None:
    op.drop_table("attendance_mappings")
    op.add_column(
        "sites",
        sa.Column("kara_workflow_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
