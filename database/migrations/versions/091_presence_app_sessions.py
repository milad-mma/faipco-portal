"""presence_sessions: نوع نشست (اپ/GPS)، آخرین زمان دیده‌شده و دستگاه؛ بستن نشست‌های رهاشده

Revision ID: 091
Revises: 090
Create Date: 2026-09-28

- kind: "app" = پرتال باز است (همه‌ی پرسنل، بدون نیاز به GPS)، "gps" = داخل محدوده‌ی سایت (رفتار قبلی).
- last_seen_at: زمان آخرین Heartbeat؛ Job دوره‌ای نشست‌های باز بدون Heartbeat اخیر را با همین زمان می‌بندد
  (قبلاً بعد از ری‌استارت سرور، نشست‌های باز برای همیشه «الان آنلاین» می‌ماندند).
- client: برچسب کوتاه دستگاه/مرورگر.
- نشست‌های بازِ قبلی (بدون last_seen_at) زمان پایان واقعی‌شان معلوم نیست: با disconnected_at = connected_at و
  مدت نامشخص (NULL) بسته می‌شوند.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "091"
down_revision: Union[str, None] = "090"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("presence_sessions", sa.Column("kind", sa.String(10), nullable=False, server_default="gps"))
    op.add_column("presence_sessions", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("presence_sessions", sa.Column("client", sa.String(120), nullable=True))
    op.create_index("ix_presence_sessions_kind_open", "presence_sessions", ["kind", "disconnected_at"])
    op.execute("UPDATE presence_sessions SET disconnected_at = connected_at, duration_seconds = NULL WHERE disconnected_at IS NULL")


def downgrade() -> None:
    op.drop_index("ix_presence_sessions_kind_open", table_name="presence_sessions")
    op.drop_column("presence_sessions", "client")
    op.drop_column("presence_sessions", "last_seen_at")
    op.drop_column("presence_sessions", "kind")
