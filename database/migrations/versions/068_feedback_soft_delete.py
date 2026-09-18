"""add soft delete to feedback messages

Revision ID: 068
Revises: 067
Create Date: 2026-09-18

طبق درخواست صریح کاربر: «تأیید قبل از حذف در سطح دیتابیس».

قبلاً تنها عملیات مدیریتی روی یک پیام انتقاد/پیشنهاد، حذف دائمی بود -
یک کلیک اشتباه یعنی از دست رفتن همیشگی بازخورد پرسنل، بدون هیچ راه
بازگشتی. حالا حذف «نرم» است: رکورد در دیتابیس می‌ماند و فقط
علامت‌گذاری می‌شود، پس در صورت نیاز قابل‌بازیابی است.

is_deleted ایندکس دارد چون همه Query های فهرست پیام‌ها روی آن فیلتر
می‌کنند (پیام‌های حذف‌شده نباید در فهرست‌ها بیایند).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "068"
down_revision: Union[str, None] = "067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "feedback_messages",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("feedback_messages", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "feedback_messages",
        sa.Column(
            "deleted_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_feedback_messages_is_deleted", "feedback_messages", ["is_deleted"])


def downgrade() -> None:
    op.drop_index("ix_feedback_messages_is_deleted", table_name="feedback_messages")
    op.drop_column("feedback_messages", "deleted_by_user_id")
    op.drop_column("feedback_messages", "deleted_at")
    op.drop_column("feedback_messages", "is_deleted")
