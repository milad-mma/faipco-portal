"""add evaluation content tables (periods, forms, categories, questions, options)

Revision ID: 051
Revises: 050
Create Date: 2026-09-06

مرحله دوم سیستم ارزیابی عملکرد - «محتوا»: دوره‌های ارزیابی و فرم‌ها
(با دسته‌بندی/سوال/گزینه). این مرحله فقط مشخص می‌کند «چه چیزی پرسیده
می‌شود و در چه بازه زمانی» - نه «چه کسی چه کسی را ارزیابی می‌کند» (آن
در Migration 050 ساخته شد) و نه خودِ فرایند پرسش‌وپاسخ واقعی (یک مرحله
بعدی).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "051"
down_revision: Union[str, None] = "050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERIOD_STATUS_ENUM = "evaluation_period_status"
_PERIOD_STATUS_VALUES = ("draft", "scheduled", "active", "closed", "archived")

_FORM_STATUS_ENUM = "evaluation_form_status"
_FORM_STATUS_VALUES = ("draft", "active", "inactive", "archived")

_QUESTION_TYPE_ENUM = "evaluation_question_type"
_QUESTION_TYPE_VALUES = ("single_choice", "multiple_choice", "rating", "yes_no", "text", "number", "date")


def upgrade() -> None:
    bind = op.get_bind()
    sa.Enum(*_PERIOD_STATUS_VALUES, name=_PERIOD_STATUS_ENUM).create(bind, checkfirst=True)
    sa.Enum(*_FORM_STATUS_VALUES, name=_FORM_STATUS_ENUM).create(bind, checkfirst=True)
    sa.Enum(*_QUESTION_TYPE_VALUES, name=_QUESTION_TYPE_ENUM).create(bind, checkfirst=True)

    op.create_table(
        "evaluation_periods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(*_PERIOD_STATUS_VALUES, name=_PERIOD_STATUS_ENUM, create_type=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_evaluation_periods_site", "evaluation_periods", ["site_id"])
    op.create_index("ix_evaluation_periods_status", "evaluation_periods", ["status"])

    op.create_table(
        "evaluation_forms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "parent_form_id", sa.Integer(), sa.ForeignKey("evaluation_forms.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "status",
            postgresql.ENUM(*_FORM_STATUS_VALUES, name=_FORM_STATUS_ENUM, create_type=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_evaluation_forms_site", "evaluation_forms", ["site_id"])
    op.create_index("ix_evaluation_forms_status", "evaluation_forms", ["status"])

    op.create_table(
        "evaluation_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "form_id", sa.Integer(), sa.ForeignKey("evaluation_forms.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("weight", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
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
    op.create_index("ix_evaluation_categories_form", "evaluation_categories", ["form_id"])

    op.create_table(
        "evaluation_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("evaluation_categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "question_type",
            postgresql.ENUM(*_QUESTION_TYPE_VALUES, name=_QUESTION_TYPE_ENUM, create_type=False),
            nullable=False,
        ),
        sa.Column("weight", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
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
    op.create_index("ix_evaluation_questions_category", "evaluation_questions", ["category_id"])

    op.create_table(
        "evaluation_question_options",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "question_id",
            sa.Integer(),
            sa.ForeignKey("evaluation_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("score", sa.Numeric(6, 2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("question_id", "sort_order", name="uq_evaluation_option_sort_order"),
    )
    op.create_index("ix_evaluation_options_question", "evaluation_question_options", ["question_id"])

    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('performance.periods.manage', 'مدیریت دوره‌های ارزیابی عملکرد')
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('performance.forms.manage', 'مدیریت فرم‌های ارزیابی عملکرد')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("evaluation_question_options")
    op.drop_table("evaluation_questions")
    op.drop_table("evaluation_categories")
    op.drop_table("evaluation_forms")
    op.drop_table("evaluation_periods")

    sa.Enum(name=_QUESTION_TYPE_ENUM).drop(op.get_bind(), checkfirst=True)
    sa.Enum(name=_FORM_STATUS_ENUM).drop(op.get_bind(), checkfirst=True)
    sa.Enum(name=_PERIOD_STATUS_ENUM).drop(op.get_bind(), checkfirst=True)

    op.execute("DELETE FROM permissions WHERE code IN ('performance.periods.manage', 'performance.forms.manage')")
