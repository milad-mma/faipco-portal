"""multi-site: فیلتر واحد ریشه در نگاشت پرسنل + آمار Sync + جدول جابه‌جایی بین سایت‌ها

Revision ID: 086
Revises: 085
Create Date: 2026-09-24

چند سایت پرتال می‌توانند پرسنلشان را از یک دیتابیس کاراوب مشترک بخوانند و
بر اساس درخت واحدها (Sections.TFather) از هم جدا شوند:
- employee_mappings.department_lookup_parent_column: ستون واحد بالادست در جدول Lookup واحدها
- employee_mappings.root_department_codes: کد واحدهای ریشه‌ی این سایت (خالی = بدون فیلتر، مثل قبل)
- sync_logs: تعداد پرسنل ردشده به‌خاطر واحد بی‌سایت، تعداد جابه‌جایی‌ها و متن هشدار
- site_transfers: ثبت جابه‌جایی پرسنل بین سایت‌ها برای بازبینی نقش‌های سایت قبلی
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "086"
down_revision: Union[str, None] = "085"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # نگاشت پرسنل: ستون بالادست + ریشه‌های سایت
    op.add_column("employee_mappings", sa.Column("department_lookup_parent_column", sa.String(128), nullable=True))
    op.add_column(
        "employee_mappings",
        sa.Column("root_department_codes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )

    # آمار اضافه‌ی هر اجرای Sync
    op.add_column(
        "sync_logs", sa.Column("skipped_unassigned_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("sync_logs", sa.Column("transferred_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("sync_logs", sa.Column("warning_message", sa.Text(), nullable=True))

    # جابه‌جایی‌های پرسنل بین سایت‌ها
    op.create_table(
        "site_transfers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("personnel_code", sa.String(64), nullable=False),
        sa.Column("from_site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="SET NULL"), nullable=True),
        sa.Column("to_site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("transferred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_site_transfers_reviewed_at", "site_transfers", ["reviewed_at"])


def downgrade() -> None:
    op.drop_index("ix_site_transfers_reviewed_at", table_name="site_transfers")
    op.drop_table("site_transfers")
    op.drop_column("sync_logs", "warning_message")
    op.drop_column("sync_logs", "transferred_count")
    op.drop_column("sync_logs", "skipped_unassigned_count")
    op.drop_column("employee_mappings", "root_department_codes")
    op.drop_column("employee_mappings", "department_lookup_parent_column")
