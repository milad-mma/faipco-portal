"""مجوز مستقیم کاربر: جدول user_permissions

Revision ID: 106
Revises: 105
Create Date: 2026-10-07

کنار نقش‌ها، می‌توان به یک کاربر مجوزهای جداگانه داد (استثنا)، هرکدام برای همه‌ی سایت‌ها (site_id خالی) یا یک سایت
مشخص (هر سایت یک ردیف). در همه‌ی بررسی‌های مجوز کنار مجوزهای نقش‌ها حساب می‌شود؛ فقط «اضافه» است، منع ندارد.
مدیریت از همان دیالوگ «دسترسی پرسنل» (تب «مجوزهای مستقیم») با مجوز users.manage.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "106"
down_revision: Union[str, None] = "105"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=True),
        sa.Column("granted_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "permission_id", "site_id", name="uq_user_permission_site"),
    )
    op.create_index("ix_user_permissions_user_id", "user_permissions", ["user_id"])
    # NULL در Unique Constraint پستگرس یکتا نیست؛ ردیف «همه‌ی سایت‌ها» هر مجوز هم باید یکتا باشد
    op.create_index(
        "uq_user_permission_global",
        "user_permissions",
        ["user_id", "permission_id"],
        unique=True,
        postgresql_where=sa.text("site_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_user_permission_global", table_name="user_permissions")
    op.drop_index("ix_user_permissions_user_id", table_name="user_permissions")
    op.drop_table("user_permissions")
