"""add dependent WF table names for admin delete cascade

Revision ID: 069
Revises: 068
Create Date: 2026-09-18

کشف با بررسی مستقیم Foreign Key های دیتابیس Kara: علاوه بر WF_Reviews،
سه جدول فرزند دیگر هم به WF_Requests وابسته‌اند:

    WF_Attachment               (پیوست فایل)
    WF_MoveUp                   (صعود خودکار زمانی)
    WF_RequestParallelApproval  (تأیید موازی)

همگی ON DELETE NO_ACTION هستند - یعنی دیتابیس خودش آن‌ها را پاک
نمی‌کند و اگر ردیفی داشته باشند، حذف خودِ درخواست با خطای Foreign Key
شکست می‌خورد.

در نصب فعلی هر سه خالی‌اند (فقط WF_Reviews داده دارد)، ولی کاراوب
می‌تواند آن‌ها را پر کند - همان سه قابلیتی که در بررسی سورس کاراوب
دیده شد ولی در پورتال پیاده نشده. پس حذف مدیریتی باید هر چهار جدول را
پاک کند، نه فقط WF_Reviews.

هر سه نام جدول قابل‌پیکربندی‌اند (مثل بقیه نگاشت‌ها) - اگر نصبی این
جدول‌ها را نداشته باشد، کافی است خالی گذاشته شوند تا نادیده گرفته شوند.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "069"
down_revision: Union[str, None] = "068"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leave_request_mappings",
        sa.Column("wf_attachment_table_name", sa.String(length=128), nullable=True, server_default="WF_Attachment"),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column("wf_moveup_table_name", sa.String(length=128), nullable=True, server_default="WF_MoveUp"),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column(
            "wf_parallel_approval_table_name",
            sa.String(length=128),
            nullable=True,
            server_default="WF_RequestParallelApproval",
        ),
    )


def downgrade() -> None:
    op.drop_column("leave_request_mappings", "wf_parallel_approval_table_name")
    op.drop_column("leave_request_mappings", "wf_moveup_table_name")
    op.drop_column("leave_request_mappings", "wf_attachment_table_name")
