"""add attendance mapping mode (single_column vs enter_exit_columns)

Revision ID: 049
Revises: 048
Create Date: 2026-09-05

طبق درخواست صریح: بعضی نرم‌افزارهای حضور و غیاب به‌جای یک ردیف-به-ازای-
هر-تردد (date_column/time_column، الگوی اصلی این پروژه)، از چهار ستون
جدا برای ورود/خروج استفاده می‌کنند (مثلاً enterdate/exitdate و
entertime/exittime) - یک ردیف = یک نشست کامل، نه یک تردد منفرد.

date_column/time_column اکنون Nullable هستند (فقط برای
mapping_mode=single_column الزامی‌اند - این الزام در Backend
(schemas/site.py) با model_validator اعمال می‌شود، نه در سطح دیتابیس).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "049"
down_revision: Union[str, None] = "048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MODE_ENUM = "attendance_mapping_mode"
_MODE_VALUES = ("single_column", "enter_exit_columns")


def upgrade() -> None:
    bind = op.get_bind()
    sa.Enum(*_MODE_VALUES, name=_MODE_ENUM).create(bind, checkfirst=True)

    op.add_column(
        "attendance_mappings",
        sa.Column(
            "mapping_mode",
            postgresql.ENUM(*_MODE_VALUES, name=_MODE_ENUM, create_type=False),
            nullable=False,
            server_default="single_column",
        ),
    )

    op.alter_column("attendance_mappings", "date_column", existing_type=sa.String(length=128), nullable=True)
    op.alter_column("attendance_mappings", "time_column", existing_type=sa.String(length=128), nullable=True)

    op.add_column("attendance_mappings", sa.Column("enter_date_column", sa.String(length=128), nullable=True))
    op.add_column("attendance_mappings", sa.Column("enter_time_column", sa.String(length=128), nullable=True))
    op.add_column("attendance_mappings", sa.Column("exit_date_column", sa.String(length=128), nullable=True))
    op.add_column("attendance_mappings", sa.Column("exit_time_column", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("attendance_mappings", "exit_time_column")
    op.drop_column("attendance_mappings", "exit_date_column")
    op.drop_column("attendance_mappings", "enter_time_column")
    op.drop_column("attendance_mappings", "enter_date_column")

    op.alter_column("attendance_mappings", "date_column", existing_type=sa.String(length=128), nullable=False)
    op.alter_column("attendance_mappings", "time_column", existing_type=sa.String(length=128), nullable=False)

    op.drop_column("attendance_mappings", "mapping_mode")
    sa.Enum(name=_MODE_ENUM).drop(op.get_bind(), checkfirst=True)
