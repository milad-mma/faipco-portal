"""اطلاعات بانکی پرسنل (docs/bank-accounts.md)

Revision ID: 118
Revises: 117

- bank_definitions: بانک‌های هر سایت (از پنل ادمین)، اجباری/اختیاری، حالت فیلدها (شماره حساب، شبا، کارت)
- employee_bank_accounts: اطلاعات هر پرسنل برای هر بانک
- employee_bank_account_history: سابقه‌ی ثبت/تغییر
- مجوزها: bank_accounts.view (گزارش و خروجی Excel)، bank_accounts.manage (تعریف بانک‌ها و اصلاح اطلاعات پرسنل)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "118"
down_revision: Union[str, None] = "117"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bank_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("account_number_mode", sa.String(10), nullable=False, server_default="required"),
        sa.Column("sheba_mode", sa.String(10), nullable=False, server_default="required"),
        sa.Column("card_number_mode", sa.String(10), nullable=False, server_default="optional"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "employee_bank_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("bank_id", sa.Integer(), sa.ForeignKey("bank_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_number", sa.String(20), nullable=True),
        sa.Column("sheba", sa.String(26), nullable=True),
        sa.Column("card_number", sa.String(16), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("employee_id", "bank_id", name="uq_employee_bank_account"),
    )
    op.create_table(
        "employee_bank_account_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("bank_id", sa.Integer(), sa.ForeignKey("bank_definitions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("bank_name", sa.String(100), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("changed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("changed_by_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("by_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('bank_accounts.view', 'مشاهده اطلاعات بانکی پرسنل و خروجی Excel'),
        ('bank_accounts.manage', 'تعریف بانک‌ها و اصلاح اطلاعات بانکی پرسنل')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code IN ('bank_accounts.view','bank_accounts.manage'))"
    )
    op.execute("DELETE FROM permissions WHERE code IN ('bank_accounts.view','bank_accounts.manage')")
    op.drop_table("employee_bank_account_history")
    op.drop_table("employee_bank_accounts")
    op.drop_table("bank_definitions")
