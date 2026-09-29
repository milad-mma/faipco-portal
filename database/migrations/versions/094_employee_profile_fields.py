"""پرسنل: مدرک تحصیلی و آدرس (از منبع، فقط خواندنی در «مشخصات کاربری») و نگاشت ستون آدرس

Revision ID: 094
Revises: 093
Create Date: 2026-09-29

- employees.education_title: عنوان مدرک (Sync از نگاشت موجود education_column + Lookup؛ کاراوب: Grade_No → Grades.Title)
- employees.address: آدرس (Sync از نگاشت جدید employee_mappings.address_column؛ کاراوب: Address)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "094"
down_revision: Union[str, None] = "093"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("education_title", sa.String(128), nullable=True))
    op.add_column("employees", sa.Column("address", sa.String(500), nullable=True))
    op.add_column("employee_mappings", sa.Column("address_column", sa.String(128), nullable=True))
    # کاراوب: اگر نگاشت سایتی جدول Employee است، ستون Address پیش‌فرض گذاشته می‌شود (قابل تغییر از تنظیمات سایت)
    op.execute("UPDATE employee_mappings SET address_column = 'Address' WHERE lower(table_name) IN ('employee', 'dbo.employee')")


def downgrade() -> None:
    op.drop_column("employee_mappings", "address_column")
    op.drop_column("employees", "address")
    op.drop_column("employees", "education_title")
