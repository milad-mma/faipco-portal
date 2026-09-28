"""امنیت ورود: گزارش رویدادهای ناموفق، کپچای داخلی و مجوز system.login_security

Revision ID: 092
Revises: 091
Create Date: 2026-09-28

- login_security_events: رویدادهای ناموفق ورود/بازیابی رمز با IP؛ مبنای محدودیت IP، گزارش امنیتی و هشدار.
- captcha_challenges: چالش‌های کپچای تصویری (یک‌بارمصرف، انقضای ۳ دقیقه).
- تنظیمات (تعداد تلاش، مدت قفل‌ها، محدودیت IP، IPهای معاف، کپچا، هشدار) در system_settings با کلید
  login_security ذخیره می‌شود و تا ذخیره نشده، پیش‌فرض‌ها (همان رفتار قبلی ۳/۱دقیقه/۵دقیقه/۱ساعت) اعمال می‌شوند.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "092"
down_revision: Union[str, None] = "091"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "login_security_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("identifier", sa.String(255), nullable=True),
        sa.Column("ip", sa.String(64), nullable=False),
        sa.Column("user_agent", sa.String(200), nullable=True),
        sa.Column("counted", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_login_security_events_created_at", "login_security_events", ["created_at"])
    op.create_index("ix_login_security_events_kind", "login_security_events", ["kind"])
    op.create_index("ix_login_security_events_ip_created", "login_security_events", ["ip", "created_at"])

    op.create_table(
        "captcha_challenges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("answer_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_captcha_challenges_expires_at", "captcha_challenges", ["expires_at"])

    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('system.login_security', 'تنظیمات امنیت ورود، گزارش تلاش‌های ناموفق، رفع قفل و دریافت هشدار (کل سیستم)')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'system.login_security')"
    )
    op.execute("DELETE FROM permissions WHERE code = 'system.login_security'")
    op.drop_index("ix_captcha_challenges_expires_at", table_name="captcha_challenges")
    op.drop_table("captcha_challenges")
    op.drop_index("ix_login_security_events_ip_created", table_name="login_security_events")
    op.drop_index("ix_login_security_events_kind", table_name="login_security_events")
    op.drop_index("ix_login_security_events_created_at", table_name="login_security_events")
    op.drop_table("login_security_events")
