"""ماژول «درخواست وام»: مقررات هر سایت، انواع وام، درخواست، ضامن، تاریخچه، اقساط و مجوزها

Revision ID: 107
Revises: 106
Create Date: 2026-10-10

مقررات وام برای هر سایت جدا و نسخه‌دار (تاریخ اجرا) است؛ مسیر تأیید (ضامن‌ها ← مدیر واحد ← مدیر سایت ← مالی)
قابل چیدن است. بدهی وام در کاراوب نیست، پس پرداخت/اقساط/تسویه را واحد مالی در پرتال ثبت می‌کند. docs/loans.md
مجوزها: loans.policy (مقررات و تنظیمات سایت)، loans.finance (صف، پرداخت، اقساط، تسویه)، loans.view (گزارش).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "107"
down_revision: Union[str, None] = "106"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "loan_site_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "site_manager_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("last_queue_seq", sa.Integer(), nullable=False, server_default="0"),
        *_ts(),
    )
    op.create_table(
        "loan_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("effective_from", sa.String(10), nullable=False),
        sa.Column("rules_text", sa.Text(), nullable=True),
        sa.Column("block_if_unsettled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("approval_steps", sa.JSON(), nullable=False),
        sa.Column("guarantor_max_active", sa.Integer(), nullable=True),
        sa.Column("guarantor_min_service_months", sa.Integer(), nullable=True),
        sa.Column("guarantor_no_active_loan", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_ts(),
    )
    op.create_table(
        "loan_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "policy_id", sa.Integer(), sa.ForeignKey("loan_policies.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("max_amount", sa.BigInteger(), nullable=False),
        sa.Column("min_service_months", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("guarantor_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extra_requirement", sa.String(500), nullable=True),
        sa.Column("out_of_queue", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "loan_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("loan_policies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("loan_type_id", sa.Integer(), sa.ForeignKey("loan_types.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type_title", sa.String(200), nullable=False),
        sa.Column("out_of_queue", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("extra_requirement", sa.String(500), nullable=True),
        sa.Column("amount_requested", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("service_months", sa.Integer(), nullable=True),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, index=True),
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
        sa.Column("queue_seq", sa.Integer(), nullable=True),
        sa.Column("amount_approved", sa.BigInteger(), nullable=True),
        sa.Column("extra_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("finance_note", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_manual", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_ts(),
    )
    op.create_table(
        "loan_request_guarantors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "request_id", sa.Integer(), sa.ForeignKey("loan_requests.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "loan_request_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "request_id", sa.Integer(), sa.ForeignKey("loan_requests.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("actor_label", sa.String(255), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "loan_installments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "request_id", sa.Integer(), sa.ForeignKey("loan_requests.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("due_month", sa.String(7), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "loan_service_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True
        ),
        sa.Column("start_date", sa.String(10), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("set_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_ts(),
    )
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('loans.policy', 'وام: چیدن مقررات وام، مسیر تأیید و تنظیمات سایت (فعال‌سازی، مدیر سایت)'),
        ('loans.finance', 'وام: واحد مالی — صف نوبت، پرداخت و تعیین اقساط، تسویه، ثبت دستی و اصلاح سابقه'),
        ('loans.view', 'وام: مشاهده‌ی همه‌ی درخواست‌های وام سایت')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    codes = "('loans.policy','loans.finance','loans.view')"
    op.execute(f"DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code IN {codes})")
    op.execute(f"DELETE FROM user_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code IN {codes})")
    op.execute(f"DELETE FROM permissions WHERE code IN {codes}")
    for table in (
        "loan_service_overrides",
        "loan_installments",
        "loan_request_events",
        "loan_request_guarantors",
        "loan_requests",
        "loan_types",
        "loan_policies",
        "loan_site_settings",
    ):
        op.drop_table(table)
