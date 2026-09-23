"""employees: birth_date_jalali / hire_date_jalali / gender + employee_mappings: hire_date_column / gender_column

Revision ID: 084
Revises: 083
Create Date: 2026-09-23

ماژول «بیمه تکمیلی» (بازسازی سامانه insurance.faipco.ir داخل پرتال) به تاریخ
تولد کامل، تاریخ استخدام و جنسیت پرسنل نیاز دارد. قبلاً فقط روز/ماه تولد
ذخیره می‌شد. این مقادیر مثل بقیه فیلدها از کاراوب (Employee.Birth_Date /
Emp_Date / Gender - همه شمسی فشرده / ۱=مرد ۲=زن) Sync می‌شوند؛ ستون‌های
جدید نگاشت پرسنل، خالی = Sync نمی‌شود.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "084"
down_revision: Union[str, None] = "083"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("birth_date_jalali", sa.String(10), nullable=True))
    op.add_column("employees", sa.Column("hire_date_jalali", sa.String(10), nullable=True))
    op.add_column("employees", sa.Column("gender", sa.SmallInteger(), nullable=True))
    op.add_column("employee_mappings", sa.Column("hire_date_column", sa.String(128), nullable=True))
    op.add_column("employee_mappings", sa.Column("gender_column", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("employee_mappings", "gender_column")
    op.drop_column("employee_mappings", "hire_date_column")
    op.drop_column("employees", "gender")
    op.drop_column("employees", "hire_date_jalali")
    op.drop_column("employees", "birth_date_jalali")
