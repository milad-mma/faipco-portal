"""add presence_sessions table (مانیتورینگ زنده آنلاین‌بودن پرسنل با WebSocket — مدت‌زمان دقیق)

Revision ID: 020
Revises: 019
Create Date: 2026-08-14

برخلاف gps_activity_logs (که هر ۱۰ دقیقه یک عکس لحظه‌ای می‌گرفت)، این جدول
یک Session واقعی با شروع و پایان دقیق ثبت می‌کند — دقیقاً مثل «آنلاین/آفلاین»
یک سیستم چت: لحظه وصل‌شدن WebSocket = شروع، لحظه قطع‌شدن (چه با بستن تب،
چه قطعی شبکه، چه هر چیز دیگر) = پایان. duration_seconds دقیقاً محاسبه‌شده
است، نه تخمینی.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "presence_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        # تا وقتی Session باز است NULL می‌ماند — همین NULL بودن یعنی «الان
        # آنلاین است» (برای گزارش زنده «همین الان کی آنلاینه»)
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("last_latitude", sa.Float(), nullable=True),
        sa.Column("last_longitude", sa.Float(), nullable=True),
        sa.Column("last_accuracy_meters", sa.Float(), nullable=True),
        sa.Column(
            "matched_site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("last_distance_meters", sa.Float(), nullable=True),
        sa.Column("is_within_geofence", sa.Boolean(), nullable=True),
    )
    op.create_index("ix_presence_sessions_employee_id", "presence_sessions", ["employee_id"])
    op.create_index("ix_presence_sessions_connected_at", "presence_sessions", ["connected_at"])
    # برای کوئری سریع «چه کسانی الان آنلاین‌اند» (disconnected_at IS NULL)
    op.create_index(
        "ix_presence_sessions_open",
        "presence_sessions",
        ["disconnected_at"],
        postgresql_where=sa.text("disconnected_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_presence_sessions_open", table_name="presence_sessions")
    op.drop_index("ix_presence_sessions_connected_at", table_name="presence_sessions")
    op.drop_index("ix_presence_sessions_employee_id", table_name="presence_sessions")
    op.drop_table("presence_sessions")
