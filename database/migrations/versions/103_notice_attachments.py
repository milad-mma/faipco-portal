"""اطلاعیه‌ها: پیوست تصویر/PDF برای اطلاعیه‌ی متنی + مجوز notices.attachments

Revision ID: 103
Revises: 102
Create Date: 2026-10-05

- notice_attachments: بایت‌های فایل (bytea)، نام، نوع، حجم؛ با حذف فیزیکی اطلاعیه حذف می‌شود (CASCADE)
- مجوز notices.attachments (سایت‌محور): افزودن پیوست؛ برای همه‌ی سایت‌های مخاطب لازم است
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "103"
down_revision: Union[str, None] = "102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notice_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("notice_id", sa.Integer(), sa.ForeignKey("notices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(160), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notice_attachments_notice_id", "notice_attachments", ["notice_id"])
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('notices.attachments', 'افزودن تصویر و فایل PDF به اطلاعیه‌ی متنی (برای همه‌ی سایت‌های مخاطب لازم است)')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'notices.attachments')")
    op.execute("DELETE FROM permissions WHERE code = 'notices.attachments'")
    op.drop_index("ix_notice_attachments_notice_id", table_name="notice_attachments")
    op.drop_table("notice_attachments")
