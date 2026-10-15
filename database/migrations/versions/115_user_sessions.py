"""نشست‌های دستگاه (docs/login-security.md «دستگاه‌های من»)

Revision ID: 115
Revises: 114

- user_sessions: هر ورود یک نشست با شناسه‌ی sid (داخل توکن‌ها)، برچسب دستگاه/مرورگر، IP، آخرین فعالیت و ابطال.
  خروج، ابطال از راه دور و سقف نشست هم‌زمان (تنظیمات امنیت ورود، ۱ تا ۳) روی همین جدول کار می‌کند.
- users.max_sessions: سقف اختصاصی یک کاربر (خالی = پیش‌فرض سیستم).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "115"
down_revision: Union[str, None] = "114"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sid", sa.String(36), nullable=False, unique=True),
        sa.Column("device_label", sa.String(120), nullable=True),
        sa.Column("user_agent", sa.String(300), nullable=True),
        sa.Column("client_app", sa.String(20), nullable=True),  # android | None (وب)
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(30), nullable=True),  # logout | remote | admin | limit | password | deactivated
    )
    op.create_index("ix_user_sessions_user_active", "user_sessions", ["user_id", "revoked_at", "last_seen_at"])
    op.add_column("users", sa.Column("max_sessions", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "max_sessions")
    op.drop_index("ix_user_sessions_user_active", table_name="user_sessions")
    op.drop_table("user_sessions")
