"""add leave/mission request tables (WF_Requests integration)

Revision ID: 056
Revises: 055
Create Date: 2026-09-10

سازوکار «درخواست مرخصی/ماموریت» - سه جدول جدید در دیتابیس خودِ پورتال:
    - leave_request_mappings: نگاشت ستون‌های جدول خام WF_Requests هر سایت
      (دقیقاً همان الگوی attendance_mappings)
    - leave_request_types: نوع‌های قابل‌تعریف توسط ادمین (مرخصی/ماموریت،
      ساعتی/روزانه) - چون خودِ جدول خام فقط دو مقدار OperationsID دارد
      و زیرنوع دقیق را نگه نمی‌دارد
    - leave_request_approvers: تخصیص تأییدکننده هر واحد سازمانی - کاملاً
      مستقل از سرپرستِ اطلاعیه‌ها و سرپرستِ ارزیابی عملکرد

دو مجوز جدید: leave_requests.view (فقط مشاهده - مثلاً حراست) و
leave_requests.manage (مشاهده + ویرایش - مثلاً منابع انسانی).

⚠️ خودِ جدول WF_Requests در این Migration دست‌نخورده باقی می‌ماند - آن
یک دیتابیس/جدول خارجی (متعلق به نرم‌افزار ورود و خروج سایت) است، نه
بخشی از دیتابیس این پورتال.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "056"
down_revision: Union[str, None] = "055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "leave_request_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("table_name", sa.String(length=128), nullable=False, server_default="WF_Requests"),
        sa.Column("request_id_column", sa.String(length=128), nullable=False, server_default="RequestId"),
        sa.Column("emp_no_column", sa.String(length=128), nullable=False, server_default="Emp_No"),
        sa.Column("submitting_date_column", sa.String(length=128), nullable=False, server_default="SubmittingDate"),
        sa.Column("card_no_column", sa.String(length=128), nullable=False, server_default="Card_No"),
        sa.Column("start_date_column", sa.String(length=128), nullable=False, server_default="StartDate"),
        sa.Column("end_date_column", sa.String(length=128), nullable=False, server_default="EndDate"),
        sa.Column("start_hour_column", sa.String(length=128), nullable=False, server_default="StartHour"),
        sa.Column("end_hour_column", sa.String(length=128), nullable=False, server_default="EndHour"),
        sa.Column("duration_column", sa.String(length=128), nullable=False, server_default="Duration"),
        sa.Column("is_final_approved_column", sa.String(length=128), nullable=False, server_default="IsFinalApproved"),
        sa.Column(
            "approval_by_manager_column",
            sa.String(length=128),
            nullable=False,
            server_default="ApprovalByManagerEmp_No",
        ),
        sa.Column("approval_date_column", sa.String(length=128), nullable=False, server_default="ApprovalDate"),
        sa.Column("operations_id_column", sa.String(length=128), nullable=False, server_default="OperationsID"),
        sa.Column("description_column", sa.String(length=128), nullable=False, server_default="Description"),
        sa.Column("cur_emp_no_column", sa.String(length=128), nullable=False, server_default="CurEmp_NO"),
        sa.Column("manager_idea_column", sa.String(length=128), nullable=False, server_default="ManagerIdea"),
        sa.Column(
            "is_first_time_shift_column", sa.String(length=128), nullable=False, server_default="IsFirstTimeShift"
        ),
        sa.Column(
            "persian_start_date_column", sa.String(length=128), nullable=False, server_default="PersianStartDate"
        ),
        sa.Column("application_id_column", sa.String(length=128), nullable=False, server_default="ApplicationId"),
        sa.Column("source_column", sa.String(length=128), nullable=False, server_default="Source"),
        sa.Column("destination_column", sa.String(length=128), nullable=False, server_default="Distination"),
        sa.Column("branch_code_column", sa.String(length=128), nullable=True, server_default="BranchCode"),
        sa.Column("branch_code_value", sa.Integer(), nullable=True),
        sa.Column("application_id_value", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "leave_request_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("is_mission", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_hourly", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "leave_request_approvers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "department_id",
            sa.Integer(),
            sa.ForeignKey("departments.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "approver_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES
            ('leave_requests.view', 'مشاهده همه درخواست‌های مرخصی/ماموریت یک سایت (مثلاً حراست)'),
            ('leave_requests.manage', 'مشاهده و ویرایش همه درخواست‌های مرخصی/ماموریت یک سایت (مثلاً منابع انسانی)')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM permissions WHERE code IN ('leave_requests.view', 'leave_requests.manage')"
    )
    op.drop_table("leave_request_approvers")
    op.drop_table("leave_request_types")
    op.drop_table("leave_request_mappings")
