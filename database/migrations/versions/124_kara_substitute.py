"""جانشین مدیران کاراوب (WF_Substitute) در پرتال

Revision ID: 124
Revises: 123

- نگاشت جدول WF_Substitute به kara_schema نگاشت مرخصی/ماموریت سایت‌هایی که کاراوب واقعی دارند (جدول کاربران نگاشت شده)
  اضافه می‌شود تا جانشین فعال، درخواست‌های مدیر را در کارتابل خودش ببیند و تصمیم بگیرد.
- وام و مساعده: «جانشین مدیر هم بتواند تأیید کند» برای هر سایت جدا، پیش‌فرض خاموش.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "124"
down_revision: Union[str, None] = "123"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GROUP = (
    '{"wf_substitute.table": "WF_Substitute", "wf_substitute.manager_emp_no": "ManagerEmp_No", '
    '"wf_substitute.substitute_emp_no": "SubstituteEmp_No", "wf_substitute.start_date": "StartDate", '
    '"wf_substitute.end_date": "EndDate", "wf_substitute.is_active": "IsActive"}'
)


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE leave_request_mappings
        SET kara_schema = (kara_schema::jsonb || '{_GROUP}'::jsonb)::json
        WHERE kara_schema::jsonb ? 'users.table' AND NOT kara_schema::jsonb ? 'wf_substitute.table'
        """
    )
    for table in ("loan_site_settings", "advance_settings"):
        op.add_column(
            table,
            sa.Column("allow_kara_substitute", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    for table in ("loan_site_settings", "advance_settings"):
        op.drop_column(table, "allow_kara_substitute")
    op.execute(
        """
        UPDATE leave_request_mappings
        SET kara_schema = (kara_schema::jsonb - 'wf_substitute.table' - 'wf_substitute.manager_emp_no'
            - 'wf_substitute.substitute_emp_no' - 'wf_substitute.start_date' - 'wf_substitute.end_date'
            - 'wf_substitute.is_active')::json
        WHERE kara_schema IS NOT NULL
        """
    )
