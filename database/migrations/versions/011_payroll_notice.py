"""add payroll notice support (notice_type + payroll_receipts table)

Revision ID: 011
Revises: 010
Create Date: 2026-08-10

قابلیت «اطلاعیه فیش حقوقی»:
- notices.notice_type: تمایز اطلاعیه معمولی از اطلاعیه فیش حقوقی (پیش‌فرض normal
  برای همه رکوردهای قبلی — هیچ رفتار موجودی تغییر نمی‌کند).
- payroll_receipts: برای هر اطلاعیه از نوع payroll، یک رکورد به‌ازای هر پرسنلی
  که کدش در XML آپلودشده پیدا شده. fields_json تمام فیلدهای همان
  <SalaryReceiptItem> است (به‌صورت خام، بدون فرض ساختار خاص) — تا هم PDF از
  روی آن ساخته شود و هم هیچ‌کس جز خودِ همان پرسنل به آن دسترسی نداشته باشد.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notices",
        sa.Column(
            "notice_type",
            sa.Enum("normal", "payroll", name="notice_type_enum"),
            nullable=False,
            server_default="normal",
        ),
    )

    op.create_table(
        "payroll_receipts",
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
        # کد پرسنلی همان لحظه‌ی Upload (Snapshot) — برای Audit، مستقل از
        # تغییرات احتمالی بعدی personnel_code خودِ پرسنل.
        sa.Column("source_personnel_code", sa.String(length=64), nullable=False),
        # تمام فیلدهای <SalaryReceiptItem> به‌صورت JSON (لیستی از {label, value}
        # برای حفظ ترتیب اصلی ستون‌های XML).
        sa.Column("fields_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("notice_id", "employee_id", name="uq_payroll_receipt_notice_employee"),
    )
    op.create_index(
        "ix_payroll_receipts_employee_id", "payroll_receipts", ["employee_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_payroll_receipts_employee_id", table_name="payroll_receipts")
    op.drop_table("payroll_receipts")
    op.drop_column("notices", "notice_type")
    op.execute("DROP TYPE IF EXISTS notice_type_enum")
