"""کدهای تأیید یک‌بارمصرف (OTP) برای تغییر رمز عبور و تغییر شماره موبایل در پروفایل

Revision ID: 112
Revises: 111
Create Date: 2026-10-12

- purpose: password (تغییر رمز) | mobile (تغییر موبایل)
- channel: sms | email
- destination: مقصدی که کد به آن فرستاده شد (برای mobile همان شماره‌ی جدید؛ کد فقط برای همان شماره معتبر است)
- code_hash: فقط هش SHA-256 کد ذخیره می‌شود
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "112"
down_revision: Union[str, None] = "111"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "verification_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("destination", sa.String(255), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_verification_codes_user_purpose", "verification_codes", ["user_id", "purpose"])


def downgrade() -> None:
    op.drop_index("ix_verification_codes_user_purpose", table_name="verification_codes")
    op.drop_table("verification_codes")
