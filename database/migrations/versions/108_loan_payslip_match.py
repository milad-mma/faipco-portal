"""وام: تیک خودکار اقساط از روی فیش حقوقی

Revision ID: 108
Revises: 107
Create Date: 2026-10-10

وقتی حسابداری فیش حقوقی را بارگذاری می‌کند، برای هر پرسنل دارای وام در حال بازپرداخت، اگر در بخش «وام» فیش
مبلغی برابر قسطِ پرداخت‌نشده‌ی بعدی کسر شده باشد، همان قسط «پرداخت شد» می‌شود (docs/loans.md).
- loan_installments.paid_source: منبع پرداخت ("payslip:1405/07" یا "payslip-notice:123")؛ خالی = تیک دستی مالی.
  جلوی دوبار تیک خوردن با بارگذاری دوباره‌ی فیش همان ماه را می‌گیرد.
- loan_site_settings.payslip_loan_title: (اختیاری) بخشی از «نام وام» در فیش؛ اگر پر باشد فقط ردیف‌های وامی که
  نامشان شامل آن است بررسی می‌شوند (تا قسط وام بانکی هم‌مبلغ اشتباه گرفته نشود).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "108"
down_revision: Union[str, None] = "107"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("loan_installments", sa.Column("paid_source", sa.String(50), nullable=True))
    op.add_column("loan_site_settings", sa.Column("payslip_loan_title", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("loan_site_settings", "payslip_loan_title")
    op.drop_column("loan_installments", "paid_source")
