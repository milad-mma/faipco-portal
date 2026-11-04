"""اتوماسیون اداری فاز ۳ب: ابطال نامه و اصلاحیه

- oa_letters: cancelled_at، cancel_reason، cancelled_by_user_id، cancelled_by_name
- مجوز automation.cancel (سایت‌محور)

Revision ID: 146
Revises: 145
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "146"
down_revision: Union[str, None] = "145"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("oa_letters", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("oa_letters", sa.Column("cancel_reason", sa.Text(), nullable=True))
    op.add_column("oa_letters", sa.Column("cancelled_by_user_id", sa.Integer(),
                                          sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("oa_letters", sa.Column("cancelled_by_name", sa.String(200), nullable=True))
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('automation.cancel', 'اتوماسیون اداری: ابطال نامه‌ی ثبت‌شده (با دلیل؛ شماره باطل می‌شود و نامه و سابقه می‌ماند)')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'automation.cancel')")
    op.execute("DELETE FROM user_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'automation.cancel')")
    op.execute("DELETE FROM permissions WHERE code = 'automation.cancel'")
    for col in ("cancelled_by_name", "cancelled_by_user_id", "cancel_reason", "cancelled_at"):
        op.drop_column("oa_letters", col)
