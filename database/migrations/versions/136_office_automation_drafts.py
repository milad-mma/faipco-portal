"""اتوماسیون اداری فاز ۲: قالب نسخه‌دار و پیش‌نویس نامه

- oa_templates، oa_template_versions (چیدمان مستقل A4 و A5)
- oa_letters (فاز ۲ فقط پیش‌نویس شخصی)، oa_letter_versions
- مجوزها: automation.compose (نوشتن پیش‌نویس)، automation.templates (مدیریت قالب و سربرگ) — به هیچ نقشی داده نمی‌شوند

Revision ID: 136
Revises: 135
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "136"
down_revision: Union[str, None] = "135"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "oa_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("default_paper_size", sa.String(4), nullable=False, server_default="A4"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("current_version_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_ts(),
    )
    op.create_index("ix_oa_templates_site_id", "oa_templates", ["site_id"])
    op.create_table(
        "oa_template_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("oa_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("layouts", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("template_id", "version_no", name="uq_oa_template_version"),
    )
    op.create_index("ix_oa_template_versions_template_id", "oa_template_versions", ["template_id"])

    op.create_table(
        "oa_letters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False, server_default="internal"),
        sa.Column("confidentiality", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("urgency", sa.String(12), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("subject", sa.String(300), nullable=False, server_default=""),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("creator_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("current_version_id", sa.Integer(), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("discarded_at", sa.DateTime(timezone=True), nullable=True),
        *_ts(),
    )
    for col in ("site_id", "status", "created_by", "creator_employee_id"):
        op.create_index(f"ix_oa_letters_{col}", "oa_letters", [col])
    op.create_table(
        "oa_letter_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("letter_id", sa.Integer(), sa.ForeignKey("oa_letters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False, server_default=""),
        sa.Column("body_html", sa.Text(), nullable=False, server_default=""),
        sa.Column("paper_size", sa.String(4), nullable=False, server_default="A4"),
        sa.Column("template_version_id", sa.Integer(),
                  sa.ForeignKey("oa_template_versions.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="editing"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
        *_ts(),
        sa.UniqueConstraint("letter_id", "version_no", name="uq_oa_letter_version"),
    )
    op.create_index("ix_oa_letter_versions_letter_id", "oa_letter_versions", ["letter_id"])

    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('automation.compose', 'اتوماسیون اداری: ایجاد و ارسال نامه‌ی داخلی (فاز ۲: پیش‌نویس)'),
        ('automation.templates', 'اتوماسیون اداری: مدیریت قالب و سربرگ نامه')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    codes = "('automation.compose','automation.templates')"
    for table in ("role_permissions", "user_permissions"):
        op.execute(f"DELETE FROM {table} WHERE permission_id IN (SELECT id FROM permissions WHERE code IN {codes})")
    op.execute(f"DELETE FROM permissions WHERE code IN {codes}")
    op.drop_table("oa_letter_versions")
    op.drop_table("oa_letters")
    op.drop_table("oa_template_versions")
    op.drop_table("oa_templates")
