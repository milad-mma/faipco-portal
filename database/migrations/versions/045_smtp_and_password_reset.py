"""add smtp_settings + password_reset_tokens tables

Revision ID: 045
Revises: 044
Create Date: 2026-09-01

دو قابلیت وابسته به هم:
    1) smtp_settings: تنظیمات یک‌جای ارسال ایمیل سراسری (Singleton، id=1) -
       چه برای «فراموشی رمز عبور» چه برای «ارسال بکاپ به ایمیل».
    2) password_reset_tokens: توکن‌های یک‌بارمصرف و کوتاه‌عمر «بازنشانی
       رمز عبور» - هر توکن به یک User مشخص، با زمان انقضا و وضعیت مصرف‌شده.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "045"
down_revision: Union[str, None] = "044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ENCRYPTION_ENUM = "smtp_encryption_mode"
_ENCRYPTION_VALUES = ("none", "starttls", "ssl")


def upgrade() -> None:
    bind = op.get_bind()
    sa.Enum(*_ENCRYPTION_VALUES, name=_ENCRYPTION_ENUM).create(bind, checkfirst=True)

    op.create_table(
        "smtp_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("host", sa.String(length=255), nullable=True),
        sa.Column("port", sa.Integer(), nullable=False, server_default="587"),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("password_encrypted", sa.String(length=500), nullable=True),
        sa.Column("from_address", sa.String(length=255), nullable=True),
        sa.Column("from_name", sa.String(length=255), nullable=True),
        sa.Column(
            "encryption_mode",
            postgresql.ENUM(*_ENCRYPTION_VALUES, name=_ENCRYPTION_ENUM, create_type=False),
            nullable=False,
            server_default="starttls",
        ),
    )
    op.execute("INSERT INTO smtp_settings (id) VALUES (1)")

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_password_reset_tokens_token", "password_reset_tokens", ["token"])


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_token", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_table("smtp_settings")
    sa.Enum(name=_ENCRYPTION_ENUM).drop(op.get_bind(), checkfirst=True)
