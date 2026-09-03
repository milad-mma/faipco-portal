"""add sms_settings table + channel column to password_reset_tokens

Revision ID: 048
Revises: 047
Create Date: 2026-09-03

قابلیت «فراموشی رمز عبور از طریق پیامک» با ippanel Edge API
(https://ippanelcom.github.io/Edge-Document/docs/send/) - یک ردیف تنظیمات
Singleton (مثل smtp_settings)، و یک ستون channel روی password_reset_tokens
(فقط برای گزارش/نمایش - منطق اعتبارسنجی توکن برای هر دو کانال یکسان است).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "048"
down_revision: Union[str, None] = "047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SENDING_TYPE_ENUM = "sms_sending_type"
_SENDING_TYPE_VALUES = ("webservice", "pattern")
_CHANNEL_ENUM = "password_reset_channel"
_CHANNEL_VALUES = ("email", "sms")


def upgrade() -> None:
    bind = op.get_bind()
    sa.Enum(*_SENDING_TYPE_VALUES, name=_SENDING_TYPE_ENUM).create(bind, checkfirst=True)
    sa.Enum(*_CHANNEL_VALUES, name=_CHANNEL_ENUM).create(bind, checkfirst=True)

    op.create_table(
        "sms_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("api_key_encrypted", sa.String(length=500), nullable=True),
        sa.Column("from_number", sa.String(length=32), nullable=True),
        sa.Column(
            "sending_type",
            postgresql.ENUM(*_SENDING_TYPE_VALUES, name=_SENDING_TYPE_ENUM, create_type=False),
            nullable=False,
            server_default="pattern",
        ),
        sa.Column("pattern_code", sa.String(length=128), nullable=True),
        sa.Column("webservice_message_template", sa.String(length=500), nullable=True),
    )
    op.execute("INSERT INTO sms_settings (id) VALUES (1)")

    op.add_column(
        "password_reset_tokens",
        sa.Column(
            "channel",
            postgresql.ENUM(*_CHANNEL_VALUES, name=_CHANNEL_ENUM, create_type=False),
            nullable=False,
            server_default="email",
        ),
    )


def downgrade() -> None:
    op.drop_column("password_reset_tokens", "channel")
    op.drop_table("sms_settings")
    sa.Enum(name=_CHANNEL_ENUM).drop(op.get_bind(), checkfirst=True)
    sa.Enum(name=_SENDING_TYPE_ENUM).drop(op.get_bind(), checkfirst=True)
