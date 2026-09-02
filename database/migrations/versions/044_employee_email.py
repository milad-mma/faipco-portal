"""add email to Employee + email_column to EmployeeMapping

Revision ID: 044
Revises: 043
Create Date: 2026-09-01

ستون ایمیل پرسنل - از دیتابیس اصلی هر سایت (طبق نگاشت ستون‌ها) همگام‌سازی
می‌شود، دقیقاً همان الگوی mobile/mobile_column موجود. کاربرد اصلی: منبع
ایمیل برای «فراموشی رمز عبور» و امکان آینده «ارسال بکاپ به ایمیل».
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "044"
down_revision: Union[str, None] = "043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("employee_mappings", sa.Column("email_column", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("employee_mappings", "email_column")
    op.drop_column("employees", "email")
