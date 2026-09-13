"""add employee-section-manager resolution chain for leave request approver

Revision ID: 060
Revises: 059
Create Date: 2026-09-10

طبق تأیید صریح کاربر: تأییدکننده واقعی (CurEmp_NO) در نرم‌افزار ورود و
خروج فعلی، از زنجیره زیر به‌دست می‌آید - نه یک تخصیص دستی:

    WF_Requests.Emp_No -> Employee.Sec_No -> Sections.Sec_No
                        -> Sections.ManagerEmp_No -> WF_Requests.CurEmp_NO

این دقیقاً همان چیزی است که در داده واقعی مشاهده شد (پرسنل ۳۰۷۴۱۳ در
بخش ۴، مدیر بخش=۲۹۲۹۹۴ -> CurEmp_NO=۲۹۲۹۹۴ در نمونه واقعی). این روش از
این پس اولویت اول است؛ جدول LeaveRequestApprover (تخصیص دستی) فقط به‌
عنوان Fallback برای مواردی که این زنجیره جواب ندهد نگه داشته می‌شود.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "060"
down_revision: Union[str, None] = "059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leave_request_mappings",
        sa.Column("employee_table_name", sa.String(length=128), nullable=True, server_default="Employee"),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column("employee_emp_no_column", sa.String(length=128), nullable=True, server_default="Emp_No"),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column("employee_sec_no_column", sa.String(length=128), nullable=True, server_default="Sec_No"),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column("section_table_name", sa.String(length=128), nullable=True, server_default="Sections"),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column("section_sec_no_column", sa.String(length=128), nullable=True, server_default="Sec_No"),
    )
    op.add_column(
        "leave_request_mappings",
        sa.Column(
            "section_manager_emp_no_column", sa.String(length=128), nullable=True, server_default="ManagerEmp_No"
        ),
    )


def downgrade() -> None:
    op.drop_column("leave_request_mappings", "section_manager_emp_no_column")
    op.drop_column("leave_request_mappings", "section_sec_no_column")
    op.drop_column("leave_request_mappings", "section_table_name")
    op.drop_column("leave_request_mappings", "employee_sec_no_column")
    op.drop_column("leave_request_mappings", "employee_emp_no_column")
    op.drop_column("leave_request_mappings", "employee_table_name")
