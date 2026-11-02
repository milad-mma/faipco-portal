"""اتوماسیون اداری: منشی (ارسال به نام مدیر) و پیوست هنگام ثبت نتیجه‌ی اقدام

- oa_secretaries (مدیر ← منشی)
- oa_letters.principal_employee_id (نامه‌ای که منشی به نام مدیر می‌فرستد)
- oa_task_attachments (فایل‌های نتیجه‌ی اقدام)

Revision ID: 142
Revises: 141
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "142"
down_revision: Union[str, None] = "141"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oa_secretaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("principal_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("secretary_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("principal_employee_id", "secretary_employee_id", name="uq_oa_secretary_pair"),
    )
    op.create_index("ix_oa_secretaries_principal_employee_id", "oa_secretaries", ["principal_employee_id"])
    op.create_index("ix_oa_secretaries_secretary_employee_id", "oa_secretaries", ["secretary_employee_id"])

    op.add_column(
        "oa_letters",
        sa.Column("principal_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_oa_letters_principal_employee_id", "oa_letters", ["principal_employee_id"])

    op.create_table(
        "oa_task_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("oa_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("oa_files.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("added_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_oa_task_attachments_task_id", "oa_task_attachments", ["task_id"])
    op.create_index("ix_oa_task_attachments_file_id", "oa_task_attachments", ["file_id"])


def downgrade() -> None:
    op.drop_index("ix_oa_task_attachments_file_id", table_name="oa_task_attachments")
    op.drop_index("ix_oa_task_attachments_task_id", table_name="oa_task_attachments")
    op.drop_table("oa_task_attachments")
    op.drop_index("ix_oa_letters_principal_employee_id", table_name="oa_letters")
    op.drop_column("oa_letters", "principal_employee_id")
    op.drop_index("ix_oa_secretaries_secretary_employee_id", table_name="oa_secretaries")
    op.drop_index("ix_oa_secretaries_principal_employee_id", table_name="oa_secretaries")
    op.drop_table("oa_secretaries")
