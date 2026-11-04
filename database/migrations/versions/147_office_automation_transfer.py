"""اتوماسیون اداری فاز ۳ب: انتقال کارهای باز افراد ترک‌کار/جابه‌جا

- oa_task_transfers
- oa_tasks: transfer_id، reassigned_to_task_id
- مجوز automation.reassign (سایت‌محور)

Revision ID: 147
Revises: 146
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "147"
down_revision: Union[str, None] = "146"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oa_task_transfers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("from_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("from_name_snapshot", sa.String(200), nullable=False),
        sa.Column("to_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("to_name_snapshot", sa.String(200), nullable=False),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="SET NULL"), nullable=True),
        sa.Column("performed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("performed_by_name", sa.String(200), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("visible_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_oa_task_transfers_from_employee_id", "oa_task_transfers", ["from_employee_id"])
    op.create_index("ix_oa_task_transfers_to_employee_id", "oa_task_transfers", ["to_employee_id"])
    op.create_index("ix_oa_task_transfers_site_id", "oa_task_transfers", ["site_id"])
    op.add_column("oa_tasks", sa.Column("transfer_id", sa.Integer(),
                                        sa.ForeignKey("oa_task_transfers.id", ondelete="SET NULL"), nullable=True))
    op.add_column("oa_tasks", sa.Column("reassigned_to_task_id", sa.Integer(), nullable=True))
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('automation.reassign', 'اتوماسیون اداری: انتقال کارهای باز افراد ترک‌کار یا جابه‌جاشده به جایگزین (بدون خواندن محرمانه)')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'automation.reassign')")
    op.execute("DELETE FROM user_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'automation.reassign')")
    op.execute("DELETE FROM permissions WHERE code = 'automation.reassign'")
    op.drop_column("oa_tasks", "reassigned_to_task_id")
    op.drop_column("oa_tasks", "transfer_id")
    op.drop_index("ix_oa_task_transfers_site_id", table_name="oa_task_transfers")
    op.drop_index("ix_oa_task_transfers_to_employee_id", table_name="oa_task_transfers")
    op.drop_index("ix_oa_task_transfers_from_employee_id", table_name="oa_task_transfers")
    op.drop_table("oa_task_transfers")
