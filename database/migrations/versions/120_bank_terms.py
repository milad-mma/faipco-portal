"""اطلاعات بانکی: پذیرش تعهد «حساب به نام خودِ پرسنل» (docs/bank-accounts.md)

Revision ID: 120
Revises: 119
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "120"
down_revision: Union[str, None] = "119"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employee_bank_terms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("accepted_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("terms_text", sa.String(1000), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("employee_bank_terms")
