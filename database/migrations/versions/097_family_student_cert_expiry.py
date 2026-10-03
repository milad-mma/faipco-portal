"""family_members.student_cert_expiry: تاریخ اعتبار گواهی اشتغال به تحصیل

Revision ID: 097
Revises: 096
Create Date: 2026-10-03

برای پسر/دختری که به سن تعیین‌شده رسیده و در حال تحصیل است، همراه گواهی اشتغال به تحصیل «تاریخ اعتبار گواهی»
(شمسی، YYYY/MM/DD) هم گرفته می‌شود و مبنای انقضای گواهی، هشدار و شرط «گواهی معتبر» در شمول حق اولاد است.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "097"
down_revision: Union[str, None] = "096"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("family_members", sa.Column("student_cert_expiry", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("family_members", "student_cert_expiry")
