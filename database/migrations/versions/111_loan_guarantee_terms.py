"""وام: قوانین و مقررات ضمانت و متن تیک پذیرش (برای هر نسخه‌ی مقررات)

Revision ID: 111
Revises: 110
Create Date: 2026-10-12

ضامن هنگام قبول ضمانت متن قوانین را همان‌جا در کارتابل می‌بیند و باید تیک «… خوانده‌ام و قبول دارم» را بزند.
- loan_policies.guarantee_terms: متن قوانین و مقررات ضمانت (اختیاری)
- loan_policies.guarantee_agree_label: متن تیک پذیرش (خالی = متن پیش‌فرض)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "111"
down_revision: Union[str, None] = "110"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("loan_policies", sa.Column("guarantee_terms", sa.Text(), nullable=True))
    op.add_column("loan_policies", sa.Column("guarantee_agree_label", sa.String(300), nullable=True))


def downgrade() -> None:
    op.drop_column("loan_policies", "guarantee_agree_label")
    op.drop_column("loan_policies", "guarantee_terms")
