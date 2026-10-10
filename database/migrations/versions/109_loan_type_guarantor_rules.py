"""وام: قواعد ضامن به‌ازای هر نوع وام (نه کل مقررات)

Revision ID: 109
Revises: 108
Create Date: 2026-10-10

حداکثر ضمانت هم‌زمان، حداقل سابقه‌ی ضامن و «ضامن خودش وام تسویه‌نشده نداشته باشد» از loan_policies به loan_types
منتقل می‌شوند؛ مقدار فعلی هر مقررات روی همه‌ی انواع همان مقررات کپی می‌شود.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "109"
down_revision: Union[str, None] = "108"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("loan_types", sa.Column("guarantor_max_active", sa.Integer(), nullable=True))
    op.add_column("loan_types", sa.Column("guarantor_min_service_months", sa.Integer(), nullable=True))
    op.add_column(
        "loan_types",
        sa.Column("guarantor_no_active_loan", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        """
        UPDATE loan_types t SET
            guarantor_max_active = p.guarantor_max_active,
            guarantor_min_service_months = p.guarantor_min_service_months,
            guarantor_no_active_loan = p.guarantor_no_active_loan
        FROM loan_policies p WHERE p.id = t.policy_id
        """
    )
    op.drop_column("loan_policies", "guarantor_no_active_loan")
    op.drop_column("loan_policies", "guarantor_min_service_months")
    op.drop_column("loan_policies", "guarantor_max_active")


def downgrade() -> None:
    op.add_column("loan_policies", sa.Column("guarantor_max_active", sa.Integer(), nullable=True))
    op.add_column("loan_policies", sa.Column("guarantor_min_service_months", sa.Integer(), nullable=True))
    op.add_column(
        "loan_policies",
        sa.Column("guarantor_no_active_loan", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.drop_column("loan_types", "guarantor_no_active_loan")
    op.drop_column("loan_types", "guarantor_min_service_months")
    op.drop_column("loan_types", "guarantor_max_active")
