"""گزارش خطاها: جدول‌های error_logs و error_log_occurrences + مجوز system.logs

Revision ID: 105
Revises: 104
Create Date: 2026-10-07

- error_logs: یک ردیف برای هر «گروه» خطای یکسان (fingerprint یکتا) با تعداد و اولین/آخرین زمان، وضعیت «حل شد».
- error_log_occurrences: هر رخداد با کد پیگیری، کاربر، درخواست؛ با حذف گروه حذف می‌شود.
- مجوز system.logs: دیدن گزارش خطاها و تنظیم ایمیل هشدار (کل سیستم).
هر دو جدول با Job روزانه بعد از ۳۰ روز پاک‌سازی می‌شوند.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "105"
down_revision: Union[str, None] = "104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "error_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fingerprint", sa.String(40), nullable=False, unique=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("source", sa.String(120), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_request", sa.String(300), nullable=True),
        sa.Column("last_user_id", sa.Integer(), nullable=True),
        sa.Column("last_user_label", sa.String(200), nullable=True),
        sa.Column("last_ip", sa.String(64), nullable=True),
        sa.Column("last_context", sa.JSON(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_error_logs_kind", "error_logs", ["kind"])
    op.create_index("ix_error_logs_category", "error_logs", ["category"])
    op.create_index("ix_error_logs_last_seen", "error_logs", ["last_seen"])
    op.create_table(
        "error_log_occurrences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("error_id", sa.Integer(), sa.ForeignKey("error_logs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(16), nullable=True),
        sa.Column("request", sa.String(300), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("user_label", sa.String(200), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("context", sa.JSON(), nullable=True),
    )
    op.create_index("ix_error_log_occurrences_error_id", "error_log_occurrences", ["error_id"])
    op.create_index("ix_error_log_occurrences_occurred_at", "error_log_occurrences", ["occurred_at"])
    op.create_index("ix_error_log_occurrences_request_id", "error_log_occurrences", ["request_id"])
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('system.logs', 'گزارش خطاها: خطاهای سرور، درخواست‌های کند، خطاهای مرورگر و اپ اندروید، و ایمیل هشدار')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'system.logs')")
    op.execute("DELETE FROM permissions WHERE code = 'system.logs'")
    op.drop_table("error_log_occurrences")
    op.drop_table("error_logs")
