"""add department supervisor

Revision ID: 002
Revises: 001
Create Date: 2026-07-30

اضافه کردن ستون supervisor_user_id به جدول departments.
نکته درباره ترتیب: این ستون در Migration جداگانه (نه در 001) اضافه می‌شود چون
یک وابستگی دوری بین جدول‌ها ایجاد می‌کند (departments -> users -> employees ->
departments). چون در این Migration هر دو جدول departments و users از قبل با
Migration 001 ساخته شده‌اند، اضافه‌کردن این ستون با ALTER TABLE کاملاً بی‌مشکل است.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "departments",
        sa.Column(
            "supervisor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("departments", "supervisor_user_id")
