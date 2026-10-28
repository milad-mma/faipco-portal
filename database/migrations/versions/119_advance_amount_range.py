"""مساعده: مبلغ دلخواه در محدوده‌ی پله (docs/advances.md)

Revision ID: 119
Revises: 118

- advance_settings.amount_mode (fixed | range، پیش‌فرض fixed = رفتار قبلی) و amount_step (مضرب مبلغ دلخواه، اختیاری)
- advance_tiers.min_amount: حداقل مبلغ دلخواه پله؛ amount در حالت range سقف پله است
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "119"
down_revision: Union[str, None] = "118"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("advance_settings", sa.Column("amount_mode", sa.String(10), nullable=False, server_default="fixed"))
    op.add_column("advance_settings", sa.Column("amount_step", sa.BigInteger(), nullable=True))
    op.add_column("advance_tiers", sa.Column("min_amount", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("advance_tiers", "min_amount")
    op.drop_column("advance_settings", "amount_step")
    op.drop_column("advance_settings", "amount_mode")
