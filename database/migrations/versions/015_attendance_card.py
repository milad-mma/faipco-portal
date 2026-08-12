"""add attendance_card notice type + attendance_card_receipts table (فیش کارکرد پرسنل — مدیر منابع انسانی)

Revision ID: 015
Revises: 014
Create Date: 2026-08-12

قابلیت «اطلاعیه فیش کارکرد» — دقیقاً هم‌ساختار با «فیش حقوقی» (011):
- notice_type مقدار جدید attendance_card می‌گیرد.
- attendance_card_receipts: برای هر اطلاعیه از نوع attendance_card، یک رکورد
  به‌ازای هر پرسنلی که کدش در اکسل آپلودشده پیدا شده — fields_json خام (لیست
  {label, value}) تا هم PDF از رویش ساخته شود، هم فقط خودِ همان پرسنل به آن
  دسترسی داشته باشد (دقیقاً همان مدل دسترسی فیش حقوقی).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # نکته PostgreSQL: افزودن مقدار جدید به یک Enum موجود، برخلاف ساخت جدول
    # جدید، نیاز به ALTER TYPE دارد (نه بازسازی کامل Type).
    op.execute("ALTER TYPE notice_type_enum ADD VALUE IF NOT EXISTS 'attendance_card'")

    op.create_table(
        "attendance_card_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "notice_id",
            sa.Integer(),
            sa.ForeignKey("notices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            sa.Integer(),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_personnel_code", sa.String(length=64), nullable=False),
        sa.Column("fields_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("notice_id", "employee_id", name="uq_attendance_card_receipt_notice_employee"),
    )
    op.create_index(
        "ix_attendance_card_receipts_employee_id", "attendance_card_receipts", ["employee_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_attendance_card_receipts_employee_id", table_name="attendance_card_receipts")
    op.drop_table("attendance_card_receipts")
    # نکته: PostgreSQL حذف یک مقدار از Enum را پشتیبانی نمی‌کند — Downgrade
    # این مقدار را در Type باقی می‌گذارد (بی‌خطر، چون دیگر جایی استفاده نمی‌شود).
