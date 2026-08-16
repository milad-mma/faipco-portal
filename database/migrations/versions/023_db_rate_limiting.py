"""add DB-backed rate limiting tables (رفع دور زدن Lockout ورود بین چند Worker — یافته تست نفوذ زنده)

Revision ID: 023
Revises: 022
Create Date: 2026-08-16

⚠️ رفع یک یافته تأییدشده از تست نفوذ زنده: چون سرویس با چند Worker
(uvicorn --workers 2) اجرا می‌شود و شمارنده‌های Lockout قبلی فقط در
حافظه پایتون (مخصوص هر Worker، نه مشترک) نگه‌داری می‌شدند، تلاش‌های
ناموفق ورود بین Worker ها پخش می‌شدند و هیچ‌کدام به آستانه قفل نمی‌رسیدند
— یعنی عملاً Lockout قابل‌دورزدن بود (نه با تکنیک خاص مهاجم، فقط با
توزیع طبیعی Load Balancer). این Migration دو جدول می‌سازد تا این
شمارنده‌ها بین همه Worker ها (و حتی چند سرور، اگر در آینده لازم شد)
مشترک باشند.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("identifier", sa.String(length=255), nullable=False),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_login_attempts_identifier", "login_attempts", ["identifier"], unique=True)

    op.create_table(
        "message_rate_limits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_message_rate_limits_user_id", "message_rate_limits", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_message_rate_limits_user_id", table_name="message_rate_limits")
    op.drop_table("message_rate_limits")
    op.drop_index("ix_login_attempts_identifier", table_name="login_attempts")
    op.drop_table("login_attempts")
