"""ماژول «درخواست مساعده» (docs/advances.md)

Revision ID: 114
Revises: 113

- advance_settings: تنظیمات هر سایت (فعال/غیرفعال، مدیر سایت مساعده، بازه‌ی روزهای مجاز ثبت در ماه، حداکثر دفعات در
  ماه، متن قوانین برای پرسنل)
- advance_tiers: پله‌های سابقه ← مبلغ ثابت مساعده (هر سایت، جدا برای هر گروه: پرسنل / سرپرستان / مدیران)
- advance_group_members: تعیین دستی گروه یک پرسنل (مدیر، یا سرپرستی که در زنجیره‌ی تأییدکننده نیست)
- advance_requests: درخواست‌ها (مبلغ از پله، سابقه، ماه شمسی، مسیر مدیر واحد ← مدیر سایت ← مالی، پرداخت)
- advance_request_events: تاریخچه‌ی هر درخواست
- مجوزها: advances.policy / advances.finance / advances.view
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "114"
down_revision: Union[str, None] = "113"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ts():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "advance_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "site_manager_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("window_from_day", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("window_to_day", sa.Integer(), nullable=False, server_default="31"),
        sa.Column("max_per_month", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("rules_text", sa.Text(), nullable=True),
        *_ts(),
    )
    op.create_table(
        "advance_tiers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("group", sa.String(20), nullable=False, server_default="staff"),  # staff | supervisor | manager
        sa.Column("min_months", sa.Integer(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint("site_id", "group", "min_months", name="uq_advance_tier_site_group_months"),
    )
    op.create_table(
        "advance_group_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True
        ),
        sa.Column("group", sa.String(20), nullable=False),  # supervisor | manager
    )
    op.create_table(
        "advance_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("employee_group", sa.String(20), nullable=False, server_default="staff"),  # گروه هنگام ثبت
        sa.Column("service_months", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("request_month", sa.String(7), nullable=False, index=True),  # YYYY/MM شمسی
        sa.Column("status", sa.String(30), nullable=False, index=True),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "unit_manager_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "site_manager_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "current_approver_employee_id",
            sa.Integer(),
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("paid_date", sa.String(10), nullable=True),  # تاریخ پرداخت شمسی YYYY/MM/DD
        sa.Column("paid_note", sa.String(500), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        *_ts(),
    )
    op.create_table(
        "advance_request_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "request_id",
            sa.Integer(),
            sa.ForeignKey("advance_requests.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("actor_label", sa.String(255), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('advances.policy', 'مساعده: تنظیمات سایت (فعال‌سازی، مدیر سایت، بازه‌ی ثبت، پله‌های سابقه، متن اعلان‌ها)'),
        ('advances.finance', 'مساعده: تأیید نهایی و ثبت پرداخت توسط واحد مالی'),
        ('advances.view', 'مساعده: مشاهده‌ی همه‌ی درخواست‌های سایت')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    codes = "('advances.policy', 'advances.finance', 'advances.view')"
    op.execute(f"DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code IN {codes})")
    op.execute(f"DELETE FROM user_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code IN {codes})")
    op.execute(f"DELETE FROM permissions WHERE code IN {codes}")
    op.drop_table("advance_request_events")
    op.drop_table("advance_requests")
    op.drop_table("advance_group_members")
    op.drop_table("advance_tiers")
    op.drop_table("advance_settings")
