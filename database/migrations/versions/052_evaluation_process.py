"""add evaluation process tables (assignments, evaluations, answers)

Revision ID: 052
Revises: 051
Create Date: 2026-09-06

مرحله سوم سیستم ارزیابی عملکرد - خودِ «جریان انجام ارزیابی»: تولید
Assignment (بر اساس ساختار سازمانی Migration 050 + دوره فعال از
Migration 051)، خودِ فرم پرشده (با Historical Snapshot کامل)، و پاسخ هر
سوال (با Snapshot متن/نوع سوال).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "052"
down_revision: Union[str, None] = "051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ASSIGNMENT_STATUS_ENUM = "evaluation_assignment_status"
_ASSIGNMENT_STATUS_VALUES = ("pending", "completed")

_EVALUATION_STATUS_ENUM = "evaluation_status"
_EVALUATION_STATUS_VALUES = ("draft", "submitted")


def upgrade() -> None:
    bind = op.get_bind()
    sa.Enum(*_ASSIGNMENT_STATUS_VALUES, name=_ASSIGNMENT_STATUS_ENUM).create(bind, checkfirst=True)
    sa.Enum(*_EVALUATION_STATUS_VALUES, name=_EVALUATION_STATUS_ENUM).create(bind, checkfirst=True)

    op.create_table(
        "evaluation_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "period_id", sa.Integer(), sa.ForeignKey("evaluation_periods.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("form_id", sa.Integer(), sa.ForeignKey("evaluation_forms.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "evaluator_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "target_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "status",
            postgresql.ENUM(*_ASSIGNMENT_STATUS_VALUES, name=_ASSIGNMENT_STATUS_ENUM, create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "period_id", "form_id", "evaluator_employee_id", "target_employee_id", name="uq_evaluation_assignment"
        ),
    )
    op.create_index("ix_eval_assignment_evaluator", "evaluation_assignments", ["evaluator_employee_id"])
    op.create_index("ix_eval_assignment_target", "evaluation_assignments", ["target_employee_id"])
    op.create_index("ix_eval_assignment_period", "evaluation_assignments", ["period_id"])

    op.create_table(
        "evaluations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "assignment_id",
            sa.Integer(),
            sa.ForeignKey("evaluation_assignments.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(*_EVALUATION_STATUS_VALUES, name=_EVALUATION_STATUS_ENUM, create_type=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("total_score", sa.Float(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evaluator_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("evaluator_personnel_code_snapshot", sa.String(length=64), nullable=False),
        sa.Column("target_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("target_personnel_code_snapshot", sa.String(length=64), nullable=False),
        sa.Column("site_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("department_name_snapshot", sa.String(length=255), nullable=True),
        sa.Column("form_title_snapshot", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_evaluations_status", "evaluations", ["status"])

    op.create_table(
        "evaluation_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "question_id", sa.Integer(), sa.ForeignKey("evaluation_questions.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("question_text_snapshot", sa.Text(), nullable=False),
        sa.Column("question_type_snapshot", sa.String(length=32), nullable=False),
        sa.Column("selected_option_ids", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column("text_value", sa.Text(), nullable=True),
        sa.Column("number_value", sa.Float(), nullable=True),
        sa.Column("date_value", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("evaluation_id", "question_id", name="uq_evaluation_answer_question"),
    )
    op.create_index("ix_eval_answers_evaluation", "evaluation_answers", ["evaluation_id"])

    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('performance.evaluate', 'ارزیابی عملکرد پرسنل تحت مدیریت/سرپرستی')
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('performance.assignments.manage', 'تولید و مدیریت انتساب‌های ارزیابی برای یک دوره')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("evaluation_answers")
    op.drop_table("evaluations")
    op.drop_table("evaluation_assignments")

    sa.Enum(name=_EVALUATION_STATUS_ENUM).drop(op.get_bind(), checkfirst=True)
    sa.Enum(name=_ASSIGNMENT_STATUS_ENUM).drop(op.get_bind(), checkfirst=True)

    op.execute(
        "DELETE FROM permissions WHERE code IN ('performance.evaluate', 'performance.assignments.manage')"
    )
