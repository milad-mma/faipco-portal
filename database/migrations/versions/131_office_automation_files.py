"""اتوماسیون اداری فاز ۱: فایل‌ها، تنظیمات پیوست هر سایت، ثبت وقایع و مجوزهای پایه

- oa_files: متادیتای فایل‌های بیرون از دیتابیس (Storage خصوصی)، وضعیت اسکن و هش
- oa_attachment_settings: تعداد/حجم/فرمت پیوست هر سایت (از پرتال)
- oa_audit_events: ثبت وقایع فقط‌افزودنی
- مجوزها: automation.access (ورود و کارتابل — از فاز ۳الف)، automation.settings (تنظیمات اتوماسیون هر سایت)
  به هیچ نقشی داده نمی‌شوند (پیش‌فرض: هیچ‌کس؛ ادمین کل همه را دارد).

Revision ID: 131
Revises: 130
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "131"
down_revision: Union[str, None] = "130"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "oa_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="SET NULL"), nullable=True),
        sa.Column("storage_key", sa.String(255), nullable=True),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("detected_format", sa.String(16), nullable=True),
        sa.Column("content_type", sa.String(128), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("purpose", sa.String(32), nullable=False, server_default="attachment"),
        sa.Column("status", sa.String(16), nullable=False, server_default="uploading"),
        sa.Column("state", sa.String(16), nullable=False, server_default="temp"),
        sa.Column("reject_reason", sa.String(500), nullable=True),
        sa.Column("scan_result", sa.String(255), nullable=True),
        sa.Column("scan_db_version", sa.String(128), nullable=True),
        sa.Column("scan_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True),
        *_ts(),
    )
    op.create_index("ix_oa_files_site_id", "oa_files", ["site_id"])
    op.create_index("ix_oa_files_status", "oa_files", ["status"])
    op.create_index("ix_oa_files_state", "oa_files", ["state"])
    op.create_index("ix_oa_files_storage_key", "oa_files", ["storage_key"], unique=True)

    op.create_table(
        "oa_attachment_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("letter_max_files", sa.Integer(), nullable=False),
        sa.Column("letter_max_file_mb", sa.Integer(), nullable=False),
        sa.Column("letter_max_total_mb", sa.Integer(), nullable=False),
        sa.Column("action_max_files", sa.Integer(), nullable=False),
        sa.Column("action_max_file_mb", sa.Integer(), nullable=False),
        sa.Column("action_max_total_mb", sa.Integer(), nullable=False),
        sa.Column("letter_all_max_total_mb", sa.Integer(), nullable=False),
        sa.Column("allowed_formats", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_ts(),
    )

    op.create_table(
        "oa_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("letter_id", sa.Integer(), nullable=True),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("entity", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_name", sa.String(200), nullable=True),
        sa.Column("on_behalf_of", sa.Integer(), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_oa_audit_events_letter_id", "oa_audit_events", ["letter_id"])
    op.create_index("ix_oa_audit_events_site_id", "oa_audit_events", ["site_id"])
    op.create_index("ix_oa_audit_events_at", "oa_audit_events", ["at"])

    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('automation.access', 'اتوماسیون اداری: ورود و کارتابل شخصی'),
        ('automation.settings', 'اتوماسیون اداری: تنظیمات سایت (تعداد/حجم/فرمت پیوست، اعلان‌ها، پیشوند شماره‌ی دبیرخانه)')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    codes = "('automation.access','automation.settings')"
    for table in ("role_permissions", "user_permissions"):
        op.execute(f"DELETE FROM {table} WHERE permission_id IN (SELECT id FROM permissions WHERE code IN {codes})")
    op.execute(f"DELETE FROM permissions WHERE code IN {codes}")
    op.drop_table("oa_audit_events")
    op.drop_table("oa_attachment_settings")
    op.drop_table("oa_files")
