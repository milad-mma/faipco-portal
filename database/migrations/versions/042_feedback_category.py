"""add category (subject) field to feedback_messages

Revision ID: 042
Revises: 041
Create Date: 2026-08-31

فیلد «موضوع» (انتقاد/پیشنهاد/نظر) به هر پیام - برای دسته‌بندی و فیلتر
در پنل ادمین. طبق تجربه قبلی این پروژه (Migration 019)، ساخت Type مربوط
به Enum در PostgreSQL باید صریح و جدا از op.add_column انجام شود، وگرنه
با خطای "type already exists" مواجه می‌شویم.

پیام‌های از قبل موجود (اگر باشند) با مقدار پیش‌فرض «نظر» (comment) پر
می‌شوند - چون این نزدیک‌ترین معنای خنثی به یک پیام بدون دسته‌بندی مشخص است.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "042"
down_revision: Union[str, None] = "041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ENUM_NAME = "feedback_category"
_ENUM_VALUES = ("complaint", "suggestion", "comment")


def upgrade() -> None:
    bind = op.get_bind()
    category_enum = sa.Enum(*_ENUM_VALUES, name=_ENUM_NAME)
    category_enum.create(bind, checkfirst=True)

    op.add_column(
        "feedback_messages",
        sa.Column(
            "category",
            postgresql.ENUM(*_ENUM_VALUES, name=_ENUM_NAME, create_type=False),
            nullable=False,
            server_default="comment",
        ),
    )
    # server_default فقط برای پرکردن ردیف‌های قبلی لازم بود؛ از این به بعد
    # هر پیام جدید باید صریحاً موضوع خودش را مشخص کند (اجباری در فرم).
    op.alter_column("feedback_messages", "category", server_default=None)


def downgrade() -> None:
    op.drop_column("feedback_messages", "category")
    sa.Enum(name=_ENUM_NAME).drop(op.get_bind(), checkfirst=True)
