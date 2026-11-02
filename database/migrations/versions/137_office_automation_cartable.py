"""اتوماسیون اداری فاز ۳الف: گیرندگان، دسترسی صریح، مسئولیت/ارجاع، هامش، پیوست نامه و جلوگیری از اعلان تکراری

- oa_recipients: گیرنده‌ی اصلی/رونوشت (همیشه شخص؛ نام/سمت/واحد لحظه‌ی انتخاب).
- oa_letter_access: تنها منبع دسترسی محتوایی (بخش ۵.۲ سند)؛ read_at خوانده‌شدن برای هر شخص.
- oa_tasks: مسئولیت (اقدام/اطلاع) و درخت ارجاع.
- oa_notes: هامش داخلی (هرگز در چاپ رسمی نمی‌آید).
- oa_attachments: پیوست نسخه‌ی نامه.
- oa_notification_log: کلید یکتا برای اعلان تکراری.
- oa_letters: sender_employee_id، sent_at.

Revision ID: 137
Revises: 136
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "137"
down_revision: Union[str, None] = "136"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.add_column("oa_letters", sa.Column("sender_employee_id", sa.Integer(),
                                          sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True))
    op.add_column("oa_letters", sa.Column("sender_name_snapshot", sa.String(200), nullable=True))
    op.add_column("oa_letters", sa.Column("sender_title_snapshot", sa.String(200), nullable=True))
    op.add_column("oa_letters", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_oa_letters_sender_employee_id", "oa_letters", ["sender_employee_id"])

    op.create_table(
        "oa_recipients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("letter_id", sa.Integer(), sa.ForeignKey("oa_letters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(4), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name_snapshot", sa.String(200), nullable=False),
        sa.Column("title_snapshot", sa.String(200), nullable=True),
        sa.Column("department_snapshot", sa.String(200), nullable=True),
        sa.Column("selected_via", sa.String(16), nullable=False, server_default="direct"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        *_ts(),
        sa.UniqueConstraint("letter_id", "employee_id", name="uq_oa_recipient_letter_employee"),
    )
    op.create_index("ix_oa_recipients_letter_id", "oa_recipients", ["letter_id"])
    op.create_index("ix_oa_recipients_employee_id", "oa_recipients", ["employee_id"])

    op.create_table(
        "oa_letter_access",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("letter_id", sa.Integer(), sa.ForeignKey("oa_letters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("can_act", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_refer", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("granted_by_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("granted_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
    )
    op.create_index("ix_oa_letter_access_letter_employee", "oa_letter_access", ["letter_id", "employee_id"])
    op.create_index("ix_oa_letter_access_employee", "oa_letter_access", ["employee_id"])

    op.create_table(
        "oa_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("letter_id", sa.Integer(), sa.ForeignKey("oa_letters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_task_id", sa.Integer(), sa.ForeignKey("oa_tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("origin", sa.String(12), nullable=False, server_default="delivery"),
        sa.Column("assignee_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assignee_name_snapshot", sa.String(200), nullable=False),
        sa.Column("assignee_title_snapshot", sa.String(200), nullable=True),
        sa.Column("instruction", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="open"),
        sa.Column("result_note", sa.Text(), nullable=True),
        sa.Column("created_by_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_name_snapshot", sa.String(200), nullable=True),
        sa.Column("acted_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        *_ts(),
    )
    op.create_index("ix_oa_tasks_letter_id", "oa_tasks", ["letter_id"])
    op.create_index("ix_oa_tasks_assignee_status", "oa_tasks", ["assignee_employee_id", "status"])

    op.create_table(
        "oa_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("letter_id", sa.Integer(), sa.ForeignKey("oa_letters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("oa_tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("author_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("author_name_snapshot", sa.String(200), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        *_ts(),
    )
    op.create_index("ix_oa_notes_letter_id", "oa_notes", ["letter_id"])

    op.create_table(
        "oa_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("letter_version_id", sa.Integer(), sa.ForeignKey("oa_letter_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("oa_files.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("added_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_ts(),
    )
    op.create_index("ix_oa_attachments_version", "oa_attachments", ["letter_version_id"])
    op.create_index("ix_oa_attachments_file", "oa_attachments", ["file_id"])

    op.create_table(
        "oa_notification_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(200), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("oa_notification_log")
    op.drop_table("oa_attachments")
    op.drop_table("oa_notes")
    op.drop_table("oa_tasks")
    op.drop_table("oa_letter_access")
    op.drop_table("oa_recipients")
    op.drop_index("ix_oa_letters_sender_employee_id", "oa_letters")
    for col in ("sent_at", "sender_title_snapshot", "sender_name_snapshot", "sender_employee_id"):
        op.drop_column("oa_letters", col)
