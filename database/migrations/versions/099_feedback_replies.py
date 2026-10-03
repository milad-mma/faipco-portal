"""انتقادات و پیشنهادات: گفتگو (پاسخ بازبین و پیگیری فرستنده)، وضعیت پیام و مجوز feedback.reply

Revision ID: 099
Revises: 098
Create Date: 2026-10-03

- feedback_messages.status: new | in_review | answered | closed (پیام‌های قبلی: new)
- feedback_messages.sender_seen_at: آخرین بار که فرستنده گفتگو را دیده (نشانگر «پاسخ جدید» خودِ فرستنده)
- feedback_replies: پاسخ‌های دوطرفه؛ is_from_sender طرف گفتگو را مستقل از کاربر نگه می‌دارد
- مجوز feedback.reply (سایت‌محور): پاسخ دادن و تغییر وضعیت؛ مشاهده همچنان با feedback.view / feedback.view_all
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "099"
down_revision: Union[str, None] = "098"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("feedback_messages", sa.Column("status", sa.String(16), nullable=False, server_default="new"))
    op.add_column("feedback_messages", sa.Column("sender_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "feedback_replies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("feedback_id", sa.Integer(), sa.ForeignKey("feedback_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_from_sender", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("contains_profanity", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_feedback_replies_feedback_created", "feedback_replies", ["feedback_id", "created_at"])
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('feedback.reply', 'پاسخ به انتقادات و پیشنهادات و تغییر وضعیت پیام (گفتگو با فرستنده بدون دیدن هویت او)')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'feedback.reply')")
    op.execute("DELETE FROM permissions WHERE code = 'feedback.reply'")
    op.drop_index("ix_feedback_replies_feedback_created", table_name="feedback_replies")
    op.drop_table("feedback_replies")
    op.drop_column("feedback_messages", "sender_seen_at")
    op.drop_column("feedback_messages", "status")
