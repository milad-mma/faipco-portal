"""add evaluation organizational structure tables

Revision ID: 050
Revises: 049
Create Date: 2026-09-06

قابلیت «ساختار ارزیابی عملکرد» - مشخص می‌کند چه کسی مجاز به ارزیابی چه
کسی است، بر اساس یک انتساب صریح و مخصوص همین ماژول (طبق تصمیم صریح
کاربر، مستقل از نام/مجوز نقش‌های RBAC موجود که قابل‌تغییرند، و مستقل از
Department.supervisor_user_id موجود که برای هدف‌گیری اطلاعیه‌ها استفاده
می‌شود).

پنج جدول:
- evaluation_department_supervisors: سرپرست ارزیابی هر واحد (حداکثر یک نفر)
- evaluation_site_managers: مدیران سایت برای ارزیابی (چند نفر مجاز)
- evaluation_other_managers: سایر مدیرانی که مدیر سایت ارزیابی می‌کند
- evaluation_shift_leads: سرشیفت‌های هر واحد (اختیاری، چند نفر مجاز)
- evaluation_shift_assignments: تعیین می‌کند هر پرسنل عادی زیرمجموعه کدام سرشیفت است
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "050"
down_revision: Union[str, None] = "049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_department_supervisors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "department_id",
            sa.Integer(),
            sa.ForeignKey("departments.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_eval_dept_supervisor_employee", "evaluation_department_supervisors", ["employee_id"])

    op.create_table(
        "evaluation_site_managers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("site_id", "employee_id", name="uq_evaluation_site_manager"),
    )
    op.create_index("ix_eval_site_manager_employee", "evaluation_site_managers", ["employee_id"])

    op.create_table(
        "evaluation_other_managers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("site_id", "employee_id", name="uq_evaluation_other_manager"),
    )
    op.create_index("ix_eval_other_manager_employee", "evaluation_other_managers", ["employee_id"])

    op.create_table(
        "evaluation_shift_leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("department_id", "employee_id", name="uq_evaluation_shift_lead"),
    )
    op.create_index("ix_eval_shift_lead_employee", "evaluation_shift_leads", ["employee_id"])

    op.create_table(
        "evaluation_shift_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "shift_lead_id",
            sa.Integer(),
            sa.ForeignKey("evaluation_shift_leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            sa.Integer(),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
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
    op.create_index("ix_eval_shift_assignment_lead", "evaluation_shift_assignments", ["shift_lead_id"])

    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('performance.structure.manage', 'مدیریت ساختار ارزیابی عملکرد (سرپرست/مدیر سایت/سرشیفت)')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("evaluation_shift_assignments")
    op.drop_table("evaluation_shift_leads")
    op.drop_table("evaluation_other_managers")
    op.drop_table("evaluation_site_managers")
    op.drop_table("evaluation_department_supervisors")
    op.execute("DELETE FROM permissions WHERE code = 'performance.structure.manage'")
