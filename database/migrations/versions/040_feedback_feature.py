"""add feedback (complaints/suggestions) feature

Revision ID: 040
Revises: 039
Create Date: 2026-08-30

قابلیت «انتقادات و پیشنهادات» - پرسنل می‌توانند پیام بفرستند، با گزینه
درخواست ناشناس‌ماندن. دو مجوز جدید اضافه می‌شود:
    - feedback.view (سایت‌محور): فقط پیام‌های پرسنل همان سایت را می‌بیند
    - feedback.view_all (سراسری): همه پیام‌های سازمان را می‌بیند - با
      همان منطق محرمانگی (پیام ناشناس همچنان ناشناس نمایش داده می‌شود)
یک جدول هم برای فهرست کلمات/عبارات نامناسب (فقط مدیریت‌شده توسط Admin
واقعی) که تعیین می‌کند یک پیام از حالت ناشناس خارج شود یا نه.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "040"
down_revision: Union[str, None] = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feedback_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_anonymous_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("contains_profanity", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "prohibited_phrases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phrase", sa.Text(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('feedback.view', 'مشاهده انتقادات و پیشنهادات پرسنل سایت(های) تحت مدیریت')
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('feedback.view_all', 'مشاهده انتقادات و پیشنهادات همه پرسنل سازمان (سراسری)')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (SELECT id FROM permissions WHERE code IN ('feedback.view', 'feedback.view_all'))
        """
    )
    op.execute("DELETE FROM permissions WHERE code IN ('feedback.view', 'feedback.view_all')")
    op.drop_table("prohibited_phrases")
    op.drop_table("feedback_messages")
