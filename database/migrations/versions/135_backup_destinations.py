"""بکاپ: مقصدهای جدید SFTP، S3 و پوشه/دیسک محلی + بررسی کامل سالم رسیدن فایل

Revision ID: 135
Revises: 134
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "135"
down_revision: Union[str, None] = "134"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [
    sa.Column("local_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("local_path", sa.String(500), nullable=True),
    sa.Column("sftp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("sftp_host", sa.String(255), nullable=True),
    sa.Column("sftp_port", sa.Integer(), nullable=False, server_default="22"),
    sa.Column("sftp_username", sa.String(255), nullable=True),
    sa.Column("sftp_password_encrypted", sa.Text(), nullable=True),
    sa.Column("sftp_path", sa.String(500), nullable=True),
    sa.Column("sftp_host_key", sa.Text(), nullable=True),
    sa.Column("s3_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("s3_endpoint", sa.String(500), nullable=True),
    sa.Column("s3_region", sa.String(100), nullable=True),
    sa.Column("s3_bucket", sa.String(255), nullable=True),
    sa.Column("s3_prefix", sa.String(500), nullable=True),
    sa.Column("s3_access_key", sa.String(255), nullable=True),
    sa.Column("s3_secret_key_encrypted", sa.Text(), nullable=True),
    sa.Column("s3_path_style", sa.Boolean(), nullable=False, server_default=sa.true()),
    sa.Column("verify_full", sa.Boolean(), nullable=False, server_default=sa.false()),
]


def upgrade() -> None:
    for col in _COLUMNS:
        op.add_column("backup_settings", col)


def downgrade() -> None:
    for col in reversed(_COLUMNS):
        op.drop_column("backup_settings", col.name)
