"""عکس پرسنلی: درخواست بارگذاری/حذف با تأیید منابع انسانی

- جدول profile_photo_requests
- employee_mappings.photo_small_column (ستون عکس کوچک؛ کاراوب: ThumbnailImg). برای نگاشت‌های موجود روی
  EmployeeExtendedInfo مقدار ThumbnailImg پر می‌شود.
- مجوز photo.approve

Revision ID: 141
Revises: 140
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "141"
down_revision: Union[str, None] = "140"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "profile_photo_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("image", sa.LargeBinary(), nullable=True),
        sa.Column("thumbnail", sa.LargeBinary(), nullable=True),
        sa.Column("image_size", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_by_name", sa.String(200), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_profile_photo_requests_employee_id", "profile_photo_requests", ["employee_id"])
    op.create_index("ix_profile_photo_requests_site_id", "profile_photo_requests", ["site_id"])
    op.create_index("ix_profile_photo_requests_status", "profile_photo_requests", ["status"])

    op.add_column("employee_mappings", sa.Column("photo_small_column", sa.String(128), nullable=True))
    op.execute(
        "UPDATE employee_mappings SET photo_small_column = 'ThumbnailImg' "
        "WHERE photo_table IS NOT NULL AND lower(photo_table) LIKE '%employeeextendedinfo'"
    )
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('photo.approve', 'تأیید/رد درخواست بارگذاری و حذف عکس پرسنلی (و ثبت در دیتابیس کاراوب)')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'photo.approve')")
    op.execute("DELETE FROM user_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'photo.approve')")
    op.execute("DELETE FROM permissions WHERE code = 'photo.approve'")
    op.drop_column("employee_mappings", "photo_small_column")
    op.drop_index("ix_profile_photo_requests_status", table_name="profile_photo_requests")
    op.drop_index("ix_profile_photo_requests_site_id", table_name="profile_photo_requests")
    op.drop_index("ix_profile_photo_requests_employee_id", table_name="profile_photo_requests")
    op.drop_table("profile_photo_requests")
