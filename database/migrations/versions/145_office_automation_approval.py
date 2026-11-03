"""اتوماسیون اداری فاز ۳ب: گردش تأیید ترتیبی (پاراف / تأیید / امضا)

- oa_approval_steps
- oa_letters: approval_round، submitted_at

Revision ID: 145
Revises: 144
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "145"
down_revision: Union[str, None] = "144"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oa_approval_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("letter_id", sa.Integer(), sa.ForeignKey("oa_letters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("approver_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approver_name_snapshot", sa.String(200), nullable=False),
        sa.Column("approver_title_snapshot", sa.String(200), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="planned"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("oa_tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("signature_version_id", sa.Integer(), sa.ForeignKey("oa_signature_versions.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("acted_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_oa_approval_steps_letter_id", "oa_approval_steps", ["letter_id"])
    op.create_index("ix_oa_approval_steps_approver_employee_id", "oa_approval_steps", ["approver_employee_id"])
    op.add_column("oa_letters", sa.Column("approval_round", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("oa_letters", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("oa_letters", "submitted_at")
    op.drop_column("oa_letters", "approval_round")
    op.drop_index("ix_oa_approval_steps_approver_employee_id", table_name="oa_approval_steps")
    op.drop_index("ix_oa_approval_steps_letter_id", table_name="oa_approval_steps")
    op.drop_table("oa_approval_steps")
