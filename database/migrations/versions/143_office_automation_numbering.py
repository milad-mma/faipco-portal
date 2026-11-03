"""اتوماسیون اداری فاز ۳ب: دبیرخانه، شمارنده و شماره‌ی رسمی

- oa_secretariats (یک دبیرخانه برای هر سایت؛ پیشوند فقط از پرتال، بدون مقدار پیش‌فرض)
- oa_number_counters (سایت × سال شمسی)، oa_issued_numbers (یکتا، used/void)
- oa_letters: secretariat_id، official_number، registered_at

Revision ID: 143
Revises: 142
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "143"
down_revision: Union[str, None] = "142"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oa_secretariats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False, server_default="دبیرخانه"),
        sa.Column("number_prefix", sa.String(10), nullable=True, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "oa_number_counters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("secretariat_id", sa.Integer(), sa.ForeignKey("oa_secretariats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("jalali_year", sa.Integer(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("secretariat_id", "jalali_year", name="uq_oa_counter_year"),
    )
    op.create_table(
        "oa_issued_numbers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("secretariat_id", sa.Integer(), sa.ForeignKey("oa_secretariats.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("letter_id", sa.Integer(), sa.ForeignKey("oa_letters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(8), nullable=False, server_default="used"),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("secretariat_id", "number", name="uq_oa_issued_number"),
    )
    op.create_index("ix_oa_issued_numbers_letter_id", "oa_issued_numbers", ["letter_id"])

    op.add_column("oa_letters", sa.Column("secretariat_id", sa.Integer(),
                                          sa.ForeignKey("oa_secretariats.id", ondelete="RESTRICT"), nullable=True))
    op.add_column("oa_letters", sa.Column("official_number", sa.String(40), nullable=True))
    op.add_column("oa_letters", sa.Column("registered_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_oa_letters_official_number", "oa_letters", ["official_number"])


def downgrade() -> None:
    op.drop_index("ix_oa_letters_official_number", table_name="oa_letters")
    op.drop_column("oa_letters", "registered_at")
    op.drop_column("oa_letters", "official_number")
    op.drop_column("oa_letters", "secretariat_id")
    op.drop_index("ix_oa_issued_numbers_letter_id", table_name="oa_issued_numbers")
    op.drop_table("oa_issued_numbers")
    op.drop_table("oa_number_counters")
    op.drop_table("oa_secretariats")
