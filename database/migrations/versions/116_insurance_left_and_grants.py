"""بیمه تکمیلی: هشدار ترک کار + ثبت‌نام اختصاصی افراد خاص (docs/insurance.md)

Revision ID: 116
Revises: 115

- insurance_registrations.employee_left_at: زمانی که Sync پرسنلِ دارای ثبت‌نام را غیرفعال (ترک کار) کرد.
- insurance_registrations.left_reviewed_at / left_reviewed_by_user_id: بررسی هشدار ترک کار توسط مسئول بیمه؛
  هشدار = پرسنل غیرفعال و بررسی‌نشده. ثبت‌نام با ترک کار حذف نمی‌شود.
- insurance_registration_grants: باز بودن ثبت‌نام برای یک پرسنل خاص در یک بازه‌ی زمانی، حتی وقتی ثبت‌نام سایتش بسته است.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "116"
down_revision: Union[str, None] = "115"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("insurance_registrations", sa.Column("employee_left_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("insurance_registrations", sa.Column("left_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "insurance_registrations",
        sa.Column(
            "left_reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
    )
    op.create_table(
        "insurance_registration_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("insurance_registration_grants")
    op.drop_column("insurance_registrations", "left_reviewed_by_user_id")
    op.drop_column("insurance_registrations", "left_reviewed_at")
    op.drop_column("insurance_registrations", "employee_left_at")
