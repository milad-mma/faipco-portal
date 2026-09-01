"""add backup_settings table (scheduling + SMB/FTP remote targets)

Revision ID: 043
Revises: 042
Create Date: 2026-09-01

قابلیت «زمان‌بندی بکاپ + ارسال خودکار به سرور راه‌دور» (SMB/FTP). یک ردیف
واحد (Singleton، id=1) - چون این تنظیم سراسری سرور است، نه چیزی که بین
چند سایت تکرار شود. طبق تجربه قبلی این پروژه با Enum های PostgreSQL
(Migration 019)، Type های مربوطه صریحاً و جدا از create_table ساخته
می‌شوند تا خطای "type already exists" رخ ندهد.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "043"
down_revision: Union[str, None] = "042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEDULE_TYPE_ENUM = "backup_schedule_type"
_SCHEDULE_TYPE_VALUES = ("daily", "weekly", "interval")
_RETENTION_MODE_ENUM = "backup_retention_mode"
_RETENTION_MODE_VALUES = ("count", "days")


def upgrade() -> None:
    bind = op.get_bind()
    sa.Enum(*_SCHEDULE_TYPE_VALUES, name=_SCHEDULE_TYPE_ENUM).create(bind, checkfirst=True)
    sa.Enum(*_RETENTION_MODE_VALUES, name=_RETENTION_MODE_ENUM).create(bind, checkfirst=True)

    op.create_table(
        "backup_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("schedule_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "schedule_type",
            postgresql.ENUM(*_SCHEDULE_TYPE_VALUES, name=_SCHEDULE_TYPE_ENUM, create_type=False),
            nullable=False,
            server_default="daily",
        ),
        sa.Column("schedule_hour", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("schedule_minute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("schedule_weekday", sa.Integer(), nullable=True),
        sa.Column("schedule_interval_hours", sa.Integer(), nullable=True),
        sa.Column("smb_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("smb_host", sa.String(length=255), nullable=True),
        sa.Column("smb_share", sa.String(length=255), nullable=True),
        sa.Column("smb_path", sa.String(length=500), nullable=True),
        sa.Column("smb_username", sa.String(length=255), nullable=True),
        sa.Column("smb_password_encrypted", sa.Text(), nullable=True),
        sa.Column("smb_domain", sa.String(length=255), nullable=True),
        sa.Column("ftp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ftp_host", sa.String(length=255), nullable=True),
        sa.Column("ftp_port", sa.Integer(), nullable=False, server_default="21"),
        sa.Column("ftp_username", sa.String(length=255), nullable=True),
        sa.Column("ftp_password_encrypted", sa.Text(), nullable=True),
        sa.Column("ftp_path", sa.String(length=500), nullable=True),
        sa.Column("ftp_use_tls", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "retention_mode",
            postgresql.ENUM(*_RETENTION_MODE_VALUES, name=_RETENTION_MODE_ENUM, create_type=False),
            nullable=False,
            server_default="count",
        ),
        sa.Column("retention_count", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("retention_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_success", sa.Boolean(), nullable=True),
        sa.Column("last_run_message", sa.Text(), nullable=True),
    )

    # ردیف Singleton اولیه - تا Backend همیشه بدون چک "آیا رکوردی هست یا نه" بتواند بخواند/بنویسد
    op.execute("INSERT INTO backup_settings (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("backup_settings")
    sa.Enum(name=_RETENTION_MODE_ENUM).drop(op.get_bind(), checkfirst=True)
    sa.Enum(name=_SCHEDULE_TYPE_ENUM).drop(op.get_bind(), checkfirst=True)
