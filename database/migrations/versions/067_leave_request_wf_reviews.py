"""add WF_Reviews mapping - real approver comment storage location

Revision ID: 067
Revises: 066
Create Date: 2026-09-17

کشف حیاتی (تأییدشده با بررسی مستقیم دیتابیس Kara): نظر واقعی
تأییدکننده در ستون WF_Requests.ManagerIdea ذخیره نمی‌شود - آن ستون
همیشه خالی/"" باقی می‌ماند، حتی برای درخواست ۲۲ که واقعاً از طریق خودِ
کاراوب تأیید شده بود و نظر «موافقت می شود» داشت. آن نظر واقعی در جدول
جداگانه WF_Reviews ذخیره شده بود (RequestId=22, ReviewedEmp_No=222088,
Description="موافقت می شود", ReviewType=4, ShowToPersonal=1).

⚠️ فقط مقدار ReviewType برای «تأیید» با داده واقعی تأیید شد (۴) - کل
جدول WF_Reviews در این نصب فقط همین یک رکورد را داشت، پس مقدار دقیق
«رد» هنوز تأیید نشده (پیش‌فرض حدسی: ۳) - قابل‌اصلاح در تنظیمات سایت.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "067"
down_revision: Union[str, None] = "066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leave_request_mappings",
        sa.Column("wf_reviews_table_name", sa.String(length=128), nullable=True, server_default="WF_Reviews"),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column(
            "wf_reviews_request_id_column", sa.String(length=128), nullable=True, server_default="RequestId"
        ),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column(
            "wf_reviews_reviewed_emp_no_column",
            sa.String(length=128),
            nullable=True,
            server_default="ReviewedEmp_No",
        ),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column(
            "wf_reviews_description_column", sa.String(length=128), nullable=True, server_default="Description"
        ),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column("wf_reviews_type_column", sa.String(length=128), nullable=True, server_default="ReviewType"),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column("wf_reviews_date_column", sa.String(length=128), nullable=True, server_default="ReviewDate"),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column(
            "wf_reviews_show_to_personal_column",
            sa.String(length=128),
            nullable=True,
            server_default="ShowToPersonal",
        ),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column("wf_reviews_approved_type_value", sa.Integer(), nullable=True, server_default="4"),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column("wf_reviews_rejected_type_value", sa.Integer(), nullable=True, server_default="3"),
    )


def downgrade() -> None:
    op.drop_column("leave_request_mappings", "wf_reviews_rejected_type_value")
    op.drop_column("leave_request_mappings", "wf_reviews_approved_type_value")
    op.drop_column("leave_request_mappings", "wf_reviews_show_to_personal_column")
    op.drop_column("leave_request_mappings", "wf_reviews_date_column")
    op.drop_column("leave_request_mappings", "wf_reviews_type_column")
    op.drop_column("leave_request_mappings", "wf_reviews_description_column")
    op.drop_column("leave_request_mappings", "wf_reviews_reviewed_emp_no_column")
    op.drop_column("leave_request_mappings", "wf_reviews_request_id_column")
    op.drop_column("leave_request_mappings", "wf_reviews_table_name")
