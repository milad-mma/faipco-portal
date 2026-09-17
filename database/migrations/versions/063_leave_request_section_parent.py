"""add section_parent_column - escalate to parent section when self-managed

Revision ID: 063
Revises: 062
Create Date: 2026-09-17

کشف حیاتی (تأییدشده با بررسی مستقیم دیتابیس Kara و مقایسه با نتیجه
واقعی ثبت‌شده توسط کاراوب برای یک درخواست واقعی): وقتی یک نفر خودش مدیر
بخش خودش است (مثلاً پرسنل ۲۲۵۷۳۵ که خودش ManagerEmp_No واحد «آی‌تی»
است)، هیچ‌کس نمی‌تواند تأییدکننده خودش باشد - نرم‌افزار واقعی در این
حالت به مدیرِ واحدِ بالادستی (پدر همان بخش، از طریق ستون TFather) صعود
می‌کند - نه اینکه خودِ فرد را به‌عنوان تأییدکننده در نظر بگیرد.

مثال تأییدشده: پرسنل ۲۲۵۷۳۵ (بخش ۱۸ - آی‌تی) خودش ManagerEmp_No آن بخش
است؛ چون TFather بخش ۱۸ برابر ۱ (مدیریت) است و ManagerEmp_No بخش ۱ برابر
۲۲۲۰۸۸ است (متفاوت از خودِ فرد)، تأییدکننده واقعی باید ۲۲۲۰۸۸ باشد - نه
۲۲۵۷۳۵.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "063"
down_revision: Union[str, None] = "062"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leave_request_mappings",
        sa.Column("section_parent_column", sa.String(length=128), nullable=True, server_default="TFather"),
    )


def downgrade() -> None:
    op.drop_column("leave_request_mappings", "section_parent_column")
