"""اتوماسیون اداری فاز ۳الف (بخش دوم): پاسخ/عطف/پیرو و تنظیمات اعلان شخصی

- oa_letter_relations: from_letter_id (نامه‌ی جدید) → to_letter_id (نامه‌ی مرجع)، type: reply | reference (عطف) | follow_up (پیرو).
  رابطه هیچ دسترسی‌ای نمی‌دهد؛ موضوع نامه‌ی مرتبط فقط برای کسی نمایش داده می‌شود که به آن دسترسی دارد.
- oa_notification_prefs: رویدادهایی که هر پرسنل برایشان اعلان گوشی/مرورگر نمی‌خواهد (پیش‌فرض: همه روشن).

Revision ID: 139
Revises: 138
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "139"
down_revision: Union[str, None] = "138"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oa_letter_relations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("from_letter_id", sa.Integer(), sa.ForeignKey("oa_letters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_letter_id", sa.Integer(), sa.ForeignKey("oa_letters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(12), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("from_letter_id", "to_letter_id", name="uq_oa_letter_relation"),
    )
    op.create_index("ix_oa_letter_relations_from", "oa_letter_relations", ["from_letter_id"])
    op.create_index("ix_oa_letter_relations_to", "oa_letter_relations", ["to_letter_id"])
    op.create_table(
        "oa_notification_prefs",
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("disabled_events", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("oa_notification_prefs")
    op.drop_table("oa_letter_relations")
